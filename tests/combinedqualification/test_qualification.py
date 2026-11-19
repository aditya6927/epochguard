import asyncio
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import httpx
import pytest
from modelqualification.common import sha
from combinedqualification.common import Runtime,Settings,Plan,configuration_hash,scenarios,read_plan,read_runtime,live_guards,runtime_code_hash,BATCHES
from combinedqualification.sources import create_qualification_app,simulated_sources,Ledger,ReservedSource
from combinedqualification.relay import CombinedRelay
from combinedqualification import qualify as q
from verifier.bounded_prose.contract import Request
from combinedqualification.report import assemble


def runtime(batch="standard",**values):
    settings = dict(model="gemini-offline-fixture",max_requests=6,input_usd_per_million=0.0,output_usd_per_million=0.0,
        max_request_usd=0.25,max_run_usd=1.0,python_request_usd=0.0,pypi_request_usd=0.0,max_source_run_usd=1.0)
    return Runtime(live=False,batch=batch,settings=Settings(**(settings|values)))


async def prepared(batch="standard"):
    r = runtime(batch)
    app = create_qualification_app(r,*simulated_sources(r))
    sample = await app.state.pipeline.evidence_pipeline.preflight()
    plan = Plan.model_validate_json(json.dumps({"runtime_sha256":configuration_hash(r),"created_at":datetime.now(timezone.utc).isoformat(),"observations":sample["observations"]}))
    return r,app,plan


def native(relay,name):
    return json.dumps({"model":relay.settings.model,"contents":[{"role":"user","parts":[{"text":relay.prompts[name]}]}],
        "generationConfig":{"maxOutputTokens":relay.settings.output_tokens}}).encode()


def test_explicit_dual_authorization_before_docker_or_secret_access(monkeypatch,tmp_path):
    for enabled in ((),("EPOCHGUARD_005E_ALLOW_MODEL",),("EPOCHGUARD_005E_ALLOW_EVIDENCE",)):
        for name in enabled: monkeypatch.setenv(name,"1")
        with pytest.raises(ValueError): live_guards()
        with pytest.raises(ValueError): q.environment(tmp_path,live=True,model_secret="missing",evidence_secret="missing")
        for name in enabled: monkeypatch.delenv(name)
    monkeypatch.setenv("GEMINI_API_KEY","PRIVATE_UNUSED")
    monkeypatch.setenv("EPOCHGUARD_RUN_LIVE_004E","1")
    env = q.environment(tmp_path)
    assert "GEMINI_API_KEY" not in env and "EPOCHGUARD_RUN_LIVE_004E" not in env


@pytest.mark.parametrize("values",[{"response_mode":"unadapted"},{"max_source_run_usd":0.1,"python_request_usd":0.1},
    {"python_request_usd":float("nan")},{"pypi_request_usd":-1.0},{"output_tokens":True}])
def test_invalid_budgets_and_modes(values):
    with pytest.raises(ValueError): runtime(**values)


def test_live_scenario_and_transport_guards(monkeypatch):
    r,_,plan = asyncio.run(prepared())
    with pytest.raises(ValueError): Runtime(live=True,batch="faults",settings=r.settings)
    live = Runtime(live=True,batch="standard",settings=r.settings.model_copy(update={"max_requests":4}))
    with pytest.raises(ValueError): CombinedRelay(live,plan)
    monkeypatch.setenv("EPOCHGUARD_005E_ALLOW_MODEL","1")
    monkeypatch.setenv("EPOCHGUARD_005E_ALLOW_EVIDENCE","1")
    with pytest.raises(ValueError): CombinedRelay(live,plan,transport=httpx.MockTransport(lambda _:None))


def test_sampling_validates_versions_without_persisting_prompts(tmp_path):
    r,app,plan = asyncio.run(prepared())
    outputs,prompts = scenarios(plan,r)
    assert "3.88.7" in outputs["supported"] and "3.88.6" in outputs["older"]
    assert outputs["supported"] not in plan.model_dump_json() and "Return exactly" not in plan.model_dump_json()
    path = tmp_path/"plan.json"
    path.write_text(plan.model_dump_json())
    assert read_plan(r,path)==plan
    with pytest.raises(ValueError): read_plan(r,path,clock=lambda:plan.created_at+timedelta(seconds=301))
    with pytest.raises(ValueError): plan.versions(r.model_copy(update={"batch":"faults"}))
    row = app.state.pipeline.report()
    assert all(s["attempted"]==1 for s in row["sources"].values())
    assert [c["phase"] for c in row["source_budget"]["calls"]]==["preflight","preflight"]


@pytest.mark.parametrize("name",["file_neighbor","file_same_part","two_candidates","detached_signature","thinking","tool"])
def test_all_lossy_collisions_refused_before_conversion(name):
    r,_,plan = asyncio.run(prepared("envelopes"))
    relay = CombinedRelay(r,plan)
    response = asyncio.run(relay.generate(native(relay,name),"offline-only"))
    assert response.status_code==502 and relay.records[0]["adapter"]["validation"]=="REFUSED"
    assert "SYNTHETIC_PRIVATE" not in json.dumps(relay.report())


