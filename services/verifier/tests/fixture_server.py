"""Offline Tavily HTTP test double; never substitutes for the verifier policy."""

import asyncio
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from verifier.contract import SOURCE_URL

app = FastAPI()
calls = Counter()
primary = (Path(__file__).parent / "fixtures" / "primary.txt").read_text()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def stats():
    return dict(calls)


@app.post("/v1/verify")
async def malformed_verifier():
    # Deliberately malformed verifier edge, not an alternative ALLOW source.
    calls["malformed_verifier"] += 1
    return PlainTextResponse('{"verdict":"SUPPORTED"}', media_type="application/json")


@app.post("/{mode}/extract")
async def extract(mode: str, request: Request):
    body = await request.json()
    expected = {"urls": [SOURCE_URL], "extract_depth": "basic", "format": "text",
                "timeout": 3.0, "include_images": False}
    if body != expected:
        return PlainTextResponse("unexpected retrieval request", status_code=400)
    calls[mode] += 1
    if mode == "timeout":
        await asyncio.sleep(6)
    if mode == "failure":
        return PlainTextResponse("fixture retrieval failure", status_code=503)
    if mode == "missing":
        content = "Python Releases for Windows\nStable Releases\nNo latest label available."
    elif mode == "ambiguous":
        content = primary.replace("Stable Releases", "Latest Python 3 Release - Python 3.88.6\nStable Releases")
    else:
        # The gateway must hold all candidate bytes during this retrieval wait.
        await asyncio.sleep(0.2)
        content = primary
    return {"results": [{"url": SOURCE_URL, "raw_content": content}],
            "failed_results": [], "request_id": f"offline-{mode}-{calls[mode]}", "response_time": 0.2}
