"""Private qualification roles. Never exports HTTP bodies, headers or receipts."""
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
from tests_live.runner import versions, older

PATH = "/openai/v1/chat/completions"
SENTINEL = "UNVERIFIED_METADATA_004GS"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def call(host, port, method, path, value=None):
    data = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode() if value is not None else b""
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()

    async def exchange():
        async with asyncio.timeout(52):
            async with httpx.AsyncClient(timeout=52, trust_env=False, follow_redirects=False) as client:
                async with client.stream(method, f"http://{host}:{port}{path}", content=data,
                                         headers={"Content-Type": "application/json"}) as response:
                    body, first = bytearray(), None
                    async for chunk in response.aiter_bytes():
                        if chunk and first is None:
                            first = (time.monotonic() - started) * 1000
                        body.extend(chunk)
                        if len(body) > 256 * 1024:
                            raise ValueError("response bound")
                    if host.startswith("ingress") and (any(k.startswith("x-epochguard-") for k in response.headers)
                            or any(SENTINEL in v for v in response.headers.values())):
                        raise ValueError("protected headers leaked")
                    return response.status_code, bytes(body), first

    status, body, first = asyncio.run(exchange())
    return {"started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status, "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "first_byte_ms": round(first, 3) if first is not None else None,
            "request_sha256": sha(data)}, json.loads(body)


def candidates(preflight):
    python, pypi = versions(preflight, preflight["simulated_transports"])
    supported = f"\t Python.org currently lists Python {python} as its latest stable Windows release.\r\n\tPyPI reports requests version {pypi}.\n"
    contradicted = f"Python.org lists Python {older(python)} as its latest stable Windows release.\nAccording to the PyPI JSON API, the version of requests is {pypi}."
    return [
        ("A-support", supported, "user", "ingress", 200),
        ("B-contradiction", contradicted, "user", "ingress", 403),
        ("C-unsupported", supported + "PRIVATE_PROVIDER_SENTINEL unchecked assertion.", "user", "ingress", 503),
        ("D-no-plugin", supported + "\t", "user", "ingress-unsafe", 503),
        ("E-provider-error", "PRIVATE_PROVIDER_SENTINEL provider error control", "system", "ingress", 400),
    ]


def infer(name, text, role, host, expected):
    value = {"model": "fixture/epochguard-test", "messages": [{"role": role, "content": text}], "stream": False}
    if name == "B-contradiction":
        value["fallbacks"] = ["fixture/epochguard-fallback"]
    row, body = call(host, 8082, "POST", PATH, value)
    released = row["status"] == 200
    exact = body == {"object": "chat.completion", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": text}}]}
    error = body.get("error", {})
    if released:
        if not exact:
            raise ValueError("protected content or metadata mismatch")
        outcome = "ALLOW"
    else:
        encoded = json.dumps(body)
        if "choices" in body or SENTINEL in encoded or "PRIVATE_PROVIDER_SENTINEL" in encoded or any(
                line.strip() and len(line.strip()) > 12 and line.strip() in encoded for line in text.splitlines()):
            raise ValueError("candidate leaked")
        if error.get("type") == "epochguard_policy_error":
            outcome = "REJECT" if row["status"] == 403 else "UNAVAILABLE"
        elif error.get("type") == "epochguard_ingress_error":
            outcome = "INGRESS_REFUSED"
        elif row["status"] == 400 and error == {"type": "invalid_request_error", "code": "epochguard_provider_error",
                                                "message": "Provider request failed."}:
            outcome = "PROVIDER_ERROR"
        else:
            raise ValueError("unexpected protected error")
    expected_outcome = {"A-support": "ALLOW", "B-contradiction": "REJECT", "C-unsupported": "UNAVAILABLE",
                        "D-no-plugin": "INGRESS_REFUSED", "E-provider-error": "PROVIDER_ERROR"}[name]
    row.update(case=name, candidate_sha256=sha(text.encode()), answer_released=released,
               candidate_bytes_match=exact, outcome=outcome,
               expectation_met=row["status"] == expected and outcome == expected_outcome,
               receipt_validation="passed_ingress_v2_checks" if outcome != "INGRESS_REFUSED" else "refused_or_unavailable")
    return row


def boundary():
    for host, port in (("gateway", 8080), ("10.77.44.10", 8080), ("gateway-control", 8080),
                       ("verifier", 8000), ("provider", 9000)):
        try:
            connection = socket.create_connection((host, port), timeout=1)
        except OSError:
            continue
        connection.close()
        raise ValueError("private network exposed")
    row, _ = call("ingress", 8082, "POST", "/api/plugins", {})
    if row["status"] != 400:
        raise ValueError("management route exposed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "report", "client", "readiness", "stats", "metadata", "fixture-boundary"])
    args = parser.parse_args()
    simulated = os.getenv("EPOCHGUARD_TEST_MODE") == "1"
    if not simulated and any(os.getenv(n) != "1" for n in ("EPOCHGUARD_RUN_LIVE_004E", "EPOCHGUARD_RUN_LIVE_004G")):
        parser.exit(2, "Both E and G live opt-ins required\n")
    try:
        if args.action == "fixture-boundary":
            if not simulated:
                raise ValueError("fault control is offline only")
            row, _ = call("verifier", 8000, "POST", "/test/control", {"fault": "none"})
            if row["status"] != 200:
                raise ValueError("offline control unavailable")
            text = "Python.org currently lists Python 3.88.7 as its latest stable Windows release.\nPyPI reports requests version 2.88.7."
            row = infer("A-support", text, "user", "ingress-live-mode", 503)
            _, observed = call("verifier", 8000, "GET", "/qualification/report")
            if row["status"] != 503 or row["outcome"] != "UNAVAILABLE" or len(observed["records"]) != 1 or observed["records"][0]["verdict"] != "SUPPORTED":
                raise ValueError("fixture evidence passed live Go validation")
            output = {"fixture_evidence_refused_in_live_mode": True}
        elif args.action in {"preflight", "report"}:
            row, output = call("verifier", 8000, "POST" if args.action == "preflight" else "GET",
                               "/qualification/" + args.action)
            if row["status"] != 200:
                raise ValueError("observation unavailable")
        elif args.action == "metadata":
            row, _ = call("provider", 9000, "POST", "/test/control", {"channel": "id"})
            if row["status"] != 200:
                raise ValueError("metadata control unavailable")
            output = {"metadata_sentinel_enabled": True}
        elif args.action == "stats":
            row, values = call("provider", 9000, "GET", "/stats")
            if row["status"] != 200 or not isinstance(values, dict) or len(values) > 64:
                raise ValueError("counters unavailable")
            output = {sha(text.encode()): count for text, count in values.items() if type(count) is int}
        elif args.action == "readiness":
            row, _ = call("ingress", 8082, "GET", "/ready")
            if row["status"] != 200:
                raise ValueError("readiness unavailable")
            output = {"readiness_status": 200, "source_health_claimed": False}
        else:
            boundary()
            preflight = json.load(sys.stdin)
            if preflight.get("simulated_transports") is not simulated:
                raise ValueError("simulation mismatch")
            output = {"cases": [infer(*case) for case in candidates(preflight)]}
        print(json.dumps(output, sort_keys=True))
        return 3 if args.action == "client" and not all(c["expectation_met"] for c in output["cases"]) else 0
    except Exception:
        parser.exit(2, "004G-L runner failed; raw details withheld; no retry\n")


if __name__ == "__main__":
    sys.exit(main())
