"""004E operator orchestration. Default execution is entirely offline.

--live additionally requires EPOCHGUARD_RUN_LIVE_004E=1 and a runtime key file.
Never reads/prints the key or resolved Compose configuration. No retries.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--builder", default="epochguard-002a")
    args = parser.parse_args()
    print("Sources: Tavily Extract -> fixed Python.org Windows URL; PyPI -> fixed requests JSON URL.", flush=True)
    print("Live budget: at most 3 Tavily and 3 PyPI retrieval attempts: one preflight + two factual gateway requests. No retries, polling or Gemini.", flush=True)
    if args.live and (os.getenv("EPOCHGUARD_RUN_LIVE_004E") != "1" or not os.getenv("EPOCHGUARD_TAVILY_SECRET_HOST_FILE")):
        parser.exit(2, "LIVE QUALIFICATION PENDING: explicit operator opt-in and runtime credential file required\n")
    name = "live" if args.live else "offline"
    logs = ROOT / "artifacts/004e" / name
    logs.mkdir(parents=True, exist_ok=True)
    compose = ["docker", "compose", "-f", "compose.verify.004e.yaml" if args.live else "compose.verify.004e.offline.yaml"]
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run(label, command, *, data=None, check=True, structured=False, timeout=240):
        print(label, flush=True)
        result = subprocess.run(command, cwd=ROOT, input=data, text=True, encoding="utf-8",
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                                creationflags=hidden)
        (logs / (label + ".log")).write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
        if structured and result.stdout.strip():
            value = json.loads(result.stdout)
            (logs / (label + ".json")).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        else:
            value = None
        if check and result.returncode:
            raise RuntimeError(f"{label} failed; inspect artifacts/004e/{name}/{label}.log")
        return result.returncode, value

    def operator(label, action, **kwargs):
        return run(label, compose + ["run", "--rm", "--no-deps", "qualification-operator",
                   "python", "-m", "tests_live.runner", action], structured=True, **kwargs)

    report = None
    try:
        if args.build:
            run("native-build", ["docker", "buildx", "build", "--builder", args.builder, "--load", "-t", "epochguard-dev:002a", "-f", "dev/Dockerfile", "."], timeout=1800)
            run("python-base-build", ["docker", "buildx", "build", "--builder", args.builder, "--load", "-t", "epochguard-verifier:004c", "-f", "services/verifier/Dockerfile.004c", "."], timeout=600)
            run("python-live-build", ["docker", "build", "-t", "epochguard-verifier:004e", "-f", "services/verifier/Dockerfile.004e", "."], timeout=600)
        run("clean-start", compose + ["down", "--volumes", "--remove-orphans"])
        services = ["ingress", "ingress-unsafe"] + ([] if args.live else ["ingress-live-mode"])
        run("start", compose + ["up", "-d", "--wait"] + services, timeout=240)
        run("readiness", compose + ["run", "--rm", "--no-deps", "qualification-client", "python", "-m", "tests_live.runner", "readiness"], structured=True)
        _, before = operator("before-preflight", "report")
        if any(s["attempted"] for s in before["sources"].values()):
            raise RuntimeError("readiness consumed source budget")
        _, preflight = operator("preflight", "preflight")
        _, provider_before = operator("provider-before", "stats")
        result, cases = run("client", compose + ["run", "--rm", "--no-deps", "-T", "qualification-client"],
                            data=json.dumps(preflight), structured=True, check=False, timeout=280)
        _, report = operator("report", "report")
        _, provider_after = operator("provider-after", "stats")
        if not isinstance(cases, dict) or not isinstance(cases.get("cases"), list):
            raise RuntimeError("client did not produce a case report; operator observations preserved")
        if any(s["attempted"] > 3 for s in report["sources"].values()):
            raise RuntimeError("live budget exceeded")
        # Match verifier observations to each gateway candidate hash, keeping
        # source changes visible rather than rewriting preflight expectations.
        for case in cases["cases"]:
            matches = [r for r in report["records"] if r["candidate_sha256"] == case["candidate_sha256"]] if case["case"][:1] in {"A", "B", "C"} else []
            case["verifier_observations"] = matches
            case["provider_calls"] = provider_after.get(case["candidate_sha256"], 0) - provider_before.get(case["candidate_sha256"], 0)
            expected_calls = 2 if case["case"] in {"A-support", "E-no-plugin"} else 1
            # A and E deliberately share one candidate; report their combined
            # counter scope rather than inventing individual deltas.
            case["provider_count_scope"] = "combined A+E" if expected_calls == 2 else "this case"
            if case["provider_calls"] != expected_calls:
                raise RuntimeError("unexpected provider call count or fallback")
            if case["case"] in {"A-support", "B-contradiction"} and len(matches) != 1:
                raise RuntimeError("factual request has missing/ambiguous verifier observation")
            baseline = {"python-windows-latest-v1": preflight["observations"][0]["observed_version"],
                        "pypi-requests-reported-v1": preflight["observations"][1]["observed_version"]}
            case["source_changed_since_preflight"] = any(
                evidence["observed_version"] != baseline[claim["policy_id"]]
                for observation in matches for claim in observation.get("claims", []) for evidence in claim["evidence"])
            case["qualification_status"] = "EXPECTED_OUTCOME" if case["expectation_met"] else "INCONCLUSIVE_OR_FAILED"
            if case["case"] == "A-support" and case["status"] == 200 and (
                len(matches[0]["claims"]) != 2 or any(c["verdict"] != "SUPPORTED" for c in matches[0]["claims"])):
                raise RuntimeError("released answer lacks two supported observations")
        (logs / "measurements.json").write_text(json.dumps({"cases": cases["cases"], "sources": report["sources"],
            "count_scope": report["count_scope"], "fixture": report["fixture"]}, indent=2) + "\n", encoding="utf-8")
        if result:
            raise RuntimeError("factual expectation not met: qualification inconclusive/failed; do not repeat automatically")
        if any(s["attempted"] != 3 or s["completed"] != 3 for s in report["sources"].values()):
            raise RuntimeError("standard successful qualification did not have the expected bounded source calls")
        if not args.live:
            operator("simulated-source-faults", "simulated")
        print("LIVE RUN COLLECTED: independent result review required" if args.live else "004E offline qualification passed; LIVE QUALIFICATION PENDING", flush=True)
    finally:
        if report is None:
            try:
                operator("failure-report", "report", check=False)
            except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError):
                pass
        run("cleanup", compose + ["down", "--volumes", "--remove-orphans"], check=False)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as error:
        # All RuntimeErrors above are fixed text; never print arbitrary tool
        # exception strings (which may contain response bodies or environment).
        print("004E qualification failed; inspect the sanitized stage logs. No automatic retry.", file=sys.stderr)
        sys.exit(1)
