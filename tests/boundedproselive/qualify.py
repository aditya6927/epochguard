"""Isolated 004G-L orchestration. Offline by default; no live retries."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boundedproselive.report import assemble, observations, preflight

ROOT = Path(__file__).resolve().parents[2]


def runtime_environment(live):
    # Do not access values of inherited source/model credentials. Only the
    # explicitly selected runtime file path goes to live Compose interpolation.
    env = {k: os.environ[k] for k in os.environ
           if not k.startswith("EPOCHGUARD_") and not any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET"))}
    if live:
        if any(os.getenv(n) != "1" for n in ("EPOCHGUARD_RUN_LIVE_004E", "EPOCHGUARD_RUN_LIVE_004G")):
            raise ValueError("both live opt-ins required")
        path = os.getenv("EPOCHGUARD_TAVILY_SECRET_HOST_FILE")
        if not path:
            raise ValueError("runtime secret file path required")
        if any(k.startswith("EPOCHGUARD_") and any(part in k for part in
               ("TIMEOUT", "POLICY", "SOURCE", "ENDPOINT", "PACKAGE", "_URL")) for k in os.environ):
            raise ValueError("live overrides forbidden")
        env.update(EPOCHGUARD_RUN_LIVE_004E="1", EPOCHGUARD_RUN_LIVE_004G="1",
                   EPOCHGUARD_TAVILY_SECRET_HOST_FILE=path)
    return env


def strict_json(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate observation field")
            value[key] = item
        return value
    def invalid(_):
        raise ValueError("nonfinite observation")
    if len(data) > 256 * 1024:
        raise ValueError("observation limit")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def execute(*, live=False, build=False, builder="epochguard-002a", invoke=subprocess.run):
    env = runtime_environment(live)  # fail before Docker/output when not opted in
    revision = invoke(["git", "rev-parse", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE, text=True, timeout=10).stdout.strip()
    name = "live" if live else "offline"
    directory = ROOT / "artifacts/004gl" / name / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    compose = ["docker", "compose", "-f", "compose.verify.004gl.yaml" if live else "compose.verify.004gl.offline.yaml"]
    stages, report, stage = [], None, "initialization"
    started_stack, observed = False, None
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def save(name, value):
        (directory / (name + ".json")).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    def run(label, command, *, data=None, check=True, structured=False, timeout=240):
        nonlocal stage
        stage = label
        print(label, flush=True)
        started = time.monotonic()
        try:
            result = invoke(command, cwd=ROOT, env=env, input=data, text=True, encoding="utf-8",
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, creationflags=hidden)
        except (OSError, subprocess.TimeoutExpired):
            stages.append({"stage": label, "exit_code": None, "elapsed_ms": round((time.monotonic() - started) * 1000, 3)})
            raise RuntimeError("qualification stage unavailable") from None
        stages.append({"stage": label, "exit_code": result.returncode,
                       "elapsed_ms": round((time.monotonic() - started) * 1000, 3)})
        save("stages", stages)
        # Never save arbitrary Docker stdout/stderr, service logs or environments.
        if check and result.returncode:
            raise RuntimeError("qualification stage failed")
        return strict_json(result.stdout) if structured else result.returncode

    def role(label, who, action, **kwargs):
        return run(label, compose + ["run", "--rm", "--no-deps", "-T", "qualification-" + who,
                   "python", "-m", "boundedproselive.runner", action], structured=True, **kwargs)

    try:
        if build:
            for tag, file in (("epochguard-dev:002a", "dev/Dockerfile"),
                              ("epochguard-verifier:004c", "services/verifier/Dockerfile.004c"),
                              ("epochguard-verifier:004e", "services/verifier/Dockerfile.004e"),
                              ("epochguard-verifier:004g", "services/verifier/Dockerfile.004g"),
                              ("epochguard-verifier:004gl", "services/verifier/Dockerfile.004gl")):
                command = ["docker", "buildx", "build", "--builder", builder, "--load"] if tag.endswith((":002a", ":004c")) else ["docker", "build"]
                run("build-" + tag.split(":")[1], command + ["-t", tag, "-f", file, "."], timeout=1800)
        run("clean-start", compose + ["down", "--volumes", "--remove-orphans"])
        run("start", compose + ["up", "-d", "--wait", "ingress", "ingress-unsafe"] + ([] if live else ["ingress-live-mode"]))
        started_stack = True
        role("readiness", "client", "readiness")
        initial = observations(role("before-preflight", "operator", "report"), not live)
        if any(s["attempted"] for s in initial["sources"].values()) or initial["records"]:
            raise RuntimeError("readiness consumed source budget")
        probe = preflight(role("preflight", "operator", "preflight"), not live)
        save("preflight", probe)
        role("metadata-sentinel", "operator", "metadata")
        before = role("provider-before", "operator", "stats")
        clients = role("client", "client", "client", data=json.dumps(probe), check=False, timeout=280)
        observed = observations(role("report", "operator", "report"), not live)
        save("observations", observed)
        after = role("provider-after", "operator", "stats")
        stage = "validate-measurements"
        report = assemble(probe, observed, clients, before, after, live=live, revision=revision)
        inputs = hashlib.sha256()
        for name in ("tests/boundedproselive/qualify.py", "tests/boundedproselive/runner.py", "tests/boundedproselive/report.py",
                     "services/verifier/verifier/bounded_prose/qualification.py", "dev/prose-live/gateway.json",
                     "compose.verify.004gl.yaml", "compose.verify.004gl.offline.yaml"):
            path = ROOT / name
            if path.exists():  # test orchestration uses a temporary, empty root
                inputs.update(name.encode() + b"\0" + path.read_bytes())
        report["harness_sha256"] = inputs.hexdigest()
        save("measurements", report)
        if not report["expectations_met"]:
            raise RuntimeError("qualification inconclusive or failed")
        if not live:
            boundary = role("fixture-boundary", "operator", "fixture-boundary")
            if boundary != {"fixture_evidence_refused_in_live_mode": True}:
                raise RuntimeError("source-mode boundary failed")
            save("fixture-boundary", boundary)
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        failed_stage = stage
        if started_stack and observed is None:
            try:
                observed = observations(role("failure-observations", "operator", "report"), not live)
                save("observations", observed)
            except (RuntimeError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
                pass
        save("failure", {"stage": failed_stage, "failure": "qualification_inconclusive_or_failed", "live_qualification_pending": True})
        raise RuntimeError("qualification failed; sanitized failure category saved") from None
    finally:
        cleaned = None
        try:
            cleaned = run("cleanup", compose + ["down", "--volumes", "--remove-orphans"], check=False)
        finally:
            save("cleanup", {"completed": cleaned == 0})
        if cleaned:
            raise RuntimeError("cleanup failed; manual project cleanup required")
    print("LIVE RUN COLLECTED: independent review required" if live else "004G-L offline qualification passed", flush=True)
    print("004G LIVE QUALIFICATION PENDING", flush=True)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--builder", default="epochguard-002a")
    args = parser.parse_args()
    try:
        print(execute(live=args.live, build=args.build, builder=args.builder).relative_to(ROOT))
    except (RuntimeError, ValueError, OSError):
        parser.exit(1, "004G-L failed; raw details withheld. No automatic retry.\n")


if __name__ == "__main__":
    main()
