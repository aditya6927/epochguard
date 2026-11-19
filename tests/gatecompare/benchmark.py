"""Private measurement client. Labels never enter an authorization decision."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

HERE = Path(__file__).resolve().parent
DATA = HERE / "data/candidates.json"
DATA_SHA256 = "00bc7980901364e475e7dbeeaedbd4118da8348af8f0e915d9925d936edbefa9"
PATH = "/openai/v1/chat/completions"
SETUP = {"X-Bifrost-Setup-Token": "epochguard-local-dev-only"}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load_dataset(path=DATA):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    if sha(raw) != DATA_SHA256:
        raise ValueError("frozen dataset digest mismatch")
    value = json.loads(raw)
    cases = value["cases"]
    if value["schema_version"] != "005f.dataset.v1" or len(cases) != 24 or len({c["id"] for c in cases}) != 24:
        raise ValueError("frozen dataset shape mismatch")
    return cases


def runtime_hash(verifier, fixture, benchmark=HERE):
    roots = [("verifier", verifier, list(verifier.rglob("*.py"))),
             ("fixture", fixture.parent, [fixture]),
             ("benchmark", benchmark, [*benchmark.glob("*.py"), benchmark / "data/candidates.json"])]
    return sha(b"".join(label.encode()+b"/"+p.relative_to(root).as_posix().encode()+b"\0"+
                        p.read_bytes().replace(b"\r\n", b"\n")
                        for label, root, paths in roots for p in sorted(paths)))


def payload(case):
    return json.dumps({"model": "fixture/epochguard-test", "messages": [
        {"role": "user", "content": case["candidate"]}], "stream": False},
        ensure_ascii=True, separators=(",", ":")).encode()


def protected_outcome(status, body, candidate):
    if status == 200:
        expected = {"object": "chat.completion", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": candidate}}]}
        if body != expected:
            raise ValueError("protected content or envelope mismatch")
        return "ALLOW", True
    refusals = {
        "REJECT": (403, "epochguard_policy_error", "epochguard_rejected", "EpochGuard refused the provider response."),
        "UNAVAILABLE": (503, "epochguard_policy_error", "epochguard_verification_unavailable", "EpochGuard verification is unavailable."),
        "INGRESS_REFUSED": (503, "epochguard_ingress_error", "epochguard_ingress_refused", "EpochGuard protected ingress refused the response.")}
    for outcome, (code, kind, error, message) in refusals.items():
        if status == code and body == {"error": {"type": kind, "code": error, "message": message}}:
            return outcome, False
    raise ValueError("unexpected protected response")


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None}
    return {"n": len(ordered), "p50_ms": ordered[math.ceil(.50*len(ordered))-1]/1e6,
            "p95_ms": ordered[math.ceil(.95*len(ordered))-1]/1e6,
            "mean_ms": statistics.fmean(ordered)/1e6}


def metrics(cases, rows):
    labels = {c["id"]: c for c in cases}
    subsets = {
        "unsafe_answers_delivered": lambda c: c["truth"] == "unsafe",
        "supported_answers_delivered_correctly": lambda c: c["category"] == "supported",
        "safe_but_unnecessary_refusals": lambda c: c["unnecessary_refusal"],
        "unknown_or_inconclusive_answers_delivered": lambda c: c["truth"] == "unknown",
        "all_labelled_correct_answers_delivered": lambda c: c["truth"] == "correct",
        "missing_plugin_refusals": lambda c: c["missing_plugin"]}
    result = {"cases": len({r["case"] for r in rows}), "matched_pairs": len(rows)}
    for name, predicate in subsets.items():
        selected = [r for r in rows if predicate(labels[r["case"]])]
        refuse = name in {"safe_but_unnecessary_refusals", "missing_plugin_refusals"}
        result[name] = {"denominator_cases": len({r["case"] for r in selected}),
            "denominator_observations": len(selected), **{
                path: sum(not r[path]["candidate_content_reached_client"] if refuse
                          else r[path]["candidate_content_reached_client"] for r in selected)
                for path in ("unprotected", "protected")}}
    result["protected_outcomes"] = dict(Counter(r["protected"]["outcome"] for r in rows))
    result["latency"] = {path: quantiles([r[path]["elapsed_ns"] for r in rows])
                         for path in ("unprotected", "protected")}
    result["latency"]["matched_added"] = quantiles([r["added_latency_ns"] for r in rows])
    result["source_invocations"] = {path: {source: sum(r[path]["source_invocations"][source] for r in rows)
        for source in ("python", "pypi")} for path in ("unprotected", "protected")}
    return result


def summarize(cases, rows, repetitions):
    labels = {c["id"]: c for c in cases}
    expected_pairs = {(c["id"], i) for c in cases for i in range(repetitions)}
    if len(rows) != len(expected_pairs) or {(r["case"], r["repetition"]) for r in rows} != expected_pairs:
        raise ValueError("incomplete measured denominator")
    matches = []
    for row in rows:
        case = labels[row["case"]]
        digest = sha(case["candidate"].encode())
        exact_request = sha(payload(case))
        matches.append(row["protected"]["outcome"] == case["expected"] and
            row["protected"]["status"] == {"ALLOW": 200, "REJECT": 403, "UNAVAILABLE": 503, "INGRESS_REFUSED": 503}[case["expected"]] and
            row["protected"]["source_invocations"] == case["sources"] and
            row["unprotected"]["status"] == 200 and row["unprotected"]["outcome"] == "DELIVERED" and
            row["unprotected"]["source_invocations"] == {"python": 0, "pypi": 0})
        if row["added_latency_ns"] != row["protected"]["elapsed_ns"] - row["unprotected"]["elapsed_ns"]:
            raise ValueError("unmatched latency delta")
        for path in ("unprotected", "protected"):
            measured = row[path]
            if (measured["request_sha256"] != exact_request or measured["provider_requests"] != 1 or
                measured["elapsed_ns"] < 0 or
                measured["candidate_content_reached_client"] != (measured["status"] == 200 and measured["outcome"] in {"ALLOW", "DELIVERED"}) or
                measured["content_sha256"] != (digest if measured["candidate_content_reached_client"] else None)):
                raise ValueError("invalid measured correspondence")
    return {"expectations_met": all(matches), "overall": metrics(cases, rows),
        "categories": {category: metrics(cases, [r for r in rows if labels[r["case"]]["category"] == category])
                       for category in sorted({c["category"] for c in cases})}}


def counters(operator):
    sources = operator.get("http://verifier:8000/test/report")
    provider = operator.get("http://provider:9000/stats")
    sources.raise_for_status()
    provider.raise_for_status()
    info = sources.json()
    if not info["fixture"] or not info["simulated_transports"] or info["active"]:
        raise ValueError("fixture state mismatch")
    # Provider stats contain synthetic prompt keys; export only the total.
    return info["source_invocations"], sum(provider.json().values())


def check_inventory(loaded):
    protected, baseline = set(loaded["gateway"]), set(loaded["gateway-control"])
    # Pinned Bifrost loads its own built-ins even with configured plugins=[].
    # Both paths must have the same built-ins; EpochGuard is the sole addition.
    if ("epochguard" in baseline or "semantic_cache" in protected | baseline or
        protected-baseline != {"epochguard"} or baseline-protected):
        raise ValueError("genuine baseline or protected plugin unavailable")


def observed_request(client, operator, case, wire, path):
    before, before_provider = counters(operator)
    url = "http://gateway-control:8080" if path == "unprotected" else (
        "http://ingress-unsafe:8082" if case["missing_plugin"] else "http://ingress:8082")
    started = time.perf_counter_ns()
    with client.stream("POST", url+PATH, content=wire, headers={"Content-Type": "application/json"}) as response:
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 256*1024:
                raise ValueError("response bound")
    elapsed = time.perf_counter_ns() - started
    after, after_provider = counters(operator)
    body = json.loads(data)
    if path == "protected":
        if any(k.startswith("x-epochguard-") for k in response.headers):
            raise ValueError("internal metadata leaked")
        outcome, delivered = protected_outcome(response.status_code, body, case["candidate"])
    else:
        choice = body["choices"][0]
        if (response.status_code != 200 or len(body["choices"]) != 1 or choice["finish_reason"] != "stop" or
            choice["message"] != {"role": "assistant", "content": case["candidate"]}):
            raise ValueError("unprotected provider correspondence failed")
        outcome, delivered = "DELIVERED", True
    return {"status": response.status_code, "outcome": outcome, "elapsed_ns": elapsed,
        "candidate_content_reached_client": delivered,
        "content_sha256": sha(case["candidate"].encode()) if delivered else None,
        "request_sha256": sha(wire), "response_sha256": sha(data),
        "source_invocations": {k: after[k]-before[k] for k in before},
        "provider_requests": after_provider-before_provider}


def measure(cases, repetitions, rows, controls):
    import httpx
    with ExitStack() as stack:
        clients = {name: stack.enter_context(httpx.Client(timeout=12, trust_env=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2)))
            for name in ("operator", "unprotected", "protected")}
        operator = clients["operator"]
        loaded = {}
        controls["stage"] = "plugin_inventory"
        controls["inventory_status"] = {}
        for host in ("gateway", "gateway-control"):
            r = operator.get(f"http://{host}:8080/api/plugins/loaded", headers=SETUP)
            controls["inventory_status"][host] = r.status_code
            r.raise_for_status()
            loaded[host] = r.json()["plugins"]
        controls["loaded_plugins"] = loaded
        check_inventory(loaded)
        controls["stage"] = "readiness"
        before, _ = counters(operator)
        readiness = {host: operator.get(f"http://{host}:8082/ready").status_code for host in ("ingress", "ingress-unsafe")}
        after, _ = counters(operator)
        if readiness != {"ingress": 200, "ingress-unsafe": 503} or before != after:
            raise ValueError("readiness boundary failed")
        controls.update(loaded_plugins=loaded, readiness=readiness, readiness_source_invocations=0)
        warmup = []
        for i in range(2):
            for path in ("unprotected", "protected"):
                controls["stage"] = "warmup_"+path
                warmup.append({"path": path, **observed_request(clients[path], operator, cases[0], payload(cases[0]), path)})
        controls["warmup"] = warmup
        for case_index, case in enumerate(cases):
            controls["stage"] = "case_"+case["id"]
            r = operator.post("http://verifier:8000/test/control", json={"fault": case["fault"]})
            r.raise_for_status()
            wire = payload(case)
            for repetition in range(repetitions):
                order = ("unprotected", "protected") if (case_index+repetition) % 2 == 0 else ("protected", "unprotected")
                row = {"case": case["id"], "repetition": repetition, "order": list(order)}
                for path in order:
                    row[path] = observed_request(clients[path], operator, case, wire, path)
                row["added_latency_ns"] = row["protected"]["elapsed_ns"] - row["unprotected"]["elapsed_ns"]
                rows.append(row)
        controls["final_sources"], controls["final_provider_requests"] = counters(operator)
        controls["stage"] = "complete"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    rows, controls = [], {}
    result = {"schema_version": "005f.measurements.v1", "complete": False,
              "dataset_sha256": DATA_SHA256, "repetitions": args.repetitions,
              "measurements": rows, "controls": controls}
    try:
        controls["stage"] = "dataset"
        cases = load_dataset()
        controls["stage"] = "runtime_identity"
        result["runtime_sha256"] = runtime_hash(Path("/app/verifier"), Path("/app/tests_bounded_prose/simulated.py"))
        measure(cases, args.repetitions, rows, controls)
        result.update(complete=True, summary=summarize(cases, rows, args.repetitions))
    except Exception as exc:
        result["failure"] = "measurement_failed; incomplete observations retained"
        result["failure_type"] = type(exc).__name__
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
