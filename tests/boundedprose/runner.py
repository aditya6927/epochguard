"""Offline client/operator checks. Never prints raw bodies or receipts."""
import concurrent.futures
import asyncio
import json
import socket
import sys
import time
from pathlib import Path
import httpx

PATH = "/openai/v1/chat/completions"
A = "Python.org currently lists Python 3.15.2 as its latest stable Windows release.\nPyPI reports requests version 2.34.2."
B = A.replace("3.15.2", "3.15.1")
OLD = "The latest stable Python 3 release for Windows listed on Python.org is 3.88.7.\nThe version reported for requests by the PyPI JSON API is 2.88.7."
HEADERS = {"X-Bifrost-Setup-Token":"epochguard-local-dev-only"}
rows = []


def call(host, port, method, path, value=None, headers=None):
    with httpx.Client(timeout=12, trust_env=False, follow_redirects=False) as client:
        return client.request(method, f"http://{host}:{port}{path}", json=value, headers=headers)


def infer(name, text=A, status=200, host="ingress", role="user", fallback=None):
    started = time.monotonic()
    value = {"model":"fixture/epochguard-test", "messages":[{"role":role,"content":text}],"stream":False}
    if fallback is True or (fallback is None and role == "user"):
        value["fallbacks"] = ["fixture/epochguard-fallback"]
    r = call(host,8082,"POST",PATH,value, {"X-EpochGuard-Internal-Receipt":"forged", "X-EpochGuard-Verified":"true"})
    assert r.status_code in (status if isinstance(status,tuple) else (status,)), (name,r.status_code)
    assert not any(k.startswith("x-epochguard-") for k in r.headers)
    assert "UNVERIFIED_METADATA_004GS" not in r.text
    assert all("UNVERIFIED_METADATA_004GS" not in value for value in r.headers.values())
    if r.status_code == 200:
        assert r.json()["choices"][0]["message"]["content"].encode() == text.encode(), name
        if host != "ingress-old":
            assert r.json() == {"object":"chat.completion","choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":text}}]}, name
    else:
        assert "choices" not in r.json() and "PRIVATE_PROVIDER_SENTINEL" not in r.text
        assert all(line not in r.text for line in text.splitlines() if len(line)>12), name
        if r.status_code == 400:
            assert r.json()["error"] == {"type":"invalid_request_error","code":"epochguard_provider_error","message":"Provider request failed."}
    row = {"case":name,"status":r.status_code,"elapsed_ms":round((time.monotonic()-started)*1000,3),
           "candidate_bytes_match":r.status_code==200,"fixture":True}
    rows.append(row)
    return row


def control(fault):
    assert call("verifier",8000,"POST","/test/control",{"fault":fault}).status_code == 200


def ready(host="ingress", expected=200):
    assert call(host,8082,"GET","/ready").status_code == expected, host


def client():
    ready()
    for host in ("ingress-unsafe","ingress-cross-g","ingress-cross-b"): ready(host,503)
    infer("A-supported")
    infer("B-contradicted",B,403)
    forms = json.loads(Path("/app/conformance/004g-grammar.json").read_text())
    for i,row in enumerate(forms):
        if row["reason"] != "BOUNDED_GRAMMAR" and len(row["text"])>0 and not any(ord(c)<32 and c not in '\t\r\n' for c in row["text"]):
            infer(f"grammar-{i}",row["text"],503)
    for i,row in enumerate(forms[:9]): infer(f"form-{i}",row["text"])
    infer("missing-plugin",A,503,"ingress-unsafe")
    infer("004B-receipt-at-G",OLD,503,"ingress-cross-g")
    infer("004G-receipt-at-B",A,503,"ingress-cross-b")
    infer("old-profile-supported",OLD,200,"ingress-old")
    infer("provider-error","PRIVATE_PROVIDER_SENTINEL",400,role="system")
    for path in ("/v1/chat/completions","/api/plugins","/openai/v1/chat/completions?x=1"):
        assert call("ingress",8082,"POST",path,{}).status_code >=400
    value={"model":"fixture/epochguard-test","messages":[{"role":"user","content":A}],"stream":True}
    assert call("ingress",8082,"POST",PATH,value).status_code>=400
    for host,port in (("gateway",8080),("gateway-old",8080),("verifier",8000),("provider",9000)):
        try:
            socket.create_connection((host,port),timeout=.5).close()
        except OSError: pass
        else: raise AssertionError("private network exposed")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        tasks=[]
        for i in range(16):
            text,expected=(A+" "*i,(200,503)) if i%3==0 else (B+" "*i,(403,503)) if i%3==1 else (A+"\nExtra.",(503,))
            tasks.append(pool.submit(infer,f"concurrency-{i}",text,expected))
        outcomes=[task.result() for task in tasks]
        assert any(r["status"]==200 for r in outcomes)


