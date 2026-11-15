import asyncio
import copy
import json
from pathlib import Path
import subprocess

import httpx
import pytest

from verifier.bounded_prose.contract import Request, Result
from verifier.bounded_prose.qualification import live_app, qualification_app
from verifier.multiclaim.deployment import CANARY, ObservedPipeline
from verifier.multiclaim.demo import scenario
from verifier.policy import digest
from tests_live_g.simulated import fixture_app
from boundedproselive import qualify, report, runner

TEXT = "Python.org currently lists Python 3.88.7 as its latest stable Windows release.\nPyPI reports requests version 2.88.7."


def request(text=TEXT):
    return Request(request_id="test-004gl", candidate=text, candidate_sha256=digest(text))


def authorized(monkeypatch, tmp_path):
    path = tmp_path / "synthetic.key"
    path.write_text("synthetic-placeholder-not-a-live-key")
    for name, value in (("EPOCHGUARD_RUN_LIVE_004E", "1"), ("EPOCHGUARD_RUN_LIVE_004G", "1"),
                        ("EPOCHGUARD_004E_PROFILE", "live"), ("EPOCHGUARD_TAVILY_SECRET_FILE", str(path))):
        monkeypatch.setenv(name, value)
    return path


@pytest.mark.parametrize("fault", ["g-opt-in", "e-opt-in", "profile", "missing", "malformed", "oversized",
    "TAVILY_API_KEY", "EPOCHGUARD_TEST_MODE", "EPOCHGUARD_SOURCE_URL", "EPOCHGUARD_POLICY",
    "EPOCHGUARD_TIMEOUT_PROFILE", "EPOCHGUARD_PYPI_PACKAGE", "EPOCHGUARD_TEST_TAVILY_ENDPOINT"])
def test_live_configuration_refuses_without_reading_or_reflecting_private_values(monkeypatch, tmp_path, fault):
    path = authorized(monkeypatch, tmp_path)
    if fault == "g-opt-in": monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004G")
    elif fault == "e-opt-in": monkeypatch.delenv("EPOCHGUARD_RUN_LIVE_004E")
    elif fault == "profile": monkeypatch.setenv("EPOCHGUARD_004E_PROFILE", "other")
    elif fault == "missing": path.unlink()
    elif fault in {"malformed", "oversized"}: path.write_text("PRIVATE value" if fault == "malformed" else "x" * 300)
    else: monkeypatch.setenv(fault, "PRIVATE_CONFIGURATION_SENTINEL")
    with pytest.raises(ValueError) as error:
        live_app()
    assert "PRIVATE" not in str(error.value) and str(path) not in str(error.value)


def test_live_factory_reuses_real_retrievers_and_fixed_admission_without_calls(monkeypatch, tmp_path):
    authorized(monkeypatch, tmp_path)
    app = live_app()
    pipeline = app.state.pipeline.evidence_pipeline
    assert not pipeline.fixture and pipeline.max_requests == 1
    assert pipeline.work_seconds == 26 and pipeline.retrieval_seconds == 20.5
    assert pipeline.python.source.endpoint == "https://api.tavily.com/extract"
    assert pipeline.python.source.timeouts.retrieval_seconds == 20
    assert pipeline.pypi.source.timeout_seconds == 4 and pipeline.pypi.source.transport is None
    assert not pipeline.records and not app.state.pipeline.records
    assert pipeline.python.attempted == pipeline.pypi.attempted == 0
    paths = [route.path for route in app.routes]
    assert "/v1/verify/prose" in paths and "/test/control" not in paths
    assert "/v1/verify/multiclaim" not in paths


def test_budget_preflight_outer_binding_and_sanitized_observations(monkeypatch):
    async def run():
        monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1")
        app = fixture_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            for _ in range(20):
                canary = await app.state.pipeline.verify(request(CANARY))
                assert canary.verification is None
            assert not app.state.pipeline.records
            probe = (await client.post("/qualification/preflight")).json()
            report.preflight(probe, True)
            assert (await client.post("/qualification/preflight")).status_code == 503
            for text in (TEXT, TEXT.replace("3.88.7", "3.88.6"), TEXT):
                raw = await client.post("/v1/verify/prose", json=request(text).model_dump())
                assert raw.status_code == 200
                value = Result.model_validate_json(raw.content)
                assert value.candidate == text and value.candidate_sha256 == digest(text)
            value = (await client.get("/qualification/report")).json()
            value = report.observations(value, True)
            assert value["records"][0]["verdict"] == "SUPPORTED"
            assert value["records"][1]["verdict"] == "CONTRADICTED"
            assert value["records"][2]["verdict"] == "INSUFFICIENT"
            assert all(s["attempted"] == s["completed"] == 3 for s in value["sources"].values())
            assert all(len(s["calls"]) == 3 for s in value["sources"].values())
            assert TEXT not in json.dumps(value) and "raw_content" not in json.dumps(value)
            assert value["records"][0]["candidate_sha256"] != value["records"][0]["canonical_sha256"]
    asyncio.run(run())


