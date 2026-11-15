"""Local offline Lab lifecycle. No credential files or live profiles are read."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "--env-file", "dev/lab.compose.env", "-f", "compose.lab.yaml"]


def environment():
    env = {key: os.environ[key] for key in os.environ if not key.startswith(("EPOCHGUARD_", "COMPOSE_", "TAVILY_", "GEMINI_"))
           and not any(part in key.upper() for part in ("API_KEY", "TOKEN", "SECRET"))}
    env["COMPOSE_DISABLE_ENV_FILE"] = "1"
    return env


def run(command, *, timeout=240, check=True, name=None):
    completed = subprocess.run(command, cwd=ROOT, env=environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # Never echo arbitrary process errors or resolved configuration. Fixed stage
    # labels suffice; standalone build commands are documented for diagnostics.
    if check and completed.returncode:
        raise RuntimeError("Lab stage failed: " + (name or "command"))
    return completed


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
        assert "epochguard-lab_local-entry" not in network["Networks"]
    container = run(COMPOSE + ["ps", "-q", "lab"]).stdout.decode().strip()
    network = json.loads(run(["docker","inspect",container,"--format","{{json .NetworkSettings}}"] ).stdout)
    assert network["Ports"] == {"8787/tcp":[{"HostIp":"127.0.0.1","HostPort":"8787"}]}
    assert set(network["Networks"]) == {"epochguard-lab_local-entry", "epochguard-lab_edge"}
    rows.append({"case":"network-boundary","private_services_unpublished":True,"lab_published_only_on_loopback":True})
    print(json.dumps({"fixture":True,"fault_checks":rows}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "down", "test"])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--builder", default="default")
    args = parser.parse_args()
    if args.action == "down":
        run(COMPOSE + ["down","--volumes","--remove-orphans"], name="cleanup")
        print("Lab stopped; disposable signing volume removed.")
        return
    try:
        if args.build:
            for tag, file in (("epochguard-dev:002a","dev/Dockerfile"), ("epochguard-verifier:004c","services/verifier/Dockerfile.004c"),
                              ("epochguard-verifier:004e","services/verifier/Dockerfile.004e"), ("epochguard-verifier:004g","services/verifier/Dockerfile.004g")):
                command = ["docker","buildx","build","--builder",args.builder,"--load"] if tag.endswith((":002a",":004c")) else ["docker","build"]
                print("Build "+tag, flush=True)
                run(command+["-t",tag,"-f",file,"."],timeout=1800,name="image build")
            run(COMPOSE + ["build","lab"], timeout=1800, name="Lab image build")
        print("Start offline Lab", flush=True)
        run(COMPOSE + ["up","-d","--wait","lab"], name="startup")
        if args.action == "test":
            import smoke
            smoke.main()
            faults()
        else:
            print("Open http://127.0.0.1:8787 | fixture evidence only")
    except (RuntimeError, OSError, subprocess.TimeoutExpired, AssertionError):
        run(COMPOSE + ["down","--volumes","--remove-orphans"], check=False, name="failure cleanup")
        parser.exit(1,"Lab failed; no raw response or environment printed.\n")
    finally:
        if args.action == "test":
            run(COMPOSE + ["down","--volumes","--remove-orphans"], name="test cleanup")


if __name__ == "__main__":
    main()
