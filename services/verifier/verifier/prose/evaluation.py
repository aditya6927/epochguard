"""Draft-label risk metrics. F1 never stands in for complete coverage."""

import re

from claim_analysis.evaluation import match_spans, prf, ratio

GOLD_VERSION = re.compile(r"(?<!\d)(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})\.(?:0|[1-9][0-9]{0,2})(?!\d)")


def score(records, *, audit_decisions=True):
    gold_count = pred_count = matched = exact = fresh_gold = fresh_pred = fresh_tp = 0
    omitted = nonfresh = dynamic = unsupported_maps = gaps = failures = abstentions = ambiguous = 0
    false_complete, misses, wrong_maps = [], [], []
    safe_refusals = 0
    for record in records:
        case, result = record["case"], record["result"]
        proposals = result.proposals if result else ()
        factual = [g.source for g in case.gold if g.source.factuality == "FACTUAL"]
        predicted = [p for p in proposals if p.factuality == "FACTUAL"]
        gold_count += len(factual)
        pred_count += len(predicted)
        matched += len(match_spans(factual, predicted))
        exact += len(match_spans(factual, predicted, 1.0))
        gf = [g.source for g in case.gold if g.source.fresh_evidence == "REQUIRED"]
        pf = [p for p in proposals if p.fresh_evidence == "REQUIRED"]
        fresh_gold += len(gf)
        fresh_pred += len(pf)
        fresh_tp += len(match_spans(gf, pf))
        all_pairs = dict(match_spans([g.source for g in case.gold], proposals))
        categories = []
        for i, gold in enumerate(case.gold):
            prediction = proposals[all_pairs[i]] if i in all_pairs else None
            if gold.source.temporal == "DYNAMIC":
                dynamic += 1
                if prediction is None:
                    omitted += 1
                    misses.append({"case_id": case.case_id, "claim_id": gold.source.claim_id, "category": "DYNAMIC_OMITTED"})
                elif prediction.factuality != "FACTUAL" or prediction.fresh_evidence != "REQUIRED" or prediction.temporal != "DYNAMIC":
                    nonfresh += 1
                    misses.append({"case_id": case.case_id, "claim_id": gold.source.claim_id, "category": "DYNAMIC_NOT_FACTUAL_FRESH"})
            if prediction is None or (prediction.start, prediction.end) != (gold.source.start, gold.source.end):
                categories.append("OMITTED_OR_NONATOMIC_ASSERTION")
            elif gold.source.fresh_evidence == "REQUIRED" and (prediction.factuality, prediction.temporal, prediction.fresh_evidence) != ("FACTUAL", "DYNAMIC", "REQUIRED"):
                categories.append("FRESH_CLASSIFICATION_CONFLICT")
        if result:
            failures += result.overall_status == "ANALYSIS_FAILED"
            for mapping in result.policy_mappings:
                unit = next(u for u in result.risk_units if u.unit_id == mapping.unit_id)
                candidates = [g for g in case.gold if g.source.start < unit.end and g.source.end > unit.start]
                versions = GOLD_VERSION.findall(candidates[0].source.source_text) if len(candidates) == 1 else []
                if not candidates or len(candidates) != 1 or candidates[0].policy_id != mapping.policy_id or len(versions) != 1 or getattr(mapping, "version", None) != versions[0]:
                    unsupported_maps += 1
                    wrong_maps.append({"case_id": case.case_id, "unit_id": unit.unit_id, "category": "UNSUPPORTED_OR_WRONG_POLICY"})
                    categories.append("WRONG_POLICY_MAPPING")
            gaps += len(result.unaccounted_unit_ids)
            if not case.expected_bounded_accounting:
                ambiguous += 1
                safe_refusals += result.overall_status != "PLAN_READY"
                abstentions += result.overall_status in {"PLAN_UNCERTAIN", "PLAN_UNSUPPORTED"}
                categories.append("GOLD_UNSUPPORTED_OR_AMBIGUOUS")
            if audit_decisions and result.coverage == "BOUNDED_ACCOUNTED" and categories:
                false_complete.append({"case_id": case.case_id, "failure_categories": sorted(set(categories))})
        else:
            failures += 1
            if not case.expected_bounded_accounting:
                ambiguous += 1
                safe_refusals += 1
    return {
        "responses": len(records), "claim": prf(matched, pred_count, gold_count),
        "exact_span": prf(exact, pred_count, gold_count),
        "fresh_evidence": prf(fresh_tp, fresh_pred, fresh_gold),
        "dynamic_gold": dynamic, "dynamic_omitted": omitted,
        "dynamic_incorrectly_nonfresh_or_nonfactual": nonfresh, "dynamic_failure_cases": misses,
        "unsupported_assertions_mapped": unsupported_maps if audit_decisions else None,
        "wrong_mapping_cases": wrong_maps if audit_decisions else None,
        "unaccounted_risk_units": gaps if audit_decisions else None,
        "coverage_decision_scope": "bounded audit" if audit_decisions else "not supplied by extractor; syntactic spans are not completeness",
        "false_complete_count": len(false_complete) if audit_decisions else None,
        "false_complete_rate": ratio(len(false_complete), len(records)) if audit_decisions else None,
        "false_complete_cases": false_complete if audit_decisions else None,
        "correct_abstentions": abstentions if audit_decisions else None,
        "ambiguous_or_unsupported_cases": ambiguous,
        "correct_abstention_rate": ratio(abstentions, ambiguous) if audit_decisions else None,
        "safe_refusals_including_failures": safe_refusals if audit_decisions else None,
        "extraction_failures": failures, "extraction_failure_rate": ratio(failures, len(records)),
    }
