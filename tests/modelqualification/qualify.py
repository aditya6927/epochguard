"""Opt-in isolated native Gemini qualification. Default real calls: zero."""
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "services/claim_analysis")]
from modelqualification.common import OUTPUTS, Settings, SafeParser, read_settings, sha, write_new


def environment(live, directory, secret=None):
    # Do not inspect or reuse unrelated credential values.
    env = {k: os.environ[k] for k in os.environ if not k.startswith("EPOCHGUARD_") and
           not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET"))}
    env.update(COMPOSE_DISABLE_ENV_FILE="1", COMPOSE_ENV_FILES=str(ROOT / "dev/lab.compose.env"),
               EPOCHGUARD_005C_RUN_DIR=str(directory))
    if live:
        if os.getenv("EPOCHGUARD_RUN_MODEL_005C") != "1" or secret is None:
            raise ValueError("separate model authorization required")
        path = Path(secret).resolve(strict=True)
        if path.is_relative_to(ROOT) or path.stat().st_size > 258 or path.stat().st_size < 16:
            raise ValueError("private credential file required outside repository")
        with path.open("rb") as stream:
            key = stream.read(259).decode("ascii").rstrip("\r\n")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,256}", key):
            raise ValueError("invalid runtime credential")
        del key
        env.update(EPOCHGUARD_005C_SECRET_FILE=str(path), EPOCHGUARD_RUN_MODEL_005C="1")
    return env


def gateway(settings):
    config = json.loads((ROOT / "dev/prose/gateway.json").read_text())
    config["providers"]["gemini"] = {
        "network_config": {"base_url": "http://relay:9001/v1beta", "allow_private_network": True,
                           "max_retries": 0, "default_request_timeout_in_seconds": 20},
        "keys": [{"name": "005c-runtime", "value": "env.EPOCHGUARD_005C_KEY", "models": [settings.model], "weight": 1}]}
    return config


def validate(client, observation, live):
    transport = observation["transport"]
    verifier = observation["verifier"]
    if verifier["fixture"] is not True or verifier["simulated_transports"] is not True:
        raise ValueError("evidence mode changed")
    records, cases = transport["records"], client["cases"]
    required = list(OUTPUTS) + ([] if live else ["provider_error", "timeout"])
    if [r["scenario"] for r in records] != required or transport["real_provider"] is not live:
        raise ValueError("provider invocation accounting")
    if any(r["real_provider_invocation_attempted"] is not live for r in records) or transport["attempted"] != len(records) or sum(transport[k] for k in ("completed", "failed", "cancelled")) != len(records):
        raise ValueError("inconsistent invocation totals")
    if [c["scenario"] for c in cases] != required + ["missing_plugin", "controlled_provider_error"]:
        raise ValueError("case denominator")
    for case in cases:
        name = case["scenario"]
        observed = next((r for r in records if r["scenario"] == name), None)
        case["real_provider_invocation_attempted"] = bool(observed and observed["real_provider_invocation_attempted"])
        case["observed_model_matches_intention"] = observed["matches_intended_text"] if observed else None
        if name in OUTPUTS:
            # Noncompliance remains visible. A live safe refusal is collected,
            # never relabeled as the intended successful scenario.
            expected = {"supported": "ALLOW", "older": "REJECT", "unsupported": "UNAVAILABLE", "paraphrase": "UNAVAILABLE"}[name]
            case["intended_outcome_met"] = case["outcome"] == expected and observed["matches_intended_text"] is True
            if case["answer_released"] and case["approved_content_sha256"] != observed["candidate_sha256"]:
                raise ValueError("unexpected or altered release")
            checked = [r for r in observation["verifier"]["records"] if r["candidate_sha256"] == observed["candidate_sha256"]]
            if case["answer_released"] and not any(r["completed"] and r["verdict"] == "SUPPORTED" and r["coverage"] == "COMPLETE" for r in checked):
                raise ValueError("release without full evidence")
            if not live and not case["intended_outcome_met"]:
                raise ValueError("offline scenario failed")
        elif name == "missing_plugin":
            if case["outcome"] != "INGRESS_REFUSED":
                raise ValueError("missing plugin released")
        elif case["outcome"] != "PROVIDER_ERROR":
            raise ValueError("provider error distinction")
    return {"schema_version": "005c.gateway.v1", "provider": "native_gemini", "real_provider": live,
            "evidence": "simulated", "policy": "004g.v1/bounded-prose-v1", "receipt": "004g.receipt.v2",
            "cases": cases, "transport": transport,
            "qualification": "PENDING INDEPENDENT REVIEW" if live else "OFFLINE TRANSPORT ONLY",
            "real_model_qualification": "PENDING OPERATOR RUN" if not live else "COLLECTED; NOT APPROVED",
            "usage_scope": "reported subset at configured rates; unknown usage is null; not billing evidence"}


