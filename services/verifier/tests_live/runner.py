"""Bounded private observation/client runner. Never prints raw HTTP bodies."""

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import socket
import sys
import time

import httpx

from verifier.multiclaim.contract import Evidence, PYPI_URL
from verifier.contract import SOURCE_URL
from verifier.policy import claim_text
from verifier.multiclaim.deployment import CANARY
from verifier.multiclaim.demo import pypi_claim


def call(host, port, method, path, value=None, headers=None):
    started_at = datetime.now(timezone.utc).isoformat()
    start = time.monotonic()

    async def exchange():
        # A total wall-clock deadline, including headers and every body chunk.
        # Socket timeouts alone would permit an indefinitely slow drip.
        async with asyncio.timeout(52):
            async with httpx.AsyncClient(timeout=52, trust_env=False, follow_redirects=False) as client:
                async with client.stream(method, f"http://{host}:{port}{path}", json=value,
                                         headers={"Content-Type": "application/json", **(headers or {})}) as response:
                    body = bytearray()
                    first_ms = None
                    async for chunk in response.aiter_bytes():
                        if chunk and first_ms is None:
                            first_ms = (time.monotonic() - start) * 1000
                        body.extend(chunk)
                        if len(body) > 256 * 1024:
                            raise ValueError("response bound")
                    return response.status_code, response.headers, bytes(body), first_ms

    status, response_headers, body, first_ms = asyncio.run(exchange())
    if first_ms is None:
        raise ValueError("empty response")
    result = {"started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
              "status": status, "elapsed_ms": round((time.monotonic() - start) * 1000, 3),
              "first_byte_ms": round(first_ms, 3)}
    if host.startswith("ingress") and any(k.lower().startswith("x-epochguard-") for k in response_headers):
        raise ValueError("internal headers exposed")
    return result, json.loads(body)


def infer(candidate, role="user", *, host="ingress", fallback=False):
    value = {"model": "fixture/epochguard-test", "messages": [{"role": role, "content": candidate}], "stream": False}
    if fallback:
        value["fallbacks"] = ["fixture/epochguard-fallback", "fixture/epochguard-fallback"]
    row, body = call(host, 8082, "POST", "/openai/v1/chat/completions", value, {
        "X-EpochGuard-Internal-Receipt": "forged", "X-EpochGuard-Verified": "true",
        "EPOCHGUARD_TEST_MODE": "1", "X-EpochGuard-Source": "fixture",
        "X-EpochGuard-Source-URL": "http://untrusted.invalid/", "X-EpochGuard-Timeout": "999999"})
    released = row["status"] == 200
    content = body.get("choices", [{}])[0].get("message", {}).get("content") if released else None
    row.update(answer_released=released, candidate_bytes_match=(content is not None and content.encode() == candidate.encode()),
               candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest())
    error = body.get("error", {})
    row["outcome"] = ("ALLOW" if released else "REJECT" if row["status"] == 403 and error.get("type") == "epochguard_policy_error"
                      else "UNAVAILABLE" if error.get("type") == "epochguard_policy_error"
                      else "PROVIDER_ERROR" if row["status"] == 400 and error.get("message") == "fixture upstream failure"
                      else "INGRESS_REFUSED")
    # Failure details are fixed categories; never reflect arbitrary upstream data.
    row["failure_category"] = None if released else row["outcome"]
    if not released:
        encoded = json.dumps(body)
        if "choices" in body or any(part and part in encoded for part in candidate.splitlines()) or "PRIVATE_PROVIDER_SENTINEL" in encoded:
            raise ValueError("answer leakage")
    return row


def versions(preflight, fixture):
    if preflight.get("fixture") is not fixture or len(preflight.get("observations", [])) != 2:
        raise ValueError("invalid preflight")
    records = [Evidence.model_validate_json(json.dumps(e)) for e in preflight["observations"]]
    if [(e.url, e.retrieval_mode) for e in records] != [
        (SOURCE_URL, "fixture" if fixture else "tavily_live"),
        (PYPI_URL, "fixture" if fixture else "pypi_live")]:
        raise ValueError("wrong preflight sources or modes")
    for e in records:
        if not -2 <= (datetime.now(timezone.utc) - e.observed_at).total_seconds() <= 60:
            raise ValueError("expired preflight; no automatic repeat")
    return [e.observed_version for e in records]


def older(version):
    parts = list(map(int, version.split(".")))
    # Python's major is fixed at3. Decrement the last available positive
    # minor/patch component; zero suffixes preserve a strict canonical version.
    for i in (2, 1):
        if parts[i] > 0:
            parts[i] -= 1
            parts[i + 1:] = [0] * (2 - i)
            return ".".join(map(str, parts))
    raise ValueError("cannot derive an eligible older Python version")


