"""Real loopback Lab -> ingress -> native gateway -> simulated verifier checks."""
import concurrent.futures
import json
import time
import urllib.error
import urllib.request

ORIGIN = "http://127.0.0.1:8787"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def call(path, value=None, *, headers=None):
    data = json.dumps(value).encode() if value is not None else None
    req = urllib.request.Request(ORIGIN + path, data=data, headers={
        "Content-Type": "application/json", "Origin": ORIGIN, "X-EpochGuard-Lab": "1", **(headers or {})})
    started = time.perf_counter()
    try:
        response = HTTP.open(req, timeout=15)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        data = response.read(256 * 1024 + 1)
        assert len(data) <= 256 * 1024
        assert response.headers["Cache-Control"] == "no-store"
        assert not any(k.lower().startswith("x-epochguard-internal") for k in response.headers)
        return response.status, json.loads(data), round((time.perf_counter() - started) * 1000, 3)


def verify(scenario, text, expected, outcome):
    status, result, elapsed = call("/api/demo/verify", {"scenario": scenario, "candidate": text})
    assert status == expected and result["status"] == expected and result["outcome"] == outcome
    assert result["evidence_mode"] == "fixture"
    if expected == 200:
        assert result["content"] == text and result["exact_content_match"] is True
    else:
        assert result["content"] is None and result["exact_content_match"] is False
        assert text not in json.dumps(result) and "PRIVATE_PROVIDER" not in json.dumps(result)
    assert "UNVERIFIED_METADATA" not in json.dumps(result)
    return {"scenario": scenario, "status": status, "outcome": result["outcome"], "elapsed_ms": elapsed}


def main():
    status, info, _ = call("/api/demo/info")
    assert status == 200 and info["receipt_protocol"] == "004g.receipt.v2"
    expected = ["ALLOW", "REJECT", "UNAVAILABLE", "INGRESS_REFUSED", "PROVIDER_ERROR"]
    rows = []
    for iteration in range(3):
        for entry, outcome in zip(info["scenarios"], expected):
            row = verify(entry["id"], entry["candidate"], entry["expected_status"], outcome)
            rows.append({"iteration": iteration + 1, **row})
    text = "\t" + info["scenarios"][0]["candidate"].replace("\n", "\r\n\t") + "\r\n"
    # Negative controls: the selected preset must never fabricate its expected
    # verdict when the supplied candidate actually says something different.
    rows.append(verify("contradicted", info["scenarios"][0]["candidate"], 200, "ALLOW"))
    rows.append(verify("supported", info["scenarios"][1]["candidate"], 403, "REJECT"))
    rows.append(verify("custom", text, 200, "ALLOW"))
    rows.append(verify("custom", text + "\nPRIVATE_PROVIDER_SENTINEL extra prose.", 503, "UNAVAILABLE"))
    rows.append(verify("custom", "PyPI reports requests version 2.34.2.", 200, "ALLOW"))
    rows.append(verify("custom", "Python.org currently lists Python 3.15.2 as its latest stable Windows release.\u00a0", 503, "UNAVAILABLE"))
    for path in ("/api/plugins", "/v1/verify/prose", "/test/control", "/api/proxy?url=http://gateway:8080", "/.env", "/assets/../index.html"):
        status, _, _ = call(path)
        assert status >= 400
    status, result, _ = call("/api/demo/verify", {"scenario":"custom","candidate":"x","url":"http://gateway:8080"})
    assert status == 400 and result["content"] is None
    status, _, _ = call("/api/demo/verify", {"scenario":"custom","candidate":"x"}, headers={"Origin":"http://untrusted.invalid"})
    assert status == 403
    print(json.dumps({"fixture":True,"actual_native_gateway":True,"checks":rows}, sort_keys=True))


if __name__ == "__main__":
    main()
