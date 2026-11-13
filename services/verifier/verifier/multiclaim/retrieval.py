"""Fixed-package PyPI client. Injected transports always produce fixture mode."""

import asyncio
from datetime import datetime, timezone
import uuid

import httpx

from verifier.retrieval import Page, RetrievalFailure, RetrievalTimeout
from .contract import PYPI_URL

MAX_EVIDENCE_BYTES = 1024 * 1024


class PyPIRetriever:
    def __init__(self, *, transport=None, timeout_seconds: float = 4):
        if not 0.01 <= timeout_seconds <= 20:
            raise ValueError("invalid retrieval deadline")
        self.transport, self.timeout_seconds = transport, timeout_seconds

    async def retrieve(self) -> Page:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with httpx.AsyncClient(transport=self.transport, follow_redirects=False,
                                             trust_env=False, timeout=self.timeout_seconds,
                                             limits=httpx.Limits(max_connections=1)) as client:
                    async with client.stream("GET", PYPI_URL, headers={"Accept": "application/json"}) as response:
                        if response.status_code != 200 or str(response.url) != PYPI_URL:
                            raise RetrievalFailure()
                        if response.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                            raise RetrievalFailure()
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > MAX_EVIDENCE_BYTES:
                                raise RetrievalFailure()
            return Page(PYPI_URL, body.decode("utf-8"), datetime.now(timezone.utc),
                        uuid.uuid4().hex, "fixture" if self.transport is not None else "pypi_live")
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise RetrievalTimeout() from None
        except (httpx.HTTPError, UnicodeError):
            raise RetrievalFailure() from None
