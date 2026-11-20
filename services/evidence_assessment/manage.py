"""Isolated local Explorer lifecycle; standard library only, offline by default."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "epochguard-005i"
BASE = ["docker", "compose", "--env-file", "dev/lab.compose.env", "--project-name", PROJECT]
OFFLINE = BASE + ["-f", "compose.explorer.yaml"]
CLEANUP = BASE + ["-f", "compose.explorer.cleanup.yaml"]
ORIGIN = "http://127.0.0.1:8791"
FLAGS = ("EPOCHGUARD_005I_ALLOW_GEMINI", "EPOCHGUARD_005I_ALLOW_TAVILY")
FILES = ("EPOCHGUARD_005I_SETTINGS_HOST", "EPOCHGUARD_005I_GEMINI_SECRET_HOST", "EPOCHGUARD_005I_TAVILY_SECRET_HOST")


class Failure(RuntimeError):
    """Printable fixed stage only; never subprocess output or credential paths."""


def environment(live=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EPOCHGUARD_", "COMPOSE_", "GEMINI_", "TAVILY_"))
           and not any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET"))}
    env["COMPOSE_DISABLE_ENV_FILE"] = "1"
    if live:
        if any(os.getenv(k) != "1" for k in FLAGS):
            raise Failure("separate Gemini and Tavily authorization required")
        paths = []
        try:
            for key in FILES:
                path = Path(os.environ[key]).resolve(strict=True)
                if not path.is_file() or path.is_relative_to(ROOT) or path.stat().st_size > 8192:
                    raise ValueError()
                if os.name != "nt" and path.stat().st_mode & 0o077:
                    raise ValueError()
                paths.append(path)
            if len(set(paths)) != 3:
                raise ValueError()
        except (ValueError, OSError, KeyError):
            raise Failure("three distinct private files outside repository required; restrict file permissions") from None
        env.update(dict(zip(FILES, map(str, paths))))
        env.update({k: "1" for k in FLAGS})
    return env


def run(command, env, timeout=240):
    try:
        value = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        raise Failure("Docker command unavailable or exceeded deadline") from None
    if value.returncode:
        raise Failure("Docker stage failed; inspect the documented command privately")
    return value.stdout


def resources(env):
    result = {}
    for kind, command in (("containers", ["ps", "-aq"]), ("networks", ["network", "ls", "-q"]), ("volumes", ["volume", "ls", "-q"])):
        result[kind] = run(["docker"] + command + ["--filter", "label=com.docker.compose.project=" + PROJECT], env).decode().split()
    return result


def cleanup(env):
    run(CLEANUP + ["down", "--volumes", "--remove-orphans"], env)
    result = resources(env)
    if any(result.values()):
        raise Failure("cleanup incomplete; project resources remain")
    return result


def smoke():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    rows = []
    cases = [("Trump is Japan's prime minister.", "CONTRADICTED"),
             ("The chemical symbol for gold is Au.", "SUPPORTED"),
             ("The number of unrecorded birds alive yesterday was exactly 99.", "INSUFFICIENT_EVIDENCE")]
    for claim, expected in cases:
        req = urllib.request.Request(ORIGIN + "/api/assess", data=json.dumps({"claim": claim}).encode(),
            headers={"Content-Type": "application/json", "Origin": ORIGIN, "X-EpochGuard-Explorer": "1"})
        with opener.open(req, timeout=45) as response:
            value = json.load(response)
            assert response.status == 200 and response.headers["Cache-Control"] == "no-store"
        assert value["claim"] == claim and value["assessment"] == expected
        assert value["mode"] == "experimental-evidence" and value["authorization"] is False and value["evidence_mode"] == "simulated"
        assert set(value["citation_ids"]) <= {s["id"] for s in value["sources"]}
        if expected != "INSUFFICIENT_EVIDENCE": assert len(value["citation_ids"]) >= 2
        rows.append({"claim_sha256": hashlib.sha256(claim.encode()).hexdigest(), "assessment": value["assessment"],
                     "sources": len(value["sources"]), "citation_ids": value["citation_ids"], "authorization": False})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "down", "test"))
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--live", action="store_true", help="up only; requires separate explicit authorizations and private files")
    args = parser.parse_args()
    if args.live and args.action != "up": parser.error("--live is available only for up")
    try:
        env = environment(args.live)  # Authorization and file checks precede Docker.
        if args.action == "down":
            cleanup(env)
            print("Explorer stopped; project containers, networks and volumes absent. Private files retained.")
            return
        directory = ROOT / "artifacts/005i"
        directory.mkdir(parents=True, exist_ok=True)
        lock = directory / "lifecycle.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise Failure("another lifecycle invocation owns this project; inspect lifecycle.lock") from None
        os.close(fd)
        owned = False
        report = {"schema_version": "005i.http-smoke.v1", "simulated": not args.live}
        target = OFFLINE + (["-f", "compose.explorer.live.yaml"] if args.live else [])
        try:
            if any(resources(env).values()):
                raise Failure("existing project resources found; no existing stack changed; use down explicitly")
            owned = True
            if args.build:
                print("Building isolated Explorer image (public dependencies only)", flush=True)
                run(OFFLINE + ["build", "explorer"], env, timeout=1800)
            run(target + ["up", "-d", "--wait", "--wait-timeout", "120", "--no-build", "explorer"], env)
            if args.action == "test":
                report["cases"] = smoke()
                report["image"] = json.loads(run(["docker", "image", "inspect", "epochguard-explorer:005i", "--format", "{{json .Id}}"], env))
                report["revision"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
                report["scope"] = "Actual local HTTP service; simulated provider transports; not factual accuracy."
            else:
                print(ORIGIN + " | AI-assisted assessment; authorization=false | " + ("LIVE" if args.live else "SIMULATED"))
        finally:
            try:
                if owned and (args.action == "test" or sys.exc_info()[0] is not None):
                    report["cleanup"] = cleanup(env)
                    if args.action == "test":
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                        (directory / (stamp + "-http-smoke.json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            finally:
                lock.unlink()
        if args.action == "test": print("3/3 actual offline HTTP cases passed; cleanup verified.")
    except Failure as error:
        print("Explorer lifecycle failed: " + str(error) + ". No raw diagnostics emitted.", file=sys.stderr)
        raise SystemExit(1) from None
    except (AssertionError, OSError, ValueError):
        # A lifecycle failure may contain OS/provider details. Print no exception text.
        print("Explorer lifecycle failed; inspect prerequisites, private configuration and project ownership locally. No raw diagnostics emitted.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__": main()
