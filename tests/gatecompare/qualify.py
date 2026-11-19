"""Run only the private, offline 005F comparison. Requires Docker and Python 3.12."""
import argparse
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
sys.path.insert(0, str(ROOT / "tests"))
from gatecompare.benchmark import DATA_SHA256, load_dataset, runtime_hash, sha, summarize

PROJECT = "epochguard-005f"
COMPOSE = ["docker", "compose", "--env-file", "dev/lab.compose.env", "--project-directory", str(ROOT),
           "-f", "tests/gatecompare/compose.yaml"]


def environment():
    env = {k: v for k, v in os.environ.items() if not k.startswith(("EPOCHGUARD_", "COMPOSE_", "TAVILY_", "GEMINI_"))
           and not any(s in k.upper() for s in ("KEY", "TOKEN", "SECRET"))}
    env["COMPOSE_DISABLE_ENV_FILE"] = "1"
    return env


def source_hash():
    paths = [*ROOT.joinpath("tests/gatecompare").rglob("*.py"), *ROOT.joinpath("tests/gatecompare").rglob("*.json"),
        ROOT/"tests/gatecompare/Dockerfile", ROOT/"tests/gatecompare/compose.yaml", ROOT/"dev/prose/gateway.json",
        *ROOT.joinpath("plugins/epochguard").glob("*.go"), *ROOT.joinpath("internal/ingress").glob("*.go"),
        *ROOT.joinpath("cmd/protected-ingress").glob("*.go"), *ROOT.joinpath("cmd/provider-fixture").glob("*.go"),
        *ROOT.joinpath("services/verifier/verifier").rglob("*.py"), ROOT/"services/verifier/tests_bounded_prose/simulated.py",
        *ROOT.joinpath("services/claim_analysis/claim_analysis").rglob("*.py"),
        ROOT/"services/verifier/requirements.lock", *ROOT.joinpath("services/verifier").glob("Dockerfile*"),
        ROOT/"dev/Dockerfile", ROOT/"plugins/epochguard/go.mod", ROOT/"plugins/epochguard/go.sum", ROOT/"go.mod"]
    return sha(b"".join(p.relative_to(ROOT).as_posix().encode()+b"\0"+p.read_bytes().replace(b"\r\n", b"\n")
                        for p in sorted(set(paths))))