def operator():
    before=call("verifier",8000,"GET","/test/report").json()
    ready()
    after=call("verifier",8000,"GET","/test/report").json()
    assert before["source_invocations"]==after["source_invocations"], "readiness retrieved evidence"
    count=call("provider",9000,"GET","/stats").json().get(B,0)
    infer("terminal-refusal-fallback",B,403)
    assert call("provider",9000,"GET","/stats").json().get(B,0)-count==1
    count=call("provider",9000,"GET","/stats").json().get(A,0)
    infer("genuine-provider-fallback",A,200,role="system",fallback=True)
    assert call("provider",9000,"GET","/stats").json().get(A,0)-count==2
    for fault in ("tavily-timeout","tavily-401","tavily-429","tavily-500","pypi-timeout","pypi-json","pypi-identity","work-deadline"):
        control(fault); infer("source-"+fault,A,503)
    control("none")
    for channel in ("id","model","system_fingerprint","service_tier","usage","extra_fields","routing_info","nested","http-header","raw_response","annotations"):
        assert call("provider",9000,"POST","/test/control",{"channel":channel}).status_code==200
        infer("metadata-"+channel,A,(200,503))
    assert call("provider",9000,"POST","/test/control",{"channel":"provider-error"}).status_code==200
    infer("metadata-provider-error",A,400)
    assert call("provider",9000,"POST","/test/control",{"channel":"none"}).status_code==200
    # Prove the would-be replacement is eligible, then retain the nonce and
    # substitute the original contradicted request at the real relay.
    assert call("receipt-relay",9003,"POST","/test/control",{"fault":"none"}).status_code==200
    infer("substitution-positive",A,200,"ingress-faults")
    for fault,text in (("request-substitute",B),("request-reserialize",A),("request-field",A)):
        assert call("receipt-relay",9003,"POST","/test/control",{"fault":fault}).status_code==200
        infer(fault,text,503,"ingress-faults")
    overload()
    for fault in ("none","mac","body","replay","policy","version","duplicate","missing","fake"):
        assert call("receipt-relay",9003,"POST","/test/control",{"fault":fault}).status_code==200
        infer("receipt-"+fault,A,200 if fault=="none" else 503,"ingress-faults")
    control("slow")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        tasks=[pool.submit(infer,"disable-inflight-"+str(i),A,(200,503)) for i in range(4)]
        time.sleep(.05)
        assert call("gateway",8080,"PUT","/api/plugins/epochguard",{"enabled":False},HEADERS).status_code==200
        for task in tasks: task.result()
    control("none")
    infer("disabled-plugin",A,503)
    ready(expected=503)
    assert call("verifier",8000,"GET","/test/report").json()["active"]==0


def overload():
    async def exercise():
        connections=[]
        try:
            # Partial bodies hold HTTP work before evidence-pipeline admission.
            for _ in range(40):
                reader,writer=await asyncio.open_connection("verifier",8000)
                writer.write(b"POST /v1/verify/prose HTTP/1.1\r\nHost: verifier\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{")
                await writer.drain();connections.append((reader,writer))
            async def status(reader):
                try:
                    return (await asyncio.wait_for(reader.readline(),.3)).startswith(b"HTTP/1.1 503")
                except TimeoutError: return False
            assert any(await asyncio.gather(*(status(r) for r,_ in connections))), "server admission did not refuse overload"
        finally:
            for _,writer in connections: writer.close()
            await asyncio.gather(*(w.wait_closed() for _,w in connections),return_exceptions=True)
        await asyncio.sleep(.2)
    before=call("verifier",8000,"GET","/test/report").json()
    asyncio.run(exercise())
    after=call("verifier",8000,"GET","/test/report").json()
    assert after["active"]==0 and before["source_invocations"]==after["source_invocations"]
    infer("overload-recovery")


def recovery():
    ready(); infer("restart-recovery")


def restart_window():
    counts={200:0,503:0}
    end=time.monotonic()+15
    while time.monotonic()<end:
        row=infer("restart-window",A,(200,503)); counts[row["status"]]+=1
        time.sleep(.15)
    assert counts[200]>0 and counts[503]>0, counts


if __name__=="__main__":
    {"client":client,"operator":operator,"recovery":recovery,"restart-window":restart_window}[sys.argv[1]]()
    print(json.dumps({"fixture":True,"real_model":False,"live_status":"004G LIVE QUALIFICATION PENDING","cases":rows},indent=2))
