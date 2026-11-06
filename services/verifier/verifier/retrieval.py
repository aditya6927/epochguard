"""Fixed-URL Tavily Extract client. Candidate text never enters this request."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os

import httpx

from .contract import SOURCE_URL
from .settings import TimeoutSettings


class RetrievalFailure(Exception):
    pass


class RetrievalTimeout(RetrievalFailure):
    pass


@dataclass(frozen=True)
class Page:
    url: str
    content: str
    retrieved_at: datetime
    retrieval_id: str
    retrieval_mode: str = "fixture"


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


class TavilyRetriever:
    def __init__(self, *, client: httpx.AsyncClient | None = None,
                 endpoint: str = "https://api.tavily.com/extract",
                 api_key: str = "", timeouts: TimeoutSettings | None = None):
        self.client = client
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeouts = timeouts if timeouts is not None else TimeoutSettings()

    @classmethod
    def from_environment(cls, *, timeouts: TimeoutSettings | None = None):
        endpoint = "https://api.tavily.com/extract"
        key = os.getenv("TAVILY_API_KEY", "")
        override = os.getenv("EPOCHGUARD_TEST_TAVILY_ENDPOINT")
        if override:
            if os.getenv("EPOCHGUARD_TEST_MODE") != "1":
                raise ValueError("test endpoint requires explicit test mode")
            if key != "local-fixture-only":
                raise ValueError("test endpoints accept only the local fixture credential")
            endpoint = override
        return cls(endpoint=endpoint, api_key=key,
                   timeouts=timeouts if timeouts is not None else TimeoutSettings.from_environment())

    async def retrieve(self) -> Page:
        if not self.api_key:
            raise RetrievalFailure("credential unavailable")
        try:
            # asyncio bounds the whole operation, not only individual socket reads.
            async with asyncio.timeout(self.timeouts.retrieval_seconds):
                if self.client is not None:
                    return await self._request(self.client)
                async with httpx.AsyncClient(timeout=self.timeouts.retrieval_seconds, follow_redirects=False,
                                             trust_env=False) as client:
                    return await self._request(client)
        except (TimeoutError, httpx.TimeoutException):
            raise RetrievalTimeout("retrieval deadline") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise RetrievalFailure("invalid retrieval") from None

    async def _request(self, client: httpx.AsyncClient) -> Page:
        async with client.stream("POST", self.endpoint,
                                 headers={"Authorization": "Bearer " + self.api_key},
                                 json={"urls": [SOURCE_URL], "extract_depth": "basic",
                                       "format": "text", "timeout": self.timeouts.tavily_api_seconds,
                                       "include_images": False},
                                 timeout=self.timeouts.retrieval_seconds) as response:
            if response.status_code != 200:
                raise RetrievalFailure("retrieval status")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 1024 * 1024:
                    raise RetrievalFailure("retrieval too large")
        result = json.loads(data, object_pairs_hook=unique_object)
        # HTTP 200 is not enough: Tavily explicitly supports partial failures.
        if not isinstance(result, dict) or result.get("failed_results") != []:
            raise RetrievalFailure("partial extraction failure")
        rows = result.get("results")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise RetrievalFailure("missing or ambiguous extraction")
        row = rows[0]
        if row.get("url") != SOURCE_URL:
            raise RetrievalFailure("unexpected authority URL")
        content, request_id = row.get("raw_content"), result.get("request_id")
        if not isinstance(content, str) or not 1 <= len(content) <= 500_000:
            raise RetrievalFailure("invalid content")
        if not isinstance(request_id, str):
            raise RetrievalFailure("missing retrieval identifier")
        mode = "fixture" if self.client is not None or self.endpoint != "https://api.tavily.com/extract" else "tavily_live"
        return Page(SOURCE_URL, content, datetime.now(timezone.utc), request_id, mode)