@pytest.mark.parametrize("batch,verdicts",[("standard",["SUPPORTED","CONTRADICTED","INSUFFICIENT","INSUFFICIENT"]),
    ("faults",["INSUFFICIENT"]*3),("identity",["INSUFFICIENT"]*2),("clock",["INSUFFICIENT"]*2),("drift",["CONTRADICTED"])])
def test_actual_existing_source_parsers_and_budgets(batch,verdicts):
    async def scenario():
        r,app,plan = await prepared(batch)
        outputs,_ = scenarios(plan,r)
        got = []
        for name,text in list(outputs.items())[:len(verdicts)]:
            result = await app.state.pipeline.verify(Request(request_id="offline_"+name,candidate=text,candidate_sha256=sha(text)))
            got.append(result.verification.verdict if result.verification else "INSUFFICIENT")
        assert got==verdicts
        report = app.state.pipeline.report()
        assert all(v["attempted"]<=3 for v in report["sources"].values())
        assert len(report["source_budget"]["calls"])==sum(v["attempted"] for v in report["sources"].values())
        assert all(row["claim_report"]["authorization"] is False for row in report["records"])
    asyncio.run(scenario())


def test_preflight_failure_and_one_shot_replay():
    async def scenario():
        r = runtime("sample-failure")
        app = create_qualification_app(r,*simulated_sources(r))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://offline") as client:
            assert (await client.get("/health")).status_code==200
            assert (await client.post("/qualification/preflight")).status_code==503
            assert (await client.post("/qualification/preflight")).status_code==503
        report = app.state.pipeline.report()
        assert report["sources"]["python"]["attempted"]==1 and report["sources"]["pypi"]["attempted"]==0
    asyncio.run(scenario())


def test_source_reservation_survives_cancellation_and_exhaustion():
    async def scenario():
        settings = runtime(python_request_usd=0.1,pypi_request_usd=0.1,max_source_run_usd=0.6).settings
        ledger = Ledger(settings)
        started = asyncio.Event()
        class Blocked:
            async def retrieve(self):
                started.set()
                await asyncio.Event().wait()
        source = ReservedSource(Blocked(),"python",ledger)
        task = asyncio.create_task(source.retrieve())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert float(ledger.reserved)==0.1
        ledger.reserve("python");ledger.reserve("python")
        with pytest.raises(ValueError): ledger.reserve("python")
        ledger.started -= 301
        with pytest.raises(ValueError): ledger.reserve("pypi")
    asyncio.run(scenario())


def test_provider_failure_does_not_retrieve_post_sample_evidence():
    r,app,plan = asyncio.run(prepared())
    relay = CombinedRelay(r,plan)
    before = app.state.pipeline.report()["sources"]
    response = asyncio.run(relay.generate(native(relay,"provider_error"),"offline-only"))
    assert response.status_code==400 and app.state.pipeline.report()["sources"]==before
    assert "adapter" not in relay.records[0]


def test_missing_stale_and_changed_offline_suite_refused(monkeypatch):
    monkeypatch.setattr(q,"source_hash",lambda:"a"*64)
    now = datetime.now(timezone.utc)
    good = {"schema_version":"005e.suite.v1","source_sha256":"a"*64,"offline_passed":True,"cleanup_completed":True,
        "batches":list(BATCHES),"response_mode":"strict-005ct","policy":"004g.v1/bounded-prose-v1","receipt":"004g.receipt.v2","created_at":now.isoformat()}
    q.require_preflight(good)
    for change in ({"source_sha256":"b"*64},{"offline_passed":False},{"batches":["standard"]},
                   {"cleanup_completed":False},{"created_at":(now-timedelta(days=2)).isoformat()}):
        with pytest.raises(ValueError): q.require_preflight(good|change)


def test_exclusive_ownership_and_foreign_lock_preserved(tmp_path):
    with q.Ownership(tmp_path):
        with pytest.raises(FileExistsError):
            with q.Ownership(tmp_path): pass
    assert not (tmp_path/"owner.lock").exists()
    (tmp_path/"owner.lock").write_text("foreign")
    with pytest.raises(FileExistsError):
        with q.Ownership(tmp_path): pass
    assert (tmp_path/"owner.lock").read_text()=="foreign"


def test_partial_start_cleanup_and_existing_project_nonownership(tmp_path):
    for existing in (False,True):
        commands = []
        def invoke(command,**kw):
            commands.append(command)
            if command[1:3]==["ps","-aq"]: return SimpleNamespace(returncode=0,stdout="foreign-container" if existing else "")
            if "up" in command: return SimpleNamespace(returncode=1,stdout="PRIVATE_UNTRUSTED_ERROR")
            return SimpleNamespace(returncode=0,stdout="")
        directory = tmp_path/str(existing)
        with pytest.raises(RuntimeError): q.execute_batch(runtime(),directory,q.environment(directory),invoke=invoke)
        assert any("down" in c for c in commands) is not existing
        assert "PRIVATE" not in "".join(p.read_text() for p in directory.glob("*.json"))