@pytest.mark.parametrize("fault", ["timeout", "ambiguous", "pypi-failure", "wrong-mode"])
def test_simulated_faults_never_authorize_and_do_not_retry(monkeypatch, fault):
    async def run():
        monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1")
        app = fixture_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            await client.post("/test/control", json={"fault": fault})
            value = Result.model_validate_json((await client.post("/v1/verify/prose", json=request().model_dump())).content)
            assert value.verification.verdict == "INSUFFICIENT"
            counts = report.observations((await client.get("/qualification/report")).json(), True)["sources"]
            assert all(s["attempted"] == 1 for s in counts.values())
    asyncio.run(run())


def test_cancellation_timeout_and_recovery_release_shared_slot():
    async def run():
        class Slow:
            async def retrieve(self): await asyncio.sleep(10)
        original, _ = scenario("A")
        evidence = ObservedPipeline(Slow(), list(original.sources.values())[1])
        pipeline = qualification_app(evidence).state.pipeline
        task = asyncio.create_task(pipeline.verify(request()))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert evidence._active == 0
        evidence.work_seconds = .02
        result = await pipeline.verify(request())
        assert result.verification.verdict == "INSUFFICIENT" and evidence._active == 0
        assert evidence.python.attempted == 2 and evidence.python.completed == 0
        assert "cancelled" in {c.get("failure") for c in evidence.python.calls}
    asyncio.run(run())


def test_host_live_gate_precedes_any_docker_invocation(monkeypatch):
    calls = []
    with pytest.raises(ValueError):
        qualify.execute(live=True, invoke=lambda *a, **k: calls.append(a))
    assert not calls
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004G", "1")
    with pytest.raises(ValueError): qualify.runtime_environment(True)
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004E", "1")
    with pytest.raises(ValueError): qualify.runtime_environment(True)
    monkeypatch.setenv("EPOCHGUARD_TAVILY_SECRET_HOST_FILE", "UNREAD_EXISTING_PRIVATE_PATH")
    env = qualify.runtime_environment(True)
    assert env["EPOCHGUARD_TAVILY_SECRET_HOST_FILE"] == "UNREAD_EXISTING_PRIVATE_PATH"
    assert "EPOCHGUARD_TAVILY_SECRET_HOST_FILE" not in qualify.runtime_environment(False)
    monkeypatch.setenv("EPOCHGUARD_POLICY", "untrusted")
    with pytest.raises(ValueError): qualify.runtime_environment(True)


@pytest.mark.parametrize("failure", ["start", "preflight", "timeout", "cleanup"])
def test_driver_cleans_failed_runs_and_saves_no_raw_subprocess_output(monkeypatch, tmp_path, failure):
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    calls = []
    def invoke(command, **kwargs):
        calls.append(command)
        if command[0] == "git": return subprocess.CompletedProcess(command, 0, "a" * 40, "")
        if failure == "timeout" and "up" in command:
            raise subprocess.TimeoutExpired(command, 1, output="PRIVATE_SUBPROCESS_VALUE")
        if "readiness" in command:
            return subprocess.CompletedProcess(command, 0, '{"readiness_status":200,"source_health_claimed":false}', "")
        # For later-stage failures, stop at a malformed private observation.
        failed = (failure == "start" and "up" in command) or (failure == "cleanup" and command[-3:] == ["down", "--volumes", "--remove-orphans"])
        return subprocess.CompletedProcess(command, 1 if failed else 0, "PRIVATE_SUBPROCESS_VALUE", "PRIVATE_SUBPROCESS_VALUE")
    with pytest.raises(RuntimeError): qualify.execute(invoke=invoke)
    assert calls[-1][-3:] == ["down", "--volumes", "--remove-orphans"]
    files = list(tmp_path.rglob("*.json"))
    assert files and all("PRIVATE_SUBPROCESS_VALUE" not in p.read_text() for p in files)


