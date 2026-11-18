"""Private client and operator roles; exports sanitized summaries only."""
import asyncio
import json
import os
import sys
import socket
import httpx
from .common import OUTPUTS, PROMPTS, SUPPORTED, read_settings, sha

PATH = "/openai/v1/chat/completions"


async def call(host, port, method, path, value=None):
    async with asyncio.timeout(48):
        async with httpx.AsyncClient(timeout=48, trust_env=False, follow_redirects=False) as client:
            async with client.stream(method, f"http://{host}:{port}{path}", json=value) as response:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 256*1024:
                        raise ValueError("body bound")
                if host.startswith("ingress") and any(k.startswith("x-epochguard-") for k in response.headers):
                    raise ValueError("internal header leaked")
                return response.status_code, json.loads(data)


def classify(status, body, observed=None):
    if status == 200:
        # The relay hash binds exact observed provider text to released content.
        if set(body) != {"object", "choices"} or body["object"] != "chat.completion" or len(body["choices"]) != 1:
            raise ValueError("metadata projection")
        choice = body["choices"][0]
        if set(choice) != {"index", "finish_reason", "message"} or choice["index"] != 0 or choice["finish_reason"] != "stop" or set(choice["message"]) != {"role", "content"} or choice["message"]["role"] != "assistant":
            raise ValueError("response projection")
        text = choice["message"]["content"]
        if not isinstance(text, str) or (observed is not None and sha(text) != observed):
            raise ValueError("approved content differs")
        return "ALLOW", sha(text)
    error = body.get("error", {})
    if set(body) != {"error"} or set(error) != {"type", "code", "message"}:
        raise ValueError("refusal projection")
    if error == {"type": "epochguard_policy_error", "code": "epochguard_rejected", "message": "EpochGuard refused the provider response."} and status == 403:
        return "REJECT", None
    if error == {"type": "epochguard_policy_error", "code": "epochguard_verification_unavailable", "message": "EpochGuard verification is unavailable."} and status == 503:
        return "UNAVAILABLE", None
    if error == {"type": "epochguard_ingress_error", "code": "epochguard_ingress_refused", "message": "EpochGuard protected ingress refused the response."} and status == 503:
        return "INGRESS_REFUSED", None
    if error.get("code") == "epochguard_provider_error" and error.get("message") == "Provider request failed." and status >= 400:
        return "PROVIDER_ERROR", None
    raise ValueError("unexpected protected response")


async def execute(action):
    if action == "report":
        result = {}
        for name, host, port, path in (("transport", "relay", 9001, "/report"), ("verifier", "verifier", 8000, "/qualification/report")):
            status, value = await call(host, port, "GET", path)
            if status != 200:
                raise ValueError("report unavailable")
            result[name] = value
        return result
    if action == "readiness":
        status, _ = await call("ingress", 8082, "GET", "/ready")
        if status != 200:
            raise ValueError("readiness unavailable")
        return {"ready": True}
    settings = read_settings("/run/qualification/settings.json")
    for host, port in (("gateway", 8080), ("gateway-control", 8080), ("verifier", 8000), ("provider", 9000), ("relay", 9001)):
        try:
            connection = socket.create_connection((host, port), timeout=1)
        except OSError:
            continue
        connection.close()
        raise ValueError("private service exposed to qualification client")
    live = os.getenv("EPOCHGUARD_005C_MODE") == "live"
    cases = []
    import time
    for name in list(OUTPUTS) + ([] if live else ["provider_error", "timeout"]) + ["missing_plugin", "controlled_provider_error"]:
        value = {"model": "gemini/" + settings.model, "messages": [{"role": "user", "content": PROMPTS.get(name, SUPPORTED)}],
                 "stream": False, "max_completion_tokens": settings.output_tokens}
        if name in {"missing_plugin", "controlled_provider_error"}:
            value.pop("max_completion_tokens")
            value["model"] = "fixture/epochguard-test"
            if name == "controlled_provider_error":
                value["messages"][0]["role"] = "system"
        started = time.monotonic()
        status, body = await call("ingress-unsafe" if name == "missing_plugin" else "ingress", 8082, "POST", PATH, value)
        outcome, content_hash = classify(status, body)
        cases.append({"scenario": name, "status": status, "outcome": outcome, "answer_released": status == 200,
                      "approved_content_sha256": content_hash, "elapsed_ms": round((time.monotonic()-started)*1000, 3),
                      "request_sha256": sha(json.dumps(value, separators=(",", ":")))})
    return {"cases": cases}


def main():
    try:
        print(json.dumps(asyncio.run(execute(sys.argv[1] if len(sys.argv) == 2 else "client")), allow_nan=False))
    except Exception:
        raise SystemExit("005C role unavailable; details withheld") from None


if __name__ == "__main__":
    main()
