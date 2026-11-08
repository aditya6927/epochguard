"""Deterministic one-to-one span matching and visible dangerous misses."""

from collections import Counter
import statistics


def match_spans(gold, predicted, threshold=0.5):
    """Greedy greatest character-IoU first; ties by gold then prediction index.

    No fractional credit. One broad prediction cannot match multiple assertions.
    Partial spans below 0.5 are both FP and FN. Exact-span metrics use 1.0.
    """
    edges = []
    for i, g in enumerate(gold):
        for j, p in enumerate(predicted):
            intersection = max(0, min(g.end, p.end) - max(g.start, p.start))
            union = max(g.end, p.end) - min(g.start, p.start)
            if union and intersection / union >= threshold:
                edges.append((-intersection / union, i, j))
    used_gold, used_pred, pairs = set(), set(), []
    for _, i, j in sorted(edges):
        if i not in used_gold and j not in used_pred:
            pairs.append((i, j))
            used_gold.add(i)
            used_pred.add(j)
    return pairs


def ratio(a, b):
    return a / b if b else None


def prf(tp, predicted, gold):
    return {"precision": ratio(tp, predicted), "recall": ratio(tp, gold),
            "f1": ratio(2*tp, predicted+gold), "matched":tp, "predicted":predicted, "gold":gold}


def score(records):
    gold_count = pred_count = matches = exact = fresh_gold = fresh_pred = fresh_tp = 0
    temporal_correct = uncertain = units = failures = critical_stable = critical_omitted = dynamic_gold = dynamic_uncertain = 0
    temporal = Counter()
    critical, errors = [], []
    times, costs, in_tokens, out_tokens = [], [], [], []
    for record in records:
        case, result = record["case"], record["extraction"]
        times.append(record["latency_ms"])
        if record.get("input_tokens") is not None:
            in_tokens.append(record["input_tokens"])
            out_tokens.append(record["output_tokens"])
            costs.append(record["estimated_cost_usd"])
        if case.expected_outcome == "INVALID_INPUT":
            if record["status"] != "INVALID_INPUT":
                failures += 1
            continue
        failures += record["status"] != "ANALYZED"
        g = [c for c in case.gold.claims if c.factuality == "FACTUAL"]
        p = [c for c in result.claims if c.factuality == "FACTUAL"] if result else []
        all_pred = result.claims if result else []
        units += len(all_pred)
        uncertain += sum(c.factuality == "UNCERTAIN" or (c.factuality == "FACTUAL" and c.temporal == "UNCERTAIN") for c in all_pred)
        pairs = match_spans(g, p)
        mapping = dict(pairs)
        matches += len(pairs)
        exact += len(match_spans(g, p, 1.0))
        gold_count += len(g)
        pred_count += len(p)
        gf = [c for c in case.gold.claims if c.fresh_evidence == "REQUIRED"]
        pf = [c for c in all_pred if c.fresh_evidence == "REQUIRED"]
        fresh_gold += len(gf)
        fresh_pred += len(pf)
        fresh_tp += len(match_spans(gf, pf))
        for i, claim in enumerate(g):
            prediction = p[mapping[i]] if i in mapping else None
            temporal[claim.temporal, prediction.temporal if prediction else "MISSING"] += 1
            if prediction:
                temporal_correct += claim.temporal == prediction.temporal
            if claim.temporal == "DYNAMIC":
                dynamic_gold += 1
                category = None
                if prediction is None:
                    critical_omitted += 1
                    category = "OMITTED_OR_NOT_IDENTIFIED_AS_FACTUAL"
                elif prediction.temporal in {"STABLE", "HISTORICAL"}:
                    critical_stable += 1
                    category = "DYNAMIC_LABELED_NONFRESH"
                elif prediction.temporal == "UNCERTAIN":
                    dynamic_uncertain += 1
                if category:
                    critical.append({"case_id":case.case_id, "claim_id":claim.claim_id,
                                     "source_text":claim.source_text, "kind":category})
            if prediction is None or prediction.temporal != claim.temporal or prediction.fresh_evidence != claim.fresh_evidence:
                errors.append({"case_id":case.case_id, "source_text":claim.source_text,
                               "gold_temporal":claim.temporal, "predicted_temporal":prediction.temporal if prediction else None})
        for j, prediction in enumerate(p):
            if j not in mapping.values():
                temporal["SPURIOUS", prediction.temporal] += 1
    f1s = {}
    for category in ("DYNAMIC", "HISTORICAL", "STABLE", "UNCERTAIN"):
        tp = temporal[category, category]
        actual = sum(v for (a, _), v in temporal.items() if a == category)
        guessed = sum(v for (_, b), v in temporal.items() if b == category)
        f1s[category] = ratio(2*tp, actual+guessed) if actual+guessed else 0.0
    return {
        "responses":len(records), "analysis_failures_or_invalid_outcomes":failures,
        "claim":prf(matches,pred_count,gold_count), "exact_span_claim":prf(exact,pred_count,gold_count),
        "temporal_matched_accuracy":ratio(temporal_correct,matches),
        "temporal_end_to_end_accuracy":ratio(temporal_correct,gold_count),
        "temporal_macro_f1":sum(f1s.values())/4, "temporal_per_class_f1":f1s,
        "temporal_confusion":[{"gold":a,"predicted":b,"count":v} for (a,b),v in sorted(temporal.items())],
        "fresh_evidence":prf(fresh_tp,fresh_pred,fresh_gold),
        "critical_misses":{"dynamic_gold":dynamic_gold,"omitted":critical_omitted,"labeled_nonfresh":critical_stable,"uncertain_dynamic":dynamic_uncertain,"cases":critical},
        "uncertainty_rate":ratio(uncertain,units), "uncertain_units":uncertain, "predicted_units":units,
        "latency_ms":{"median":statistics.median(times) if times else None,"max":max(times) if times else None},
        "usage":{"reported_responses":len(in_tokens),"input_tokens":sum(in_tokens) if in_tokens else None,
                 "output_tokens_including_thoughts":sum(out_tokens) if out_tokens else None,
                 "estimated_cost_usd":sum(costs) if costs else None}, "errors":errors}
