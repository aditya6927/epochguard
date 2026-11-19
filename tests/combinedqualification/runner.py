"""Separate private operator/client roles; output bounded sanitized records only."""
import asyncio
import json
import socket
import sys
import time
from modelqualification.runner import call, classify, PATH
from modelqualification.common import sha
from .common import read_runtime, read_plan, scenarios, live_guards


async def execute(action):
    runtime = read_runtime()
    if runtime.live:
        live_guards()
    if action == "source-report":
        status, value = await call("verifier", 8000, "GET", "/qualification/report")
        if status != 200: raise ValueError("source observations unavailable")
        return value
    if action == "sample":
        status, value = await call("verifier", 8000, "POST", "/qualification/preflight")
        return {"status": status, "preflight": value if status == 200 else None}
    if action == "report":
        source = await execute("source-report")
        status, transport = await call("relay", 9001, "GET", "/report")
        if status != 200: raise ValueError("transport observations unavailable")
        return {"verifier": source, "transport": transport}
    if action == "readiness":
        status, _ = await call("ingress", 8082, "GET", "/ready")
        if status != 200: raise ValueError("readiness refused")
        return {"ready": True, "source_health_claimed": False}
    if action != "client":
        raise ValueError("unknown role")
    outputs, prompts = scenarios(read_plan(runtime), runtime)
    for host, port in (("gateway",8080),("gateway-control",8080),("verifier",8000),("relay",9001),("provider",9000)):
        try:
            connection = socket.create_connection((host, port), timeout=1)
        except OSError:
            continue
        connection.close()
        raise ValueError("private service exposed")
    rows = []
    controls = ["missing_plugin", "controlled_provider_error"] if runtime.batch == "standard" else []
    for name in [*outputs, *controls]:
        value = {"model": "gemini/"+runtime.settings.model, "messages": [{"role":"user","content":prompts.get(name, outputs.get("supported", ""))}],
                 "stream": False, "max_completion_tokens": runtime.settings.output_tokens}
        if name in controls:
            value.pop("max_completion_tokens")
            value["model"] = "fixture/epochguard-test"
            if name == "controlled_provider_error": value["messages"][0]["role"] = "system"
        started = time.monotonic()
        status, body = await call("ingress-unsafe" if name == "missing_plugin" else "ingress",8082,"POST",PATH,value)
        outcome, approved = classify(status,body)
        rows.append({"scenario":name,"status":status,"outcome":outcome,"answer_released":status==200,
                     "approved_content_sha256":approved,"elapsed_ms":round((time.monotonic()-started)*1000,3),
                     "request_sha256":sha(json.dumps(value,separators=(",",":"),ensure_ascii=False)),
                     "receipt_boundary":"refused_or_missing" if outcome=="INGRESS_REFUSED" else "runtime_ingress_v2_checks",
                     "minimal_client_envelope_checked":True})
    return {"cases":rows}


def main():
    try:
        print(json.dumps(asyncio.run(execute(sys.argv[1])),allow_nan=False))
    except Exception:
        raise SystemExit("005E role unavailable; raw details withheld; no retry") from None


if __name__ == "__main__":
    main()
