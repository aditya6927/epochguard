"""Existing client/operator split; no receipts or answer bodies are exported."""
import argparse
import json
import socket
import time

import httpx
from gatecompare.benchmark import payload, protected_outcome
from .variable_fixture import read_profile
from .variable_matrix import cases, sha


def run(action, index=None, fault="none"):
    profile = read_profile()
    with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
        if action == "report":
            response = client.get("http://verifier:8000/qualification/report")
            response.raise_for_status()
            return response.json()
        if action == "control":
            response = client.post("http://receipt-relay:9003/test/control", json={"fault":fault})
            response.raise_for_status()
            return {"status":response.status_code,"fault":fault}
        for host, port in (("gateway",8080),("verifier",8000),("provider",9000),("receipt-relay",9003)):
            try:
                connection=socket.create_connection((host,port),timeout=.3)
            except OSError:
                continue
            connection.close()
            raise ValueError("private service exposed to client")
        if action == "ready":
            statuses={host:client.get(f"http://{host}:8082/ready").status_code for host in ("ingress","ingress-unsafe")}
            if statuses != {"ingress":200,"ingress-unsafe":503}:
                raise ValueError("readiness boundary")
            return {"statuses":statuses,"private_services_inaccessible":True}
        selected=cases(profile)
        if index is not None: selected=[selected[index]]
        rows=[]
        for case in selected:
            wire=payload({"candidate":case.text})
            started=time.perf_counter_ns()
            with client.stream("POST",f"http://{case.route}:8082/openai/v1/chat/completions",content=wire,
                headers={"Content-Type":"application/json","X-EpochGuard-Internal-Receipt":"unsigned"}) as response:
                data=bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data)>256*1024: raise ValueError("response bound")
            if any(name.startswith("x-epochguard-") for name in response.headers):
                raise ValueError("internal header exposed")
            outcome, released=protected_outcome(response.status_code,json.loads(data),case.text)
            rows.append({"case":case.name,"status":response.status_code,"outcome":outcome,
                "content_released":released,"candidate_sha256":sha(case.text.encode()),
                "approved_content_sha256":sha(case.text.encode()) if released else None,
                "request_sha256":sha(wire),"response_sha256":sha(data),"elapsed_ns":time.perf_counter_ns()-started})
        return {"profile":profile.name,"cases":rows,"private_services_inaccessible":True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("client","ready","report","control"))
    parser.add_argument("--case",type=int)
    parser.add_argument("--fault",default="none",choices=("none","mac","body","policy","request-field","replay"))
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.action,args.case,args.fault),allow_nan=False))
    except Exception:
        raise SystemExit("005H role failed; unsafe diagnostics withheld") from None


if __name__ == "__main__": main()
