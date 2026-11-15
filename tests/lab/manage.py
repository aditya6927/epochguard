"""Local offline Lab lifecycle. No credential files or live profiles are read."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--env-file", "dev/lab.compose.env", "-f", "compose.lab.yaml"]
IMAGE_PREFIX = "epochguard"
PROJECT = "epochguard-lab"
TEST_PORT = 8787


class StageFailure(RuntimeError):
    """Only fixed local stage labels and allowlisted diagnoses are printable."""


def diagnosis(output):
    # Inspect captured bytes, never reflect arbitrary output, paths or secrets.
    if b'use `docker --context=' in output and b'to switch to context' in output:
        return "builder/context mismatch; omit --builder or select a builder belonging to the active Docker context"
    if any(value in output.lower() for value in (b'failed to resolve', b'no such host', b'tls handshake timeout', b'network is unreachable')):
        return "public dependency/network resolution failed; check Docker DNS, proxy and registry access, then rerun the build"
    if b'Cannot connect to the Docker daemon' in output or b'error during connect' in output:
        return "Docker daemon unavailable; start Docker Desktop in Linux-container mode"
    if b'error from sender' in output and b'Access is denied' in output:
        return "build context contains an unreadable local artifact; check Docker ignore rules and filesystem access"
    if b'Pool overlaps' in output:
        return "Docker network address pools overlap; inspect this project's network allocation without deleting unrelated networks"
    return "command failed; run the documented standalone command for this stage locally; inspect its output privately"


def environment():
    env = {key: os.environ[key] for key in os.environ if not key.startswith(("EPOCHGUARD_", "COMPOSE_", "TAVILY_", "GEMINI_"))
           and not any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET"))}
    env["COMPOSE_DISABLE_ENV_FILE"] = "1"
    env["EPOCHGUARD_LAB_IMAGE_PREFIX"] = IMAGE_PREFIX
    env["EPOCHGUARD_LAB_TEST_PORT"] = str(TEST_PORT)
    return env


def run(command, *, timeout=240, check=True, name=None):
    stage = name or "command"
    try:
        completed = subprocess.run(command, cwd=ROOT, env=environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise StageFailure(stage + ": deadline exceeded; inspect Docker build/service health locally") from None
    except OSError:
        raise StageFailure(stage + ": executable unavailable; install Docker Desktop/Compose and check PATH") from None
    if check and completed.returncode:
        raise StageFailure(stage + ": " + diagnosis(completed.stdout + completed.stderr))
    return completed


def build_images(builder):
    # Omit --builder by default: Buildx selects its configured builder for the
    # active Docker context. A builder literally named 'default' is not portable.
    buildx = ["docker", "buildx", "build"] + (["--builder", builder] if builder else []) + ["--load"]
    builds = (("-dev:002a", "dev/Dockerfile", None),
              ("-verifier:004c", "services/verifier/Dockerfile.004c", None),
              ("-verifier:004e", "services/verifier/Dockerfile.004e", "-verifier:004c"),
              ("-verifier:004g", "services/verifier/Dockerfile.004g", "-verifier:004e"))
    for suffix, file, base in builds:
        tag = IMAGE_PREFIX + suffix
        command = buildx if base is None else ["docker", "build"]
        arguments = ["--build-arg", "VERIFIER_BASE=" + IMAGE_PREFIX + base] if base else []
        print("Build " + tag, flush=True)
        run(command + arguments + ["-t", tag, "-f", file, "."], timeout=1800, name="build " + file)
    run(COMPOSE + ["build", "lab"], timeout=1800, name="build dev/Dockerfile.lab")


def private(target, value):
    # Fixed trusted operator controls for tests only; no browser route to these.
    destinations = {"verifier": "http://127.0.0.1:8000/test/control", "provider": "http://provider:9000/test/control"}
    script = "import urllib.request; opener=urllib.request.build_opener(urllib.request.ProxyHandler({})); r=opener.open(urllib.request.Request(" + repr(destinations[target]) + ",data=" + repr(json.dumps(value).encode()) + ",headers={'Content-Type':'application/json'}),timeout=5); assert r.status==200"
    run(COMPOSE + ["exec", "-T", "verifier", "python", "-c", script], name="private test control")


def faults():
    import concurrent.futures
    from smoke import call, verify
    _, info, _ = call("/api/demo/info")
    text = info["scenarios"][0]["candidate"]
    rows = []
    private("provider", {"channel":"id"})
    rows.append(verify("custom", text, 200, "ALLOW"))
    private("provider", {"channel":"provider-error"})
    rows.append(verify("custom", text, 400, "PROVIDER_ERROR"))
    private("provider", {"channel":"none"})
    private("verifier", {"fault":"slow"})
    try:
        import threading
        barrier = threading.Barrier(16)
        def burst(_):
            barrier.wait(timeout=5)
            return call("/api/demo/verify", {"scenario":"custom","candidate":text})
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            responses = list(pool.map(burst, range(16)))
        assert any(status == 200 for status, _, _ in responses)
        assert any(status == 503 and value["boundary"] == "lab" for status, value, _ in responses)
        for status, value, _ in responses:
            assert status in (200,503)
            assert value["content"] == text if status == 200 else value["content"] is None
        rows.append({"case":"overload","requests":16,"allowed":sum(s==200 for s,_,_ in responses),"refused":sum(s==503 for s,_,_ in responses)})
    finally:
        private("verifier", {"fault":"none"})
    rows.append(verify("custom", text, 200, "ALLOW"))
    for service in ("verifier", "gateway"):
        try:
            run(COMPOSE + ["stop", "-t", "1", service], name="stop " + service)
            status, value, elapsed = call("/api/demo/verify", {"scenario":"custom","candidate":text})
            assert status == 503 and value["content"] is None and text not in json.dumps(value)
            rows.append({"case":"missing-"+service,"status":status,"outcome":value["outcome"],"boundary":value["boundary"],"elapsed_ms":elapsed})
        finally:
            run(COMPOSE + ["up", "-d", "--wait", "--no-deps", service], name="restore " + service)
        rows.append(verify("custom", text, 200, "ALLOW"))
    # The BFF has no private-network membership; evidence services have no
    # public/entry network. Inspect only networking, never container env dumps.
    for service in ("gateway", "gateway-control", "provider", "verifier", "ingress", "ingress-unsafe"):
        container = run(COMPOSE + ["ps", "-q", service]).stdout.decode().strip()
        network = json.loads(run(["docker","inspect",container,"--format","{{json .NetworkSettings}}"] ).stdout)
        assert not any((network["Ports"] or {}).values())
        assert PROJECT + "_local-entry" not in network["Networks"]
    container = run(COMPOSE + ["ps", "-q", "lab"]).stdout.decode().strip()
    network = json.loads(run(["docker","inspect",container,"--format","{{json .NetworkSettings}}"] ).stdout)
    assert network["Ports"] == {"8787/tcp":[{"HostIp":"127.0.0.1","HostPort":str(TEST_PORT)}]}
    assert set(network["Networks"]) == {PROJECT + "_local-entry", PROJECT + "_edge"}
    for name in ("edge", "private"):
        result = run(["docker", "network", "inspect", PROJECT + "_" + name, "--format", "{{.Internal}}"])
        assert result.stdout.strip() == b"true"
    rows.append({"case":"network-boundary","private_services_unpublished":True,"lab_published_only_on_loopback":True})
    print(json.dumps({"fixture":True,"fault_checks":rows}, sort_keys=True))


def main():
    global IMAGE_PREFIX, PROJECT, TEST_PORT, COMPOSE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "test"])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--builder", help="Explicit Buildx builder (otherwise use Docker's selection)")
    parser.add_argument("--image-prefix", default="epochguard", help="Isolated local image namespace for clean-install qualification")
    parser.add_argument("--project-name", default="epochguard-lab", help="Compose project owned by this invocation")
    parser.add_argument("--test-port", type=int, default=8787, help="Test-only loopback connection port; application Host/Origin remain fixed")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.image_prefix):
        parser.error("image prefix must contain 1-63 lowercase letters, digits or hyphens")
    IMAGE_PREFIX = args.image_prefix
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.project_name):
        parser.error("project name must contain 1-63 lowercase letters, digits or hyphens")
    if not 1024 <= args.test_port <= 65535 or (args.action == "up" and args.test_port != 8787):
        parser.error("test port must be 1024-65535 and is unavailable for interactive up")
    PROJECT, TEST_PORT = args.project_name, args.test_port
    COMPOSE = COMPOSE + ["--project-name", PROJECT]
    if args.action == "down":
        if not cleanup():
            parser.exit(1)
        print("Lab stopped; disposable signing volume removed.")
        return
    # Do not take ownership of a running operator stack and later delete it.
    # This is outside the cleanup region because this invocation owns nothing.
    if args.action == "test":
        try:
            existing = run(COMPOSE + ["ps", "--all", "--quiet"], name="project ownership preflight")
        except StageFailure as error:
            parser.exit(1, "Lab failed: " + str(error) + ". No existing stack changed.\n")
        if existing.stdout.strip():
            parser.exit(1, "Lab test refused: project already has containers; select a separate --project-name and --test-port, or stop that project explicitly. No existing stack changed.\n")
    try:
        if args.build:
            build_images(args.builder)
        print("Start offline Lab", flush=True)
        run(COMPOSE + ["up","-d","--wait","lab"], name="startup")
        if args.action == "test":
            import smoke
            smoke.TRANSPORT_ORIGIN = "http://127.0.0.1:" + str(TEST_PORT)
            smoke.main()
            faults()
        else:
            print("Open http://127.0.0.1:8787 | fixture evidence only")
    except (RuntimeError, OSError, subprocess.TimeoutExpired, AssertionError) as error:
        message = str(error) if isinstance(error, StageFailure) else "qualification failed; inspect the fixed stage checks locally"
        print("Lab failed: " + message + ". No raw response or environment printed.", file=sys.stderr)
        if args.action != "test":
            cleanup()
        parser.exit(1)
    finally:
        if args.action == "test":
            if not cleanup():
                parser.exit(1)


def cleanup():
    try:
        result = run(COMPOSE + ["down", "--volumes", "--remove-orphans"], check=False, name="cleanup")
        if result.returncode == 0:
            return True
    except StageFailure:
        pass
    print("Lab cleanup failed; run the documented down command to remove the stack/signing volume.", file=sys.stderr)
    return False


if __name__ == "__main__":
    main()
