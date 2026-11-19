"""Non-authorizing measurement checks; never used for protected release."""
from .common import scenarios, MODEL_CASES, SOURCE_LIMIT
from modelqualification.common import sha


def assemble(runtime, plan, client, observed, native):
    transport, verifier = observed["transport"], observed["verifier"]
    outputs, _ = scenarios(plan, runtime)
    if transport["real_provider"] is not runtime.live or transport["response_mode"] != "strict-005ct":
        raise ValueError("model profile mismatch")
    if verifier["fixture"] is runtime.live or verifier["simulated_transports"] is runtime.live:
        raise ValueError("source profile mismatch")
    records = transport["records"]
    if [r["scenario"] for r in records] != list(outputs) or transport["attempted"] != len(outputs):
        raise ValueError("model accounting mismatch")
    if sum(transport[k] for k in ("completed","failed","cancelled")) != len(records):
        raise ValueError("model totals mismatch")
    controls = ["missing_plugin","controlled_provider_error"] if runtime.batch=="standard" else []
    if [c["scenario"] for c in client["cases"]] != [*outputs,*controls]:
        raise ValueError("client denominator")
    used = set()
    changed = False
    for case in client["cases"]:
        name = case["scenario"]
        model = next((r for r in records if r["scenario"]==name),None)
        stages = [r for r in native if r["request_sha256"]==case["request_sha256"]]
        if name!="missing_plugin" and len(stages)!=1:
            raise ValueError("native stage missing")
        case["native_stages"] = stages[0]["stages"] if stages else None
        expected = {"supported":(200,"ALLOW"),"older":(403,"REJECT"),"unsupported":(503,"UNAVAILABLE"),
            "paraphrase":(503,"UNAVAILABLE"),"missing_plugin":(503,"INGRESS_REFUSED"),
            "controlled_provider_error":(400,"PROVIDER_ERROR"),"provider_error":(400,"PROVIDER_ERROR"),
            "source_changed":(403,"REJECT")}.get(name, (502,"PROVIDER_ERROR") if runtime.batch=="envelopes" or name=="malformed" else (503,"UNAVAILABLE"))
        intention = not model or model["matches_intended_text"] is True
        case["expectation_met"] = (case["status"],case["outcome"])==expected and (intention or name in {"malformed","provider_error"} or runtime.batch=="envelopes")
        case["real_model_submission_attempted"] = bool(model and model["real_provider_invocation_attempted"])
        case["source_changed_since_sampling"] = False
        if model:
            if model["real_provider_invocation_attempted"] is not runtime.live:
                raise ValueError("provider invocation identity")
            adapter = model.get("adapter",{})
            case["adapter"] = adapter
            if adapter.get("validation")=="ACCEPTED":
                if (not adapter.get("text_equal") or adapter["original_text_sha256"]!=adapter["projected_text_sha256"] or
                    adapter["original_text_sha256"]!=model["candidate_sha256"]):
                    raise ValueError("text correspondence mismatch")
                possible = [(i,r) for i,r in enumerate(verifier["records"]) if i not in used and r["candidate_sha256"]==model["candidate_sha256"]]
                if possible:
                    index, checked = possible[0]
                    used.add(index)
                    case["verifier_record_index"] = index
                    if not checked["completed"] or "verifier_request_completed" not in case["native_stages"]:
                        raise ValueError("independent verifier incomplete")
                    if name.endswith("_conflict"):
                        diagnostic = checked.get("claim_report", {})
                        if (checked["coverage"] != "UNCERTAIN" or checked["claims"] or
                            checked["canonical_sha256"] is not None or checked.get("grammar_reason") != "REPEATED_CLAIM" or
                            checked.get("source_calls_before") != checked.get("source_calls_after") or
                            diagnostic.get("claims") != [] or diagnostic.get("authorization") is not False):
                            raise ValueError("singleton conflict was not refused atomically")
                    for claim in checked["claims"]:
                        for evidence in claim["evidence"]:
                            sampled = next(e for e in plan.observations if e.url==evidence["url"])
                            if evidence["observed_version"]!=sampled.observed_version:
                                case["source_changed_since_sampling"] = changed = True
                    if case["answer_released"] and (checked["coverage"]!="COMPLETE" or checked["verdict"]!="SUPPORTED"):
                        raise ValueError("release without evidence")
                else:
                    case["expectation_met"] = False
                    if case["answer_released"] or not runtime.live:
                        raise ValueError("eligible candidate missed verifier")
            elif case["answer_released"]:
                raise ValueError("release without validated original")
            if case["answer_released"] and case["approved_content_sha256"]!=model["candidate_sha256"]:
                raise ValueError("released text changed")
            if case["answer_released"] and adapter.get("validation")!="ACCEPTED":
                raise ValueError("unvalidated release")
        if case["answer_released"] and name=="missing_plugin":
            raise ValueError("unsigned release")
        if not case["answer_released"] and case["approved_content_sha256"] is not None:
            raise ValueError("refusal retained content")
    sources = verifier["sources"]
    if used!=set(range(len(verifier["records"]))):
        raise ValueError("uncorrelated verifier observations")
    for value in sources.values():
        if not 0<=value["completed"]<=value["attempted"]<=SOURCE_LIMIT or value["attempted"]!=len(value["calls"]):
            raise ValueError("source accounting mismatch")
    reservations = verifier["source_budget"]["calls"]
    if len(reservations)!=sum(s["attempted"] for s in sources.values()):
        raise ValueError("source reservation mismatch")
    if any(sum(r["source"]==name for r in reservations)!=sources[name]["attempted"] for name in sources):
        raise ValueError("per-policy accounting mismatch")
    met = all(c["expectation_met"] for c in client["cases"])
    # A changed source can safely contradict a generated label but cannot be
    # repaired into the intended supported live qualification scenario.
    return {"cases":client["cases"],"transport":transport,"verifier":verifier,"native_stages":native,
            "expectations_met":met,"source_changed_since_sampling":changed,
            "qualification_conclusive":met and not changed,
            "receipt_observation":"runtime ingress checks; raw receipts not exported or independently revalidated",
            "provenance_limit":"trusted process observations, not independent external provenance or origin freshness"}