def test_packaged_profiles_keep_v2_limits_isolation_and_credentials():
    root = next((p for p in Path(__file__).resolve().parents if (p / "compose.verify.004gl.yaml").exists()), Path("/app/security"))
    live = (root / "compose.verify.004gl.yaml").read_text()
    offline = (root / "compose.verify.004gl.offline.yaml").read_text()
    config = root / "dev/prose-live/gateway.json"
    if not config.exists(): config = root / "gateway-live.json"
    value = json.loads(config.read_text())["plugins"][0]
    assert value["config"]["attestation"]["protocol"] == "004g.receipt.v2"
    assert value["config"]["verifier"] == {"url":"http://verifier:8000/v1/verify/prose", "timeout_ms":30000,
                                            "mode":"004g.v1", "evidence_mode":"live", "timeout_profile":"004e-live"}
    for profile in (live, offline):
        assert "ports:" not in profile and "--limit-concurrency\", \"32" in profile
        assert "--no-access-log" in profile and "internal: true" in profile
        assert "004g-live" in profile and "semantic_cache" not in profile
    assert live.count("secrets: [tavily_key]") == 1
    assert "EPOCHGUARD_RUN_LIVE_004G:?" in live and "EPOCHGUARD_RUN_LIVE_004E:?" in live
    assert "evidence-egress" not in offline and "secrets:" not in offline
    assert "EPOCHGUARD_TEST_MODE" in offline and "qualification:live_app" not in offline


@pytest.mark.parametrize("payload", ['{"a":1,"a":2}', '{"x":NaN}', 'x' * (256 * 1024 + 1)])
def test_host_rejects_malformed_observation_json(payload):
    with pytest.raises(ValueError): qualify.strict_json(payload)


def test_runner_rejects_provider_metadata_and_preserves_exact_content(monkeypatch):
    def response(*args):
        text = args[-1]["messages"][0]["content"]
        return {"status":200}, {"object":"chat.completion", "choices":[{"index":0,"finish_reason":"stop",
            "message":{"role":"assistant","content":text}}], "id":"UNVERIFIED_PROVIDER_SENTINEL"}
    monkeypatch.setattr(runner, "call", response)
    with pytest.raises(ValueError): runner.infer("A-support", TEXT, "user", "ingress", 200)


def sample(monkeypatch, *, changed=False):
    async def collect():
        monkeypatch.setenv("EPOCHGUARD_TEST_MODE", "1")
        app = fixture_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            probe = (await client.post("/qualification/preflight")).json()
            if changed:
                await client.post("/test/control", json={"fault": "source-change"})
            cases = runner.candidates(probe)
            for name, text, *_ in cases[:3]:
                await app.state.pipeline.verify(request(text))
            observed = app.state.pipeline.report()
        return probe, observed, cases
    probe, observed, cases = asyncio.run(collect())
    rows, counts = [], {}
    for name, text, role, host, expected in cases:
        def call(*args):
            body = {"object":"chat.completion", "choices":[{"index":0,"finish_reason":"stop",
                    "message":{"role":"assistant","content":text}}]} if expected == 200 else {"error":
                    {"type":"epochguard_ingress_error"} if name == "D-no-plugin" else
                    {"type":"invalid_request_error","code":"epochguard_provider_error","message":"Provider request failed."}
                    if name == "E-provider-error" else {"type":"epochguard_policy_error"}}
            return {"status":expected, "started_at":probe["observations"][0]["observed_at"],
                    "finished_at":probe["observations"][0]["observed_at"], "elapsed_ms":1.2,
                    "first_byte_ms":1.0, "request_sha256":"f"*64}, body
        monkeypatch.setattr(runner, "call", call)
        rows.append(runner.infer(name, text, role, host, expected))
        counts[digest(text)] = 1
    return probe, observed, {"cases": rows}, {}, counts