def test_reporting_failure_never_changes_verifier_result(monkeypatch):
    async def scenario():
        r,app,plan = await prepared()
        text = scenarios(plan,r)[0]["older"]
        def failed(*args,**kwargs): raise RuntimeError("PRIVATE_REPORT_FAILURE")
        monkeypatch.setattr("combinedqualification.sources.from_result",failed)
        result = await app.state.pipeline.verify(Request(request_id="report_failure",candidate=text,candidate_sha256=sha(text)))
        assert result.verification.verdict=="CONTRADICTED" and app.state.pipeline.reporting_failures==1
    asyncio.run(scenario())


def test_isolation_and_credential_boundaries():
    root = Path(__file__).resolve().parents[2]
    offline = (root/"compose.verify.005e.yaml").read_text()
    live = (root/"compose.verify.005e.live.yaml").read_text()
    assert "ports:" not in offline+live and "secrets:" not in offline and "internal: true" in offline
    assert "model-egress" not in offline and "evidence-egress" not in offline
    assert "EPOCHGUARD_005E_ALLOW_MODEL:?" in live and "EPOCHGUARD_005E_ALLOW_EVIDENCE:?" in live
    assert "max_retries" not in live
    config = q.gateway(runtime())["plugins"][0]["config"]
    assert config["combined_qualification_diagnostics"] is True and "qualification_diagnostics" not in config
    assert config["verifier"]["mode"]=="004g.v1" and config["attestation"]["protocol"]=="004g.receipt.v2"
    assert len(runtime_code_hash())==64


def test_live_entrypoint_stops_before_docker_without_both_authorizations(monkeypatch):
    def forbidden(*args,**kwargs): raise AssertionError("Docker or secret access before authorization")
    monkeypatch.setattr(q.subprocess,"check_output",forbidden)
    args = SimpleNamespace(live=True,offline_preflight=None,settings=None,model_secret=None,evidence_secret=None)
    with pytest.raises(ValueError): q.execute(args)


def test_report_cannot_replace_evidence_with_diagnostic_scores():
    async def scenario():
        r,app,plan = await prepared("drift")
        relay = CombinedRelay(r,plan)
        response = await relay.generate(native(relay,"source_changed"),"offline-only")
        text = json.loads(response.body)["candidates"][0]["content"]["parts"][0]["text"]
        result = await app.state.pipeline.verify(Request(request_id="report_only",candidate=text,candidate_sha256=sha(text)))
        assert result.verification.verdict=="CONTRADICTED"
        client = {"cases":[{"scenario":"source_changed","status":403,"outcome":"REJECT","answer_released":False,
            "approved_content_sha256":None,"request_sha256":"a"*64}]}
        observed = {"transport":relay.report(),"verifier":app.state.pipeline.report()}
        for claim in observed["verifier"]["records"][0]["claim_report"]["claims"]: claim["freshness_score"]=100
        stages = [{"request_sha256":"a"*64,"stages":["candidate_eligible","verifier_request_attempted","verifier_request_completed","evidence_policy_validation_refused"]}]
        report = assemble(r,plan,client,observed,stages)
        assert report["cases"][0]["outcome"]=="REJECT" and report["source_changed_since_sampling"] and not report["qualification_conclusive"]
        client["cases"][0].update(status=200,outcome="ALLOW",answer_released=True,approved_content_sha256=sha(text))
        with pytest.raises(ValueError): assemble(r,plan,client,observed,stages)
    asyncio.run(scenario())


def test_stage_collection_failure_retains_sanitized_observations(tmp_path):
    r,app,plan = asyncio.run(prepared())
    sampled = app.state.pipeline.report()
    empty = dict(sampled,records=[],sources={k:{"attempted":0} for k in sampled["sources"]})
    observed = {"transport":CombinedRelay(r,plan).report(),"verifier":sampled}
    reads = 0
    commands = []
    def invoke(command,**kwargs):
        nonlocal reads
        commands.append(command)
        if "cat" in command: return SimpleNamespace(returncode=1,stdout="PRIVATE_STAGE_FAILURE")
        action = command[-1]
        if action=="source-report":
            reads += 1
            value = empty if reads==1 else sampled
        elif action=="sample": value={"status":200,"preflight":{"fixture":True,"simulated_transports":True,"observations":[e.model_dump(mode="json") for e in plan.observations]}}
        elif action=="readiness": value={"ready":True}
        elif action=="report": value=observed
        elif action=="client": value={"cases":[]}
        else: return SimpleNamespace(returncode=0,stdout="")
        return SimpleNamespace(returncode=0,stdout=json.dumps(value))
    directory = tmp_path/"stage-failure"
    with pytest.raises(RuntimeError): q.execute_batch(r,directory,q.environment(directory),invoke=invoke)
    saved=json.loads((directory/"observations.json").read_text())
    assert saved["verifier"]["sources"]["python"]["attempted"]==1
    assert any("down" in command for command in commands)
    assert not (directory/"report.json").exists()
    assert "PRIVATE_STAGE_FAILURE" not in "".join(p.read_text() for p in directory.glob("*.json"))