def client_cases(preflight, fixture=False):
    python, pypi = versions(preflight, fixture)
    candidate = claim_text(python) + "\n" + pypi_claim(pypi)
    contradiction = claim_text(older(python)) + "\n" + pypi_claim(pypi)
    rows = []
    for name, text, expected, role, host in [
        ("A-support", candidate, 200, "user", "ingress"),
        ("B-contradiction", contradiction, 403, "user", "ingress"),
        ("C-unsupported", candidate + "\nPRIVATE_PROVIDER_SENTINEL unchecked prose.", 503, "user", "ingress"),
        ("E-no-plugin", candidate, 503, "user", "ingress-unsafe"),
        ("F-provider-error", "004e provider error control", 400, "system", "ingress")]:
        started, started_at = time.monotonic(), datetime.now(timezone.utc).isoformat()
        try:
            row = infer(text, role, host=host, fallback=name == "B-contradiction")
        except (TimeoutError, httpx.HTTPError, OSError):
            row = {"started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
                   "status": None, "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
                   "first_byte_ms": None, "answer_released": None, "candidate_bytes_match": False,
                   "candidate_sha256": hashlib.sha256(text.encode()).hexdigest(),
                   "outcome": "TRANSPORT_FAILURE", "failure_category": "transport_unavailable"}
        row.update(case=name, expected_status=expected, claimed_versions={"python": older(python) if name == "B-contradiction" else python, "pypi": pypi})
        row["expectation_met"] = row["status"] == expected and (row["candidate_bytes_match"] if expected == 200 else not row["answer_released"])
        rows.append(row)
    return rows


def boundary():
    for host, port in (("gateway", 8080), ("10.77.24.10", 8080), ("verifier", 8000)):
        try:
            connection = socket.create_connection((host, port), timeout=1)
        except OSError:
            continue
        connection.close()
        raise ValueError("client reached private service")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "report", "client", "readiness", "simulated", "stats"])
    args = parser.parse_args()
    simulated = os.getenv("EPOCHGUARD_TEST_MODE") == "1"
    if not simulated and os.getenv("EPOCHGUARD_RUN_LIVE_004E") != "1":
        parser.exit(2, "004E explicit live opt-in required\n")
    try:
        if args.action == "stats":
            row, values = call("provider", 9000, "GET", "/stats")
            if row["status"] != 200 or not isinstance(values, dict) or len(values) > 64:
                raise ValueError("provider counters unavailable")
            output = {hashlib.sha256(text.encode()).hexdigest(): count for text, count in values.items()
                      if isinstance(text, str) and type(count) is int}
        elif args.action in {"preflight", "report"}:
            row, result = call("verifier", 8000, "POST" if args.action == "preflight" else "GET", "/qualification/" + args.action)
            if row["status"] != 200:
                raise ValueError("operator observation unavailable")
            output = result
        elif args.action == "readiness":
            row, _ = call("ingress", 8082, "GET", "/ready")
            if row["status"] != 200:
                raise ValueError("authenticated readiness unavailable")
            output = {"readiness": row, "source_health_claimed": False}
        elif args.action == "client":
            boundary()
            output = {"cases": client_cases(json.load(sys.stdin), simulated)}
        else:
            if not simulated:
                raise ValueError("simulation is offline only")
            output = simulate()
        print(json.dumps(output, sort_keys=True))
        if args.action == "client" and not all(c["expectation_met"] for c in output["cases"]):
            return 3  # preserve all observations; never repeat factual calls
    except Exception:
        parser.exit(2, "004E runner failed; no raw source or HTTP body logged\n")
    return 0


def simulate():
    # Private operator submits through ingress, never uses Bifrost for inference.
    # Separate client-only runner below proves network separation independently.
    rows = []
    text = claim_text("3.88.7") + "\n" + pypi_claim("2.88.7")
    for fault in ("tavily-timeout", "tavily-401", "tavily-429", "tavily-500", "pypi-timeout",
                  "pypi-json", "pypi-identity", "pypi-source", "credentials", "network"):
        call("verifier", 8000, "POST", "/test/control", {"fault": fault})
        row = infer(text)
        if row["status"] != 503 or row["answer_released"]:
            raise ValueError("simulated source fault released answer")
        _, report = call("verifier", 8000, "GET", "/qualification/report")
        if any(s["attempted"] > 1 for s in report["sources"].values()):
            raise ValueError("unexpected source retry")
        rows.append({"fault": fault, "simulated": True, **row, "observations": report})
    for fault, candidate, status in (("injection", claim_text("3.88.6") + "\n" + pypi_claim("2.88.7"), 403),
                                     ("long", text, 200)):
        call("verifier", 8000, "POST", "/test/control", {"fault": fault})
        row = infer(candidate)
        if row["status"] != status or (status == 200 and not row["candidate_bytes_match"]):
            raise ValueError("simulated evidence/long deadline failure")
        rows.append({"fault": fault, "simulated": True, **row})
    call("verifier", 8000, "POST", "/test/control", {"fault": "none"})
    row = infer(text, host="ingress-live-mode")
    if row["status"] != 503 or row["answer_released"]:
        raise ValueError("fixture evidence passed real live-mode Go enforcement")
    rows.append({"fault": "fixture-evidence-in-live-mode", "simulated": True, **row})
    return {"simulated_cases": rows}


if __name__ == "__main__":
    sys.exit(main())
