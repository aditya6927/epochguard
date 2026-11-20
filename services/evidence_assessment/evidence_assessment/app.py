import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request as HTTPRequest
from fastapi.responses import JSONResponse, Response
from .factory import configured_pipeline
from .providers import strict_load
from .schema import Request, Result

ORIGIN="http://127.0.0.1:8791"
HEADERS={"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer",
    "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}


def error(mode, status, reason):
    value=Result(claim=None,evidence_mode=mode,reason_code=reason,explanation="The request could not be accepted.",
        uncertainty=["No assessment was completed."],sources=[],citation_ids=[],assessed_at=datetime.now(timezone.utc))
    return JSONResponse(value.model_dump(mode="json"),status_code=status,headers=HEADERS)


class Boundary:
    """Local origin, fixed routes, bounded receipt and cancellation on disconnect."""
    def __init__(self, app, mode): self.app,self.mode,self.active=app,mode,0

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http": return await self.app(scope,receive,send)
        headers={k.lower():v for k,v in scope["headers"]}
        path=scope["path"]
        if (headers.get(b"host")!=b"127.0.0.1:8791" or headers.get(b"origin",ORIGIN.encode())!=ORIGIN.encode() or
            scope.get("query_string") or headers.get(b"sec-fetch-site") not in (None,b"none",b"same-origin")):
            return await error(self.mode,403,"ORIGIN_REFUSED")(scope,receive,send)
        allowed=(scope["method"]=="GET" and path in ("/","/app.js","/app.css","/api/info","/health")) or (scope["method"]=="POST" and path=="/api/assess")
        if not allowed: return await error(self.mode,404,"ROUTE_REFUSED")(scope,receive,send)
        if scope["method"]!="POST":
            return await self.app(scope,receive,send)
        if (headers.get(b"origin")!=ORIGIN.encode() or headers.get(b"x-epochguard-explorer")!=b"1" or
            headers.get(b"content-type")!=b"application/json" or headers.get(b"content-encoding",b"identity")!=b"identity"):
            return await error(self.mode,403,"REQUEST_REFUSED")(scope,receive,send)
        if self.active>=4: return await error(self.mode,429,"BUSY")(scope,receive,send)
        self.active+=1
        try:
            return await self.body(scope,receive,send)
        finally:
            self.active-=1

    async def body(self, scope, receive, send):
        data=bytearray()
        try:
            async with asyncio.timeout(2):
                while True:
                    message=await receive()
                    if message["type"]=="http.disconnect": return
                    data.extend(message.get("body",b""))
                    if len(data)>4096: return await error(self.mode,413,"REQUEST_TOO_LARGE")(scope,receive,send)
                    if not message.get("more_body",False): break
        except TimeoutError:
            return await error(self.mode,408,"REQUEST_TIMEOUT")(scope,receive,send)
        replayed=False
        async def replay():
            nonlocal replayed
            if not replayed:
                replayed=True
                return {"type":"http.request","body":bytes(data),"more_body":False}
            return await receive()
        async def disconnected():
            while (await receive())["type"]!="http.disconnect": pass
        work=asyncio.create_task(self.app(scope,replay,send))
        watcher=asyncio.create_task(disconnected())
        try:
            done,_=await asyncio.wait((work,watcher),return_when=asyncio.FIRST_COMPLETED)
            if work in done: await work
        finally:
            for task in (work,watcher):
                if not task.done(): task.cancel()
            await asyncio.gather(work,watcher,return_exceptions=True)


def create_app(pipeline):
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,redirect_slashes=False)
    mode="simulated" if pipeline.simulated else "live"
    app.state.pipeline=pipeline
    app.add_middleware(Boundary,mode=mode)
    web=Path(__file__).parent/"web"

    @app.get("/")
    async def index(): return Response((web/"index.html").read_bytes(),media_type="text/html",headers=HEADERS)

    @app.get("/app.js")
    async def script(): return Response((web/"app.js").read_bytes(),media_type="text/javascript",headers=HEADERS)

    @app.get("/app.css")
    async def style(): return Response((web/"app.css").read_bytes(),media_type="text/css",headers=HEADERS)

    @app.get("/health")
    @app.get("/api/info")
    async def info():
        return JSONResponse({"mode":"experimental-evidence","authorization":False,"evidence_mode":mode,
            "label":"AI-assisted assessment — not gateway authorization","max_claim_characters":512},headers=HEADERS)

    @app.post("/api/assess")
    async def assess(request: HTTPRequest):
        try:
            value=Request.model_validate(strict_load(await request.body(),4096))
        except Exception:
            return error(mode,422,"INVALID_REQUEST")
        try:
            result=await pipeline.assess(value)
            result=Result.model_validate_json(result.model_dump_json())
            raw=result.model_dump_json().encode()
            if len(raw)>131072: raise ValueError()
            return Response(raw,media_type="application/json",headers=HEADERS)
        except asyncio.CancelledError:
            raise
        except Exception:
            return JSONResponse(pipeline.result(value.claim,"ASSESSMENT_ERROR","No assessment could be completed.").model_dump(mode="json"),headers=HEADERS)
    return app


def app(): return create_app(configured_pipeline())
