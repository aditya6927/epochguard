"""005E combined qualification. Default is seven disposable offline batches."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"tests"), str(ROOT/"services/verifier"), str(ROOT/"services/claim_analysis")]
from claim_analysis.schema import strict_json
from modelqualification.common import SafeParser, sha, write_new
from modelqualification.qualify import gateway as model_gateway
from combinedqualification.common import Runtime, Settings, Plan, BATCHES, PREFLIGHT_SECONDS, configuration_hash, live_guards, runtime_code_hash
from combinedqualification.report import assemble


def source_hash():
    paths = [*(ROOT/"tests/combinedqualification").glob("*.py"), *(ROOT/"tests/modelqualification").glob("*.py"),
        *(ROOT/"services/verifier/verifier").rglob("*.py"), ROOT/"services/claim_analysis/claim_analysis/schema.py",
        *(ROOT/"plugins/epochguard").glob("*.go"), *(ROOT/"internal/ingress").glob("*.go"),
        *(ROOT/"cmd/protected-ingress").glob("*.go"), *(ROOT/"tests/conformance").glob("*.json"),
        *(ROOT/"dev/combined").glob("*"), ROOT/"dev/model/start-gateway.sh", ROOT/"dev/prose/gateway.json",
        ROOT/"dev/live/gateway-control.json", ROOT/"dev/Dockerfile", ROOT/"dev/Dockerfile.model", ROOT/"dev/Dockerfile.combined",
        ROOT/"services/verifier/requirements.lock", *(ROOT/"services/verifier").glob("Dockerfile*"),
        *(ROOT/"cmd/provider-fixture").glob("*.go"), *(ROOT/"cmd/receipt-relay").glob("*.go"),
        ROOT/"plugins/epochguard/go.mod", ROOT/"plugins/epochguard/go.sum", ROOT/"go.mod",
        *ROOT.glob("compose.verify.005e*.yaml")]
    return sha(b"".join(p.relative_to(ROOT).as_posix().encode()+b"\0"+p.read_bytes().replace(b"\r\n",b"\n") for p in sorted(set(paths))))


def gateway(runtime):
    config = model_gateway(runtime.settings)
    plugin = config["plugins"][0]["config"]
    plugin.pop("qualification_diagnostics",None)
    plugin["combined_qualification_diagnostics"] = True
    plugin["test_only"] = not runtime.live
    plugin["verifier"].update(evidence_mode="live" if runtime.live else "fixture", timeout_ms=30000,
                              timeout_profile="004e-live" if runtime.live else "")
    return config


def private_secret(path):
    path = Path(path).resolve(strict=True)
    if path.is_relative_to(ROOT) or not path.is_file() or not 16<=path.stat().st_size<=258:
        raise ValueError("private runtime secret required outside repository")
    with path.open("rb") as stream:
        value = stream.read(259).decode("ascii").rstrip("\r\n")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}",value):
        raise ValueError("invalid runtime secret")
    return path


def environment(directory, *, live=False, model_secret=None, evidence_secret=None):
    env = {k:os.environ[k] for k in os.environ if not k.startswith("EPOCHGUARD_") and
           not any(s in k.upper() for s in ("KEY","TOKEN","SECRET"))}
    env.update(COMPOSE_DISABLE_ENV_FILE="1", COMPOSE_ENV_FILES=str(ROOT/"dev/lab.compose.env"), EPOCHGUARD_005E_RUN_DIR=str(directory))
    if live:
        live_guards()
        model, evidence = private_secret(model_secret), private_secret(evidence_secret)
        if model==evidence: raise ValueError("separate provider and source secret files required")
        env.update(EPOCHGUARD_005E_ALLOW_MODEL="1", EPOCHGUARD_005E_ALLOW_EVIDENCE="1",
                   EPOCHGUARD_005E_MODEL_SECRET_FILE=str(model), EPOCHGUARD_005E_EVIDENCE_SECRET_FILE=str(evidence))
    return env


def require_preflight(value, *, clock=lambda: datetime.now(timezone.utc)):
    if (value.get("schema_version")!="005e.suite.v1" or value.get("offline_passed") is not True or
        value.get("source_sha256")!=source_hash() or value.get("cleanup_completed") is not True or
        value.get("batches")!=list(BATCHES) or value.get("response_mode")!="strict-005ct" or
        value.get("policy")!="004g.v1/bounded-prose-v1" or value.get("receipt")!="004g.receipt.v2"):
        raise ValueError("complete matching offline suite required")
    created = datetime.fromisoformat(value["created_at"])
    if created.tzinfo is None or not -2 <= (clock()-created).total_seconds() <= PREFLIGHT_SECONDS:
        raise ValueError("stale offline suite")


class Ownership:
    def __init__(self, directory):
        self.path, self.token, self.acquired = directory/"owner.lock",uuid.uuid4().hex,False

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open("x",encoding="ascii") as stream: stream.write(self.token)
        self.acquired = True
        return self

    def __exit__(self, *args):
        if self.acquired and self.path.read_text(encoding="ascii")==self.token:
            self.path.unlink()


def execute_batch(runtime, directory, env, *, invoke=subprocess.run):
    directory.mkdir(parents=True,exist_ok=False)
    env = env | {"EPOCHGUARD_005E_RUN_DIR":str(directory)}
    write_new(directory/"runtime.json",runtime.model_dump(mode="json"))
    write_new(directory/"gateway.json",gateway(runtime))
    compose = ["docker","compose","--env-file","dev/lab.compose.env","-f","compose.verify.005e.yaml"]
    if runtime.live: compose += ["-f","compose.verify.005e.live.yaml"]
    stages, owns, stage, observed, result = [],False,"ownership",None,None
    source_started = False

    def run(label, command, *, structured=False, timeout=240, check=True):
        nonlocal stage
        stage = label
        print(runtime.batch+":"+label,flush=True)
        started = time.monotonic()
        try:
            value = invoke(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding="utf-8",timeout=timeout,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        except (OSError,subprocess.TimeoutExpired):
            stages.append({"stage":label,"exit_code":None,"elapsed_ms":round((time.monotonic()-started)*1000,3)})
            raise RuntimeError("stage unavailable") from None
        stages.append({"stage":label,"exit_code":value.returncode,"elapsed_ms":round((time.monotonic()-started)*1000,3)})
        if check and value.returncode: raise RuntimeError("stage failed")
        if structured:
            return strict_json(value.stdout)
        return value.stdout.strip() if check else value.returncode

    def role(label, who, action):
        return run(label,compose+["run","--rm","--no-deps","-T","qualification-"+who,
            "python","-m","combinedqualification.runner",action],structured=True,timeout=260)

    try:
        if run("ownership",["docker","ps","-aq","--filter","label=com.docker.compose.project=epochguard-005e"]):
            raise ValueError("existing combined project; no cleanup authority")
        owns = True
        # Sampling is explicit and precedes relay creation. No prompt/output is
        # persisted: the read-only plan contains validated observations only.
        run("source-start",compose+["up","-d","--wait","verifier"])
        source_started = True
        before = role("before-sampling","operator","source-report")
        if before.get("runtime_code_sha256")!=runtime_code_hash():
            raise ValueError("stale runtime image")
        if before["records"] or any(s["attempted"] for s in before["sources"].values()):
            raise ValueError("startup consumed evidence")
        sample = role("sampling","operator","sample")
        observed_source = role("after-sampling","operator","source-report")
        if sample["status"]!=200:
            if not runtime.live and runtime.batch=="sample-failure":
                if observed_source["sources"]["python"]["attempted"]!=1 or observed_source["sources"]["pypi"]["attempted"]!=0:
                    raise ValueError("failed sample accounting")
                result = {"expectations_met":True,"qualification_conclusive":False,"cases":[],"verifier":observed_source,
                          "transport":None,"failure":"expected_sampling_refusal"}
            else:
                raise ValueError("source sampling unavailable")
        else:
            if sample["preflight"]["fixture"] is runtime.live or sample["preflight"]["simulated_transports"] is runtime.live:
                raise ValueError("sample mode mismatch")
            plan = Plan.model_validate_json(json.dumps({"runtime_sha256":configuration_hash(runtime),
                "created_at":datetime.now(timezone.utc).isoformat(),"observations":sample["preflight"]["observations"]}))
            plan.versions(runtime)
            write_new(directory/"plan.json",plan.model_dump(mode="json"))
            write_new(directory/"preflight.json",sample["preflight"])
            run("start",compose+["up","-d","--wait","ingress","ingress-unsafe"])
            role("readiness","client","readiness")
            ready = role("after-readiness","operator","report")
            if any(ready[k].get("runtime_code_sha256")!=runtime_code_hash() for k in ("verifier","transport")):
                raise ValueError("stale runtime image")
            if ready["transport"]["attempted"] or ready["verifier"]["records"] or ready["verifier"]["sources"]!=observed_source["sources"]:
                raise ValueError("readiness consumed model or source budget")
            client = role("client","client","client")
            write_new(directory/"client.json",client)
            observed = role("observations","operator","report")
            # Retain known sanitized counters even if private native-stage
            # collection subsequently fails. Never rewrite an evidence file.
            write_new(directory/"observations.json",observed)
            raw = run("native-stages",compose+["exec","-T","gateway","cat","/tmp/epochguard-005cr.jsonl"])
            if len(raw)>65536: raise ValueError("stage bound")
            native = [strict_json(line) for line in raw.splitlines()]
            write_new(directory/"native-stages.json",native)
            stage = "validation"
            result = assemble(runtime,plan,client,observed,native)
            if not runtime.live and not result["expectations_met"]:
                raise ValueError("offline expectation failed")
    except Exception:
        failed = stage
        if source_started and observed is None:
            try:
                write_new(directory/"failure-observations.json",role("failure-observations","operator","source-report"))
            except Exception:
                pass
        write_new(directory/"failure.json",{"stage":failed,"failure":"qualification_failed_or_inconclusive"})
        raise RuntimeError("005E stage failed; sanitized evidence retained; no retry") from None
    finally:
        cleaned = False
        try:
            if owns:
                cleaned = run("cleanup",compose+["down","--volumes","--remove-orphans"],check=False)==0
        finally:
            write_new(directory/"cleanup.json",{"completed":cleaned,"owned_project":owns})
            write_new(directory/"stages.json",stages)
        if owns and not cleaned: raise RuntimeError("005E cleanup failed")
    result.update(schema_version="005e.gateway.v1",batch=runtime.batch,real_model=runtime.live,
        evidence="live" if runtime.live else "simulated",policy="004g.v1/bounded-prose-v1",receipt="004g.receipt.v2",
        source_revision=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        source_sha256=source_hash(),configuration_sha256=configuration_hash(runtime),
        model_configuration=runtime.settings.model_dump(),cleanup_completed=True,
        combined_live_qualification="COLLECTED; PENDING INDEPENDENT REVIEW" if runtime.live else "PENDING SEPARATE OPERATOR RUN")
    write_new(directory/"report.json",result)
    return result


def execute(args):
    if args.live:
        live_guards()  # Before secret reads, Docker, output or sampling.
        require_preflight(strict_json(Path(args.offline_preflight).read_bytes()))
        raw = Path(args.settings).read_bytes()
        strict_json(raw)
        settings = Settings.model_validate_json(raw)
    else:
        settings = Settings(model="gemini-offline-fixture",max_requests=6,input_usd_per_million=0.0,
            output_usd_per_million=0.0,max_request_usd=0.25,max_run_usd=1.0,
            python_request_usd=0.0,pypi_request_usd=0.0,max_source_run_usd=1.0)
    if args.live: Runtime(live=True,batch="standard",settings=settings)
    root = ROOT/"artifacts/005e"
    env = environment(root,live=args.live,model_secret=args.model_secret,evidence_secret=args.evidence_secret)
    with Ownership(root):
        images = {}
        for tag in ("epochguard-dev:002a","epochguard-combined:005e"):
            images[tag] = subprocess.check_output(["docker","image","inspect","--format","{{.Id}}",tag],
                cwd=ROOT,env=env,text=True,stderr=subprocess.PIPE).strip()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}",images[tag]):
                raise ValueError("immutable image identity unavailable")
        env.update(EPOCHGUARD_005E_NATIVE_IMAGE=images["epochguard-dev:002a"],
                   EPOCHGUARD_005E_COMBINED_IMAGE=images["epochguard-combined:005e"])
        if args.live and strict_json(Path(args.offline_preflight).read_bytes()).get("images")!=images:
            raise ValueError("offline image identity mismatch")
        directory = root/("live" if args.live else "offline")/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")+uuid.uuid4().hex[:8])
        reports = []
        for batch in (["standard"] if args.live else BATCHES):
            runtime = Runtime(live=args.live,batch=batch,settings=settings)
            reports.append(execute_batch(runtime,directory/batch,env))
        if any(r["source_sha256"]!=source_hash() for r in reports):
            raise ValueError("qualification sources changed during execution")
        report = {"schema_version":"005e.suite.v1","created_at":datetime.now(timezone.utc).isoformat(),
            "source_revision":reports[0]["source_revision"],"source_sha256":source_hash(),"batches":[r["batch"] for r in reports],
            "images":images,"runtime_code_sha256":runtime_code_hash(),
            "response_mode":"strict-005ct","policy":"004g.v1/bounded-prose-v1","receipt":"004g.receipt.v2",
            "real_model":args.live,"evidence":"live" if args.live else "simulated",
            "offline_passed":not args.live and all(r["expectations_met"] for r in reports),
            "cleanup_completed":all(r["cleanup_completed"] for r in reports),
            "reports":[r["batch"]+"/report.json" for r in reports],
            "combined_live_qualification":"COLLECTED; NOT APPROVED" if args.live else "PENDING SEPARATE OPERATOR RUN"}
        write_new(directory/"report.json",report)
        print("005E LIVE COLLECTED; INDEPENDENT REVIEW REQUIRED" if args.live else "005E OFFLINE PASSED; COMBINED LIVE QUALIFICATION PENDING")
        print(directory.relative_to(ROOT))


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--live",action="store_true")
    parser.add_argument("--settings",type=Path)
    parser.add_argument("--model-secret",type=Path)
    parser.add_argument("--evidence-secret",type=Path)
    parser.add_argument("--offline-preflight",type=Path)
    args = parser.parse_args()
    try:
        execute(args)
    except Exception:
        parser.exit(1,"005E unavailable; inspect sanitized artifacts. No automatic retry.\n")


if __name__=="__main__":
    main()
