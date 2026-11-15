"""Windows-compatible offline real gateway qualification. No live option or retries."""
import argparse
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
COMPOSE=["docker","compose","-f","compose.verify.004g.yaml"]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",action="store_true")
    parser.add_argument("--builder",default="epochguard-002a")
    args=parser.parse_args()
    logs=ROOT/"artifacts/004g/qualification"; logs.mkdir(parents=True,exist_ok=True)
    hidden=getattr(subprocess,"CREATE_NO_WINDOW",0)
    def run(name,command,check=True,timeout=240):
        print(name,flush=True)
        with (logs/(name+".log")).open("w",encoding="utf-8") as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout,creationflags=hidden)
        if check and result.returncode: raise RuntimeError(f"{name} failed; see artifacts/004g/qualification/{name}.log")
    def selected(name,role,action):
        run(name,COMPOSE+["run","--rm","--no-deps",f"qualification-{role}","python","/app/prose_runner.py",action])
    observer=None
    try:
        if args.build:
            for name,tag,file in [("native","epochguard-dev:002a","dev/Dockerfile"),("004c","epochguard-verifier:004c","services/verifier/Dockerfile.004c"),("004e","epochguard-verifier:004e","services/verifier/Dockerfile.004e"),("004g","epochguard-verifier:004g","services/verifier/Dockerfile.004g")]:
                # Derived images use the local daemon's just-built base tags.
                command = (["docker","buildx","build","--builder",args.builder,"--load"]
                           if name in {"native","004c"} else ["docker","build"])
                run("build-"+name,command+["-t",tag,"-f",file,"."],timeout=1800)
        run("clean-start",COMPOSE+["down","--volumes","--remove-orphans"])
        run("start",COMPOSE+["up","-d","--wait","verifier-old","ingress","ingress-unsafe","ingress-cross-g","ingress-cross-b","ingress-old","ingress-faults"])
        selected("client","client","client")
        selected("operator","operator","operator")
        run("restore-stop",COMPOSE+["stop","-t","1","gateway"])
        run("restore-start",COMPOSE+["up","-d","--wait","gateway"])
        selected("recovery","client","recovery")
        with (logs/"restart-window.log").open("w",encoding="utf-8") as stream:
            observer=subprocess.Popen(COMPOSE+["run","--rm","--no-deps","qualification-client","python","/app/prose_runner.py","restart-window"],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,creationflags=hidden)
            time.sleep(4)
            run("restart-stop",COMPOSE+["stop","-t","1","gateway"])
            time.sleep(2)
            run("restart-start",COMPOSE+["up","-d","--wait","gateway"])
            if observer.wait(timeout=40): raise RuntimeError("restart window failed")
            observer=None
        selected("final-recovery","client","recovery")
        # Inspect runtime output in memory. Never persist raw service logs or
        # reflect an offending line; a failure reports a fixed category only.
        result=subprocess.run(COMPOSE+["logs","--no-color","gateway","provider","verifier","ingress"],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,creationflags=hidden)
        if result.returncode or any(marker in result.stdout for marker in (
            b"UNVERIFIED_METADATA_004GS",
            b"Python.org currently lists Python 3.15.",
            b"PyPI reports requests version 2.34.2.",
        )):
            raise RuntimeError("operational log isolation check failed; raw lines withheld")
        print("runtime logs: no candidate or metadata sentinel observed",flush=True)
        print("004G offline qualification passed; 004G LIVE QUALIFICATION PENDING",flush=True)
    finally:
        if observer is not None and observer.poll() is None:
            observer.terminate(); observer.wait(timeout=10)
        run("cleanup",COMPOSE+["down","--volumes","--remove-orphans"],check=False)


if __name__=="__main__": main()
