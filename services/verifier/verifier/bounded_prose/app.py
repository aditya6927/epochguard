"""Private trusted deployment only; importing never selects a source."""

import os
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse, Response
from claim_analysis.schema import strict_json
from verifier.app import create_app as legacy_app
from verifier.multiclaim.app import MultiBound
from verifier.multiclaim.demo import FixtureSource
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import PYPI_URL
from verifier.multiclaim.pipeline import Pipeline as EvidencePipeline
from .contract import Request, Result
from .pipeline import Pipeline

PATH = "/v1/verify/prose"


def create_app(pipeline):
    app = legacy_app()
    app.add_middleware(MultiBound, path=PATH)

    @app.post(PATH)
    async def verify(request: HTTPRequest):
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json" or request.headers.get("content-encoding", "identity") != "identity":
            return JSONResponse({"detail": "unsupported format"}, status_code=415)
        try:
            record = Request.model_validate(strict_json(await request.body()))
        except (ValueError, TypeError, RecursionError):
            return JSONResponse({"detail": "invalid request"}, status_code=422)
        try:
            result = Result.model_validate((await pipeline.verify(record)).model_dump(warnings=False))
            data = result.model_dump_json().encode()
            if len(data) > 256 * 1024:
                raise ValueError("output limit")
            return Response(data, media_type="application/json")
        except Exception:
            return JSONResponse({"detail": "verification unavailable"}, status_code=503)
    return app


def fixture_app():
    if os.getenv("EPOCHGUARD_TEST_MODE") != "1":
        raise ValueError("004G fixture requires explicit test mode")
    # Synthetic observations; no credentials, egress or implicit live fallback.
    python = FixtureSource(SOURCE_URL, "Python Releases for Windows\nLatest Python 3 Release - Python 3.15.2\nStable Releases\n")
    pypi = FixtureSource(PYPI_URL, '{"info":{"name":"requests","version":"2.34.2","yanked":false}}')
    return create_app(Pipeline(EvidencePipeline(python, pypi, fixture=True)))
