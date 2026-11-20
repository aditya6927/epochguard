from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import httpx
from .config import Settings, offline_settings, require_live, read_key, private_file
from .pipeline import Pipeline
from .providers import Search, Assessor, strict_load, SEARCH_URL, MODEL_ROOT

PACKET_SHA256="77deb8d225124aca38d9fbd177056b798d8fad0124a112e702e3aae73c098e04"


def packet():
    raw=(Path(__file__).resolve().parents[1]/"data/offline-v1.json").read_bytes().replace(b"\r\n",b"\n")
    if hashlib.sha256(raw).hexdigest()!=PACKET_SHA256:
        raise ValueError("offline packet digest mismatch")
    return strict_load(raw,131072)


def offline_pipeline(case=None, *, settings=None, clock=lambda:datetime.now(timezone.utc)):
    settings=settings or offline_settings()
    demos={row["claim"]:row for row in packet()["cases"] if row["demonstration"]}

    def selected(claim):
        if case is not None:
            if claim!=case["claim"]: raise ValueError("offline case binding")
            return case
        return demos.get(claim,{"claim":claim,"results":[],"fault":"none"})

    async def search(request):
        assert str(request.url)==SEARCH_URL
        value=json.loads(request.content)
        row=selected(value["query"])
        if row["fault"]=="search-timeout": raise httpx.ReadTimeout("simulated")
        return httpx.Response(200,json={"query":value["query"],"results":row["results"]})

    async def model(request):
        assert str(request.url)==MODEL_ROOT+settings.model+":generateContent"
        value=json.loads(request.content)
        data=json.loads(value["contents"][0]["parts"][0]["text"])
        row=selected(data["original_claim"])
        if row["fault"]=="model-timeout": raise httpx.ReadTimeout("simulated")
        return httpx.Response(200,json={"candidates":[{"finishReason":"STOP","content":{"role":"model",
            "parts":[{"text":json.dumps(row["model_record"])}]}}],"usageMetadata":{"promptTokenCount":500,"totalTokenCount":900}})

    return Pipeline(Search(settings,"offline-fixture-only",simulated=True,transport=httpx.MockTransport(search),clock=clock),
        Assessor(settings,"offline-fixture-only",simulated=True,transport=httpx.MockTransport(model)),settings,simulated=True,clock=clock)


def live_pipeline():
    require_live()  # Before files, credentials, provider construction or network.
    try:
        path=private_file(os.environ["EPOCHGUARD_005I_SETTINGS_FILE"])
        with path.open("rb") as stream: raw=stream.read(8193)
        settings=Settings.model_validate(strict_load(raw,8192))
        if settings.max_requests>3: raise ValueError()
        gemini=read_key(os.environ["EPOCHGUARD_005I_GEMINI_SECRET_FILE"])
        tavily=read_key(os.environ["EPOCHGUARD_005I_TAVILY_SECRET_FILE"])
    except Exception:
        raise ValueError("invalid private live configuration") from None
    clock=lambda:datetime.now(timezone.utc)
    return Pipeline(Search(settings,tavily,simulated=False,clock=clock),Assessor(settings,gemini,simulated=False),
                    settings,simulated=False,clock=clock)


def configured_pipeline():
    mode=os.getenv("EPOCHGUARD_005I_MODE","offline")
    if mode=="offline":
        if any(os.getenv(key) for key in ("EPOCHGUARD_005I_ALLOW_GEMINI","EPOCHGUARD_005I_ALLOW_TAVILY",
            "EPOCHGUARD_005I_SETTINGS_FILE","EPOCHGUARD_005I_GEMINI_SECRET_FILE","EPOCHGUARD_005I_TAVILY_SECRET_FILE")):
            raise ValueError("offline configuration must not contain live controls")
        return offline_pipeline()
    if mode=="live": return live_pipeline()
    raise ValueError("unknown explorer mode")
