"""Experimental endpoint composition; the qualified 003A app is unchanged."""

import asyncio
import os

from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse, Response

from claim_analysis.schema import strict_json
from verifier.app import create_app as legacy_app
from verifier.diagnostics import failure
from .contract import Request, Result
from .demo import scenario

PATH = "/v1/verify/multiclaim"


class MultiBound:
    """Bound body receipt before decoding, and cancel work on disconnect."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != PATH:
            return await self.app(scope, receive, send)
        data = bytearray()
        try:
            async with asyncio.timeout(2):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    data.extend(message.get("body", b""))
                    if len(data) > 65536:
                        return await JSONResponse({"detail": "request too large"}, status_code=413)(scope, receive, send)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            failure("verification_failure", "request_failure")
            return await JSONResponse({"detail": "request deadline"}, status_code=408)(scope, receive, send)
        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        async def disconnected():
            while True:
                if (await receive())["type"] == "http.disconnect":
                    return

        # Never leave abandoned work or a receive watcher behind. Real disconnect
        # cancels the application; external cancellation propagates in finally.
        work = asyncio.create_task(self.app(scope, replay, send))
        watcher = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait({work, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                await work
        finally:
            for task in (work, watcher):
                if not task.done():
                    task.cancel()
            await asyncio.gather(work, watcher, return_exceptions=True)


def create_app(pipeline):
    # Compose routes in this separate entry point, without changing /v1/verify.
    app = legacy_app()
    app.add_middleware(MultiBound)

    @app.post(PATH)
    async def verify(request: HTTPRequest):
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json" or request.headers.get("content-encoding", "identity") != "identity":
            return JSONResponse({"detail": "unsupported format"}, status_code=415)
        try:
            record = Request.model_validate(strict_json(await request.body()))
        except (ValueError, TypeError, RecursionError):
            failure("verification_failure", "request_failure")
            return JSONResponse({"detail": "invalid request"}, status_code=422)
        try:
            result = await pipeline.verify(record)
            # Explicit revalidation and bounded serialization before any response
            # bytes are sent. No raw validation exception enters diagnostics.
            result = Result.model_validate(result.model_dump(warnings=False))
            data = result.model_dump_json().encode("utf-8")
            if len(data) > 256 * 1024:
                raise ValueError("result bound")
            return Response(data, media_type="application/json")
        except Exception:
            failure("verification_failure", "verification_unavailable")
            return JSONResponse({"detail": "verification unavailable"}, status_code=503)

    return app


def fixture_app():
    # This packaged entry point is offline-only. An unset/unknown configuration
    # fails startup; there is no implicit live-source selection or credential use.
    if os.getenv("EPOCHGUARD_TEST_MODE") != "1":
        raise ValueError("experimental fixture deployment requires test mode")
    case = os.environ["EPOCHGUARD_004C_FIXTURE_CASE"]
    if case not in {"A", "C", "E", "F"}:
        raise ValueError("unknown trusted fixture case")
    pipeline, _ = scenario(case)
    return create_app(pipeline)
