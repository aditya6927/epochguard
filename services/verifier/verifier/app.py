import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .contract import VerificationRequest, VerificationResponse
from .diagnostics import failure
from .policy import verify
from .retrieval import TavilyRetriever
from .settings import TimeoutSettings


class RequestBound:
    """Small ASGI body/deadline boundary, including chunked requests."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/v1/verify":
            return await self.app(scope, receive, send)
        data = bytearray()
        try:
            async with asyncio.timeout(2):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    data.extend(message.get("body", b""))
                    if len(data) > 8192:
                        return await JSONResponse({"detail": "request too large"}, status_code=413)(scope, receive, send)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            failure("verification_failure", "request_failure")
            return await JSONResponse({"detail": "request deadline"}, status_code=408)(scope, receive, send)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}
            return await receive()

        return await self.app(scope, replay, send)


def create_app(retriever=None, *, timeouts: TimeoutSettings | None = None) -> FastAPI:
    budgets = timeouts if timeouts is not None else TimeoutSettings.from_environment()
    app = FastAPI(title="EpochGuard 003A narrow verifier")
    app.add_middleware(RequestBound)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/v1/verify", response_model=VerificationResponse)
    async def check(request: VerificationRequest):
        try:
            # No retries; the Go caller also imposes its own total deadline.
            async with asyncio.timeout(budgets.verification_seconds):
                source = retriever if retriever is not None else TavilyRetriever.from_environment(timeouts=budgets)
                return await verify(request, source)
        except Exception as error:
            failure("verification_failure", "verification_timeout" if isinstance(error, TimeoutError) else "verification_unavailable")
            return VerificationResponse(request_id=request.request_id,
                                        candidate_sha256=request.candidate_sha256,
                                        claim=None, verdict="INSUFFICIENT",
                                        reason_code="VERIFIER_ERROR", evidence=[],
                                        checked_at=datetime.now(timezone.utc))

    return app


app = create_app()
