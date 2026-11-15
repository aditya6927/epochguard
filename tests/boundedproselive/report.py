"""Standard-library, closed-shape report validation; never serializes raw inputs."""
from datetime import datetime
import hashlib
import math
import re

POLICY = "004g.v1/bounded-prose-v1"
PYTHON = "python-windows-latest-v1"
PYPI = "pypi-requests-reported-v1"
SOURCES = {PYTHON: ("https://www.python.org/downloads/windows/", "tavily_live"),
           PYPI: ("https://pypi.org/pypi/requests/json", "pypi_live")}


def require(condition):
    if not condition:
        raise ValueError("invalid qualification observations")


def shape(value, fields):
    require(type(value) is dict and set(value) == set(fields.split()))
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value))
    return value


def stamp(value):
    require(type(value) is str and len(value) <= 40)
    require(datetime.fromisoformat(value).tzinfo is not None)
    return value


def number(value):
    require(type(value) in {int, float} and math.isfinite(value) and 0 <= value <= 300000)
    return value


def version(value):
    require(type(value) is str and re.fullmatch(r"(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})", value))
    return value


def evidence(value, policy, simulated):
    shape(value, "evidence_id url retrieval_mode retrieval_id content_sha256 observed_version retrieved_at observed_at")
    url, mode = SOURCES[policy]
    require((value["url"], value["retrieval_mode"]) == (url, "fixture" if simulated else mode))
    require(type(value["retrieval_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["retrieval_id"]))
    require(digest(value["evidence_id"]) == hashlib.sha256(
        f"{value['url']}|{value['retrieval_mode']}|{value['retrieval_id']}|{digest(value['content_sha256'])}".encode()).hexdigest())
    require(stamp(value["retrieved_at"]) == stamp(value["observed_at"]))
    version(value["observed_version"])
    return dict(value)


def source_counts(values):
    shape(values, "python pypi")
    output = {}
    failures = {"cancelled", "tavily_timeout", "tavily_http_unauthorized", "tavily_http_rate_limited",
                "tavily_http_server_error", "tavily_http_failure", "tavily_request_failure", "invalid_evidence",
                "ambiguous_evidence", "retrieval_unavailable", "retrieval_credentials_unavailable"}
    for name, value in values.items():
        shape(value, "attempted completed calls")
        require(type(value["attempted"]) is int and type(value["completed"]) is int
                and 0 <= value["completed"] <= value["attempted"] <= 3)
        require(type(value["calls"]) is list and len(value["calls"]) == value["attempted"])
        calls = []
        for i, row in enumerate(value["calls"], 1):
            shape(row, "source attempt started_at completed elapsed_ms finished_at" + (" failure" if "failure" in row else ""))
            require(row["source"] == name and type(row["attempt"]) is int and row["attempt"] == i)
            require(type(row["completed"]) is bool)
            if "failure" in row:
                require(row["failure"] in failures and row["completed"] is False)
            stamp(row["started_at"]); stamp(row["finished_at"]); number(row["elapsed_ms"])
            calls.append(dict(row))
        require(sum(c["completed"] for c in calls) == value["completed"])
        output[name] = {"attempted": value["attempted"], "completed": value["completed"], "calls": calls}
    return output


def observations(value, simulated):
    shape(value, "schema_version policy_id simulated_transports fixture records sources count_scope")
    require(value["schema_version"] == "004gl.observations.v1" and value["policy_id"] == POLICY)
    require(value["simulated_transports"] is simulated and value["fixture"] is simulated)
    require(value["count_scope"] == "retrieval invocations in this process; not billing or origin-fetch counts")
    require(type(value["records"]) is list and len(value["records"]) <= 16)
    rows = []
    for row in value["records"]:
        shape(row, "candidate_sha256 started_at verdict claims coverage canonical_sha256 completed elapsed_ms finished_at")
        digest(row["candidate_sha256"]); stamp(row["started_at"]); stamp(row["finished_at"]); number(row["elapsed_ms"])
        require(row["verdict"] in {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"})
        require(row["coverage"] in {"COMPLETE", "UNCERTAIN"} and type(row["completed"]) is bool)
        if row["canonical_sha256"] is not None:
            digest(row["canonical_sha256"])
        require(type(row["claims"]) is list and len(row["claims"]) <= 8)
        claims = []
        for i, claim in enumerate(row["claims"], 1):
            shape(claim, "claim_id policy_id claimed_version verdict evidence")
            require(claim["claim_id"] == f"c{i:03d}" and claim["policy_id"] in SOURCES)
            version(claim["claimed_version"])
            require(claim["verdict"] in {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"})
            require(type(claim["evidence"]) is list and len(claim["evidence"]) <= 1)
            claims.append({**claim, "evidence": [evidence(e, claim["policy_id"], simulated) for e in claim["evidence"]]})
        rows.append({**row, "claims": claims})
    return {**value, "records": rows, "sources": source_counts(value["sources"])}


def preflight(value, simulated):
    shape(value, "observations fixture simulated_transports")
    require(value["fixture"] is simulated and value["simulated_transports"] is simulated)
    require(type(value["observations"]) is list and len(value["observations"]) == 2)
    return {**value, "observations": [evidence(e, p, simulated) for e, p in zip(value["observations"], SOURCES)]}


def assemble(probe, observed, clients, before, after, *, live, revision):
    require(type(revision) is str and re.fullmatch(r"[a-f0-9]{40}", revision))
    probe = preflight(probe, not live)
    observed = observations(observed, not live)
    shape(clients, "cases")
    require(type(clients["cases"]) is list and len(clients["cases"]) == 5)
    for counters in (before, after):
        require(type(counters) is dict and len(counters) <= 64)
        for key, count in counters.items():
            digest(key); require(type(count) is int and 0 <= count <= 64)
    baseline = {p: e["observed_version"] for p, e in zip(SOURCES, probe["observations"])}
    cases = []
    names = ("A-support", "B-contradiction", "C-unsupported", "D-no-plugin", "E-provider-error")
    statuses = (200, 403, 503, 503, 400)
    outcomes = ("ALLOW", "REJECT", "UNAVAILABLE", "INGRESS_REFUSED", "PROVIDER_ERROR")
    for row, name, status, outcome in zip(clients["cases"], names, statuses, outcomes):
        shape(row, "started_at finished_at status elapsed_ms first_byte_ms request_sha256 case candidate_sha256 answer_released candidate_bytes_match outcome expectation_met receipt_validation")
        require(row["case"] == name and type(row["status"]) is int and 100 <= row["status"] <= 599)
        stamp(row["started_at"]); stamp(row["finished_at"]); number(row["elapsed_ms"])
        if row["first_byte_ms"] is not None:
            number(row["first_byte_ms"])
        digest(row["request_sha256"]); candidate = digest(row["candidate_sha256"])
        for field in ("answer_released", "candidate_bytes_match", "expectation_met"):
            require(type(row[field]) is bool)
        require(row["outcome"] in set(outcomes))
        require(row["receipt_validation"] == ("refused_or_unavailable" if row["outcome"] == "INGRESS_REFUSED" else "passed_ingress_v2_checks"))
        require(row["answer_released"] is (row["status"] == 200))
        require(row["candidate_bytes_match"] is row["answer_released"])
        require(row["expectation_met"] is (row["status"] == status and row["outcome"] == outcome))
        matches = [r for r in observed["records"] if r["candidate_sha256"] == candidate]
        require(len(matches) <= 1)
        if name in {"A-support", "B-contradiction"}:
            require(len(matches) == 1)
            claims = matches[0]["claims"]
            require([c["policy_id"] for c in claims] == [PYTHON, PYPI])
            if name == "A-support":
                expected_versions = [baseline[PYTHON], baseline[PYPI]]
            else:
                parts = list(map(int, baseline[PYTHON].split(".")))
                for index in (2, 1):
                    if parts[index] > 0:
                        parts[index] -= 1
                        parts[index + 1:] = [0] * (2 - index)
                        break
                else:
                    raise ValueError("cannot derive older version")
                expected_versions = [".".join(map(str, parts)), baseline[PYPI]]
            require([c["claimed_version"] for c in claims] == expected_versions)
            canonical = (f"The latest stable Python 3 release for Windows listed on Python.org is {expected_versions[0]}.\n"
                         f"The version reported for requests by the PyPI JSON API is {expected_versions[1]}.")
            require(matches[0]["canonical_sha256"] == hashlib.sha256(canonical.encode()).hexdigest())
        changed = any(e["observed_version"] != baseline[c["policy_id"]]
                      for record in matches for c in record["claims"] for e in c["evidence"])
        calls = after.get(candidate, 0) - before.get(candidate, 0)
        require(calls == 1)  # unique candidates give independent dispatch counts
        if row["status"] == 200:
            require(name == "A-support" and len(matches[0]["claims"]) == 2
                    and matches[0]["coverage"] == "COMPLETE" and matches[0]["verdict"] == "SUPPORTED"
                    and all(c["verdict"] == "SUPPORTED" and len(c["evidence"]) == 1 for c in matches[0]["claims"]))
        cases.append({**row, "provider_calls": calls, "provider_count_scope": "this unique candidate",
                      "source_changed_since_preflight": changed, "verifier_observations": matches,
                      "failure_reason": "source_changed_since_preflight" if changed else None if row["expectation_met"] else "unexpected_http_outcome",
                      "qualification_status": "EXPECTED_OUTCOME" if row["expectation_met"] and not changed else "INCONCLUSIVE_OR_FAILED"})
    met = all(c["qualification_status"] == "EXPECTED_OUTCOME" for c in cases)
    if met:
        require(all(s["attempted"] == s["completed"] == 3 for s in observed["sources"].values()))
    return {"schema_version": "004gl.qualification.v1", "revision": revision, "policy_id": POLICY,
            "receipt_protocol": "004g.receipt.v2", "controlled_provider_fixture": True,
            "simulated_transports": not live, "live_qualification_pending": True,
            "receipt_observation_scope": "inferred from protected ingress release checks; raw receipts are not exported",
            "latency_scope": "client wall time; first byte is first decoded HTTP body chunk, not packet timing",
            "count_scope": observed["count_scope"], "preflight": probe, "cases": cases,
            "sources": observed["sources"], "expectations_met": met,
            "status": ("LIVE_RUN_COLLECTED_REVIEW_REQUIRED" if live else "OFFLINE_EXPECTATIONS_MET") if met else "INCONCLUSIVE_OR_FAILED"}