def test_report_success_preserves_measurement_scope_and_source_change_is_inconclusive(monkeypatch, tmp_path):
    values = sample(monkeypatch)
    result = report.assemble(*values, live=False, revision="a"*40)
    assert result["expectations_met"] and result["simulated_transports"]
    assert result["live_qualification_pending"] and result["receipt_protocol"] == "004g.receipt.v2"
    assert all(c["provider_calls"] == 1 for c in result["cases"])
    # Change only the validated observed version, preserving the evidence identity
    # (which binds content hash, not the parsed numeric interpretation).
    modified = copy.deepcopy(values)
    modified[1]["records"][0]["claims"][0]["evidence"][0]["observed_version"] = "3.88.8"
    result = report.assemble(*modified, live=False, revision="a"*40)
    assert not result["expectations_met"] and result["status"] == "INCONCLUSIVE_OR_FAILED"
    assert result["cases"][0]["failure_reason"] == "source_changed_since_preflight"

    # Exercise orchestration success and cleanup without a daemon or any sources.
    monkeypatch.setattr(qualify, "ROOT", tmp_path)
    probe, observed, clients, before, after = values
    calls = []
    def invoke(command, **kwargs):
        calls.append(command)
        if command[0] == "git": return subprocess.CompletedProcess(command, 0, "a"*40, "")
        action = command[-1]
        output = {"readiness": {"readiness_status":200,"source_health_claimed":False},
                  "preflight": probe, "client": clients, "metadata": {"metadata_sentinel_enabled":True},
                  "fixture-boundary": {"fixture_evidence_refused_in_live_mode":True}}.get(action, {})
        if action == "report":
            output = observed if any(c[-1] == "client" for c in calls) else {**observed, "records":[], "sources":{
                n:{"attempted":0,"completed":0,"calls":[]} for n in ("python","pypi")}}
        if action == "stats": output = after if any(c[-1] == "client" for c in calls) else before
        return subprocess.CompletedProcess(command, 0, json.dumps(output), "PRIVATE_DOCKER_STDERR")
    directory = qualify.execute(invoke=invoke)
    assert json.loads((directory/"cleanup.json").read_text()) == {"completed":True}
    assert calls[-1][-3:] == ["down","--volumes","--remove-orphans"]
    assert all("PRIVATE_DOCKER_STDERR" not in p.read_text() for p in directory.glob("*.json"))


@pytest.mark.parametrize("fault", ["extra", "body", "wrong-policy", "hash", "mode", "calls", "provider", "metadata", "downgrade"])
def test_reports_reject_raw_fields_bad_bindings_and_forged_observations(monkeypatch, fault):
    values = list(copy.deepcopy(sample(monkeypatch)))
    if fault == "extra": values[1]["PRIVATE_SECRET"] = "PRIVATE_VALUE"
    elif fault == "body": values[0]["observations"][0]["raw_content"] = "PRIVATE_BODY"
    elif fault == "wrong-policy": values[1]["records"][0]["claims"][0]["policy_id"] = "untrusted"
    elif fault == "hash": values[0]["observations"][0]["evidence_id"] = "0"*64
    elif fault == "mode": values[0]["observations"][0]["retrieval_mode"] = "tavily_live"
    elif fault == "calls": values[1]["sources"]["python"]["attempted"] = 4
    elif fault == "provider": values[4][values[2]["cases"][1]["candidate_sha256"]] = 2
    elif fault == "metadata": values[2]["cases"][0]["model"] = "PRIVATE_PROVIDER_TEXT"
    else: values[2]["cases"][0]["receipt_validation"] = "004d.v1"
    with pytest.raises(ValueError) as error:
        report.assemble(*values, live=False, revision="a"*40)
    assert "PRIVATE" not in str(error.value)


@pytest.mark.parametrize("fault", ["slow-body", "oversized", "metadata-header"])
def test_client_wall_deadline_response_bound_and_header_isolation(monkeypatch, fault):
    original_client, original_timeout = httpx.AsyncClient, asyncio.timeout
    closed, calls = [], []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"{"
            await asyncio.sleep(1)
            yield b"}"
        async def aclose(self): closed.append(True)
    async def transport(request):
        calls.append(str(request.url))
        if fault == "slow-body": return httpx.Response(200, stream=Body())
        if fault == "oversized": return httpx.Response(200, content=b"x" * (256*1024+1))
        return httpx.Response(200, json={"ready":True}, headers={"X-Provider-Metadata":"UNVERIFIED_METADATA_004GS"})
    def client(**kwargs):
        assert kwargs == {"timeout":52,"trust_env":False,"follow_redirects":False}
        return original_client(transport=httpx.MockTransport(transport), **kwargs)
    monkeypatch.setattr(runner.httpx, "AsyncClient", client)
    monkeypatch.setattr(runner.asyncio, "timeout", lambda seconds: original_timeout(.02))
    with pytest.raises((ValueError, TimeoutError)):
        runner.call("ingress", 8082, "GET", "/ready")
    assert len(calls) == 1
    if fault == "slow-body": assert closed == [True]