def source_hash():
    paths = [*sorted((ROOT / "tests/modelqualification").glob("*.py")), ROOT / "internal/ingress/ingress.go",
             ROOT / "cmd/protected-ingress/main.go", ROOT / "dev/model/start-gateway.sh", ROOT / "dev/prose/gateway.json",
             ROOT / "internal/ingress/model_test.go", ROOT / "compose.verify.005c.yaml", ROOT / "compose.verify.005c.live.yaml",
             ROOT / "compose.verify.005c.cleanup.yaml", ROOT / "dev/Dockerfile.model"]
    return sha(b"".join(p.relative_to(ROOT).as_posix().encode()+b"\0"+p.read_bytes().replace(b"\r\n", b"\n") for p in paths))


def execute(args):
    live = args.live
    settings = read_settings(args.settings) if live else Settings(model="gemini-offline-fixture", max_requests=6,
        input_usd_per_million=0.0, output_usd_per_million=0.0, max_request_usd=0.25, max_run_usd=1.0)
    settings.preflight(live)
    if live:
        preflight = json.loads(Path(args.offline_preflight).read_text())
        if preflight.get("source_sha256") != source_hash() or preflight.get("offline_passed") is not True:
            raise ValueError("matching offline preflight required")
    directory = ROOT / "artifacts/005c" / ("live" if live else "offline") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    env = environment(live, directory, args.secret_file)
    directory.mkdir(parents=True)
    write_new(directory / "settings.json", settings.model_dump())
    write_new(directory / "gateway.json", gateway(settings))
    compose = ["docker", "compose", "--env-file", "dev/lab.compose.env", "-f", "compose.verify.005c.yaml"]
    if live:
        compose += ["-f", "compose.verify.005c.live.yaml"]
    stages, owns, stage, started_stack = [], False, "ownership", False

    def run(label, command, structured=False, timeout=240):
        nonlocal stage
        stage = label
        print(label, flush=True)
        start = time.monotonic()
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            stages.append({"stage": label, "exit_code": None, "elapsed_ms": round((time.monotonic()-start)*1000, 3)})
            raise RuntimeError("stage unavailable") from None
        stages.append({"stage": label, "exit_code": result.returncode, "elapsed_ms": round((time.monotonic()-start)*1000, 3)})
        if result.returncode:
            raise RuntimeError("stage failed")
        return json.loads(result.stdout) if structured else result.stdout.strip()

    def role(label, who, action):
        return run(label, compose + ["run", "--rm", "--no-deps", "-T", "qualification-" + who,
                                    "python", "-m", "modelqualification.runner", action], True, 250)

    try:
        if run("ownership", ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=epochguard-005c"]):
            raise ValueError("existing qualification project; coordinate before cleanup")
        owns = True
        if args.build:
            for tag, file in (("epochguard-dev:002a", "dev/Dockerfile"), ("epochguard-verifier:004c", "services/verifier/Dockerfile.004c"),
                              ("epochguard-verifier:004e", "services/verifier/Dockerfile.004e"), ("epochguard-verifier:004g", "services/verifier/Dockerfile.004g"),
                              ("epochguard-verifier:004gl", "services/verifier/Dockerfile.004gl"), ("epochguard-model:005c", "dev/Dockerfile.model")):
                run("build-" + tag, ["docker", "buildx", "build", "--load", "-t", tag, "-f", file, "."], timeout=1800)
        run("start", compose + ["up", "-d", "--wait", "ingress", "ingress-unsafe"])
        started_stack = True
        role("readiness", "client", "readiness")
        before = role("before", "operator", "report")
        if before["transport"]["attempted"] or before["verifier"]["records"] or any(s["attempted"] for s in before["verifier"]["sources"].values()):
            raise ValueError("readiness used model or evidence")
        client = role("client", "client", "client")
        write_new(directory / "client.json", client)
        observed = role("observations", "operator", "report")
        write_new(directory / "observations.json", observed)
        stage = "validate"
        report = validate(client, observed, live)
        report.update(source_revision=run("revision", ["git", "rev-parse", "HEAD"]), source_sha256=source_hash(),
                      model_configuration=settings.model_dump(), offline_passed=not live)
    except Exception:
        failed_stage = stage
        if started_stack and not (directory / "observations.json").exists():
            try:
                write_new(directory / "observations.json", role("failure-observations", "operator", "report"))
            except Exception:
                pass
        write_new(directory / "failure.json", {"stage": failed_stage, "failure": "qualification_failed_or_inconclusive"})
        raise RuntimeError("005C failed; sanitized artifacts retained; no automatic retry") from None
    finally:
        if owns:
            try:
                run("cleanup", compose + ["down", "--volumes", "--remove-orphans"])
            finally:
                write_new(directory / "stages.json", stages)
        else:
            write_new(directory / "stages.json", stages)
    # A failed cleanup must never leave a successful offline admission record.
    report["cleanup_completed"] = True
    write_new(directory / "report.json", report)
    print("LIVE COLLECTED: independent review required" if live else "005C OFFLINE PASSED; PENDING OPERATOR RUN")
    print(directory.relative_to(ROOT))


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--offline-preflight", type=Path)
    args = parser.parse_args()
    try:
        execute(args)
    except Exception:
        parser.exit(1, "005C unavailable; inspect sanitized stage artifacts. No automatic retry.\n")


if __name__ == "__main__":
    main()
