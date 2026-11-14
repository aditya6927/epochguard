"""Host-side offline qualification, including startup, disable and real restart.

Requires Docker Desktop; no Docker socket is mounted in any test container.
All private test controls stay on the operator network. Logs contain only the
bounded fixture tests' diagnostics, not the generated signing key or receipts.
"""

import argparse
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", "compose.verify.004d.yaml"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build the pinned native and experimental Python images first")
    parser.add_argument("--builder", default="epochguard-002a")
    args = parser.parse_args()
    logs = ROOT / "artifacts/004d/reproduction"
    logs.mkdir(parents=True, exist_ok=True)
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run(name, command, *, check=True, timeout=180):
        print(name, flush=True)
        with (logs / f"{name}.log").open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, creationflags=hidden)
        if check and result.returncode:
            raise RuntimeError(f"{name} failed; see artifacts/004d/reproduction/{name}.log")

    def selected(name, role, test):
        run(name, COMPOSE + ["run", "--rm", "--no-deps", f"qualification-{role}",
                            "/app/protectedingress.test", "-test.v", f"-test.run=^{test}$", "-test.timeout=90s"])

    observer = None
    try:
        if args.build:
            run("native-build", ["docker", "buildx", "build", "--builder", args.builder, "--load",
                                "-t", "epochguard-dev:002a", "-f", "dev/Dockerfile", "."], timeout=1800)
            run("python-build", ["docker", "buildx", "build", "--builder", args.builder, "--load",
                                "-t", "epochguard-verifier:004c", "-f", "services/verifier/Dockerfile.004c", "."], timeout=600)
        run("clean-start", COMPOSE + ["down", "--volumes", "--remove-orphans"])
        run("ingress-first", COMPOSE + ["up", "-d", "ingress"])
        selected("startup", "client", "TestClientStartupOffline")
        run("private-stack", COMPOSE + ["up", "-d", "--wait", "gateway", "gateway-control", "gateway-invalid",
                                       "gateway-initfail", "gateway-loadfail", "receipt-relay", "ingress-faults",
                                       "ingress-unsafe", "ingress-badkey", "ingress-unavailable"])
        run("client", COMPOSE + ["run", "--rm", "--no-deps", "qualification-client"])
        run("operator", COMPOSE + ["run", "--rm", "--no-deps", "qualification-operator"])
        selected("disable", "operator", "TestOperatorDisable")
        run("restore-stop", COMPOSE + ["stop", "-t", "1", "gateway"])
        run("restore-start", COMPOSE + ["start", "gateway"])
        selected("recovery", "client", "TestClientRecovery")
        print("concurrent-restart", flush=True)
        with (logs / "concurrent-restart.log").open("w", encoding="utf-8") as stream:
            observer = subprocess.Popen(COMPOSE + ["run", "--rm", "--no-deps", "qualification-client",
                "/app/protectedingress.test", "-test.v", "-test.run=^TestClientRestartWindow$", "-test.timeout=60s"],
                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, creationflags=hidden)
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if "=== RUN   TestClientRestartWindow" in (logs / "concurrent-restart.log").read_text(encoding="utf-8"):
                    break
                if observer.poll() is not None:
                    raise RuntimeError("restart observer failed to start")
                time.sleep(0.1)
            else:
                raise RuntimeError("restart observer startup deadline")
            time.sleep(2)
            run("restart-stop", COMPOSE + ["stop", "-t", "1", "gateway"])
            time.sleep(1)
            run("restart-start", COMPOSE + ["start", "gateway"])
            if observer.wait(timeout=65):
                raise RuntimeError("concurrent restart assertion failed; see its log")
            observer = None
        selected("final-recovery", "client", "TestClientRecovery")
        print("004D offline qualification passed", flush=True)
    finally:
        if observer is not None and observer.poll() is None:
            observer.terminate()
            try:
                observer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                observer.kill()
                observer.wait()
        run("cleanup", COMPOSE + ["down", "--volumes", "--remove-orphans"], check=False)


if __name__ == "__main__":
    main()