class Ownership:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.path, self.token = root/"owner.lock", uuid.uuid4().hex

    def __enter__(self):
        with self.path.open("x", encoding="ascii") as stream:
            stream.write(self.token)
        return self

    def __exit__(self, *args):
        if self.path.read_text(encoding="ascii") == self.token:
            self.path.unlink()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def execute(directory, *, repetitions=3, build=False, builder=None, invoke=subprocess.run):
    directory.mkdir(parents=True, exist_ok=False)
    env = environment() | {"EPOCHGUARD_005F_RUN_DIR": directory.as_posix()}
    stages, owns, started, measurements, images, failure = [], False, False, None, {}, None
    digest, revision = source_hash(), None

    def run(stage, command, *, timeout=180, check=True):
        print(stage, flush=True)
        started = time.monotonic()
        try:
            result = invoke(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired):
            raise RuntimeError("benchmark stage unavailable") from None
        stages.append({"stage": stage, "command": command, "exit_code": result.returncode,
                       "elapsed_ms": round((time.monotonic()-started)*1000, 3)})
        if check and result.returncode:
            raise RuntimeError("benchmark stage failed")
        return result

    def resources():
        return {kind: run("inspect-"+kind, ["docker", *args, "--filter", "label=com.docker.compose.project="+PROJECT]).stdout.split()
                for kind, args in (("containers", ["ps", "-aq"]), ("volumes", ["volume", "ls", "-q"]),
                                   ("networks", ["network", "ls", "-q"]))}

    cleanup = {"completed": False}
    try:
        if any(resources().values()):
            raise ValueError("existing benchmark resources; ownership not established")
        owns = True
        revision = run("revision", ["git", "rev-parse", "HEAD"]).stdout.strip()
        load_dataset()  # Freeze and validate before starting any request.
        if build:
            command = ["docker", "buildx", "build"] + (["--builder", builder] if builder else []) + ["--load"]
            run("build-native", command+["-t", "epochguard-dev:002a", "-f", "dev/Dockerfile", "."], timeout=1800)
            for name, base in (("004c", None), ("004e", "004c"), ("004g", "004e")):
                run("build-"+name, ["docker", "build", "-t", "epochguard-verifier:"+name,
                    "-f", "services/verifier/Dockerfile."+name, "."], timeout=1800)
        run("build-benchmark", ["docker", "build", "-t", "epochguard-benchmark:005f", "-f", "tests/gatecompare/Dockerfile", "."], timeout=600)
        for tag in ("epochguard-dev:002a", "epochguard-verifier:004g", "epochguard-benchmark:005f"):
            identity = run("image-identity", ["docker", "image", "inspect", "--format", "{{.Id}}", tag]).stdout.strip()
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
                raise ValueError("immutable image identity required")
            images[tag] = identity
        env.update(EPOCHGUARD_005F_NATIVE_IMAGE=images["epochguard-dev:002a"],
                   EPOCHGUARD_005F_BENCH_IMAGE=images["epochguard-benchmark:005f"])
        config = json.loads((ROOT/"dev/prose/gateway.json").read_text())
        write(directory/"gateway.json", config)
        control = dict(config, plugins=[])
        write(directory/"gateway-control.json", control)
        started = True  # A failed up can still leave owned resources to remove.
        run("start", COMPOSE+["up", "-d", "--wait", "ingress", "ingress-unsafe"], timeout=240)
        network_ids = resources()["networks"]
        networks = json.loads(run("network-isolation", ["docker", "network", "inspect", *network_ids]).stdout)
        if len(networks) != 2 or not all(n["Internal"] for n in networks):
            raise ValueError("external network present")
        container_ids = resources()["containers"]
        containers = json.loads(run("port-isolation", ["docker", "inspect", *container_ids]).stdout)
        if any(c["HostConfig"].get("PortBindings") for c in containers):
            raise ValueError("published benchmark port")
        write(directory/"isolation.json", {"internal_networks": len(networks), "published_ports": 0})
        result = run("measure", COMPOSE+["run", "--rm", "--no-deps", "-T", "benchmark", "python", "-m",
            "gatecompare.benchmark", "--repetitions", str(repetitions)], timeout=240)
        measurements = json.loads(result.stdout)
        write(directory/"measurements.json", measurements)
        expected_runtime = runtime_hash(ROOT/"services/verifier/verifier", ROOT/"services/verifier/tests_bounded_prose/simulated.py")
        if not measurements.get("complete") or measurements.get("dataset_sha256") != DATA_SHA256 or measurements.get("runtime_sha256") != expected_runtime:
            raise ValueError("incomplete or mismatched runtime measurement")
        summary = summarize(load_dataset(), measurements["measurements"], repetitions)
        if not summary["expectations_met"] or source_hash() != digest:
            raise ValueError("unexpected results or source changed")
    except Exception:
        failure = "benchmark incomplete; inspect sanitized stages and retained measurements"
    finally:
        if owns:
            try:
                down = run("cleanup", COMPOSE+["down", "--volumes", "--remove-orphans"], check=False) if started else None
                remaining = resources()
                cleanup = {"completed": (down is None or down.returncode == 0) and not any(remaining.values()), "remaining": remaining}
            except Exception:
                cleanup = {"completed": False}
        write(directory/"cleanup.json", cleanup)
        write(directory/"stages.json", stages)
    if failure or not cleanup["completed"]:
        write(directory/"failure.json", {"failure": failure or "cleanup incomplete", "source_revision": revision,
            "source_sha256": digest, "images": images, "cleanup": cleanup})
        raise RuntimeError("005F incomplete; sanitized artifacts retained")
    report = {"schema_version": "005f.report.v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": revision, "source_sha256": digest, "dataset_sha256": DATA_SHA256,
        "runtime_sha256": measurements["runtime_sha256"], "images": images, "fixture": True, "real_model": False,
        "baseline": "unprotected Bifrost gateway -> shared controlled provider; configured plugins empty, built-ins retained, EpochGuard absent",
        "direct_provider_delivery": "NOT MEASURED", "protected": "ingress -> pinned Bifrost -> native plugin -> Python verifier -> receipt-v2 ingress",
        "policy": "004g.v1/bounded-prose-v1", "receipt": "004g.receipt.v2",
        "repetitions": repetitions, "measurements": "measurements.json", "cleanup_completed": True,
        "latency_method": "perf_counter_ns, full response read, two warmups per path, persistent clients, alternating pair order; nearest-rank quantiles of matched observations; not pure plugin overhead",
        "metric_scope": "Authored synthetic labels and simulated source HTTP, not real-world factual detection accuracy. Missing-plugin refusal is necessary protection, excluded from unnecessary-refusal denominator.",
        **summary}
    write(directory/"report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="rebuild native and verifier dependencies first")
    parser.add_argument("--builder", help="Buildx builder for the pinned native build")
    parser.add_argument("--repetitions", type=int, choices=range(1, 6), default=3)
    args = parser.parse_args()
    root = ROOT/"artifacts/005f"
    with Ownership(root):
        directory = root/(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")+uuid.uuid4().hex[:8])
        execute(directory, repetitions=args.repetitions, build=args.build, builder=args.builder)
    print("005F CONTROLLED COMPARATIVE EVALUATION COMPLETE")
    print(directory.relative_to(ROOT))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("005F incomplete; no live calls or automatic retries; inspect artifacts/005f") from None
