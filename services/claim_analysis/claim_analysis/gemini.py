"""One bounded Gemini REST request per response. No SDK, tools or retries."""

import asyncio
import json
import os
import re

import httpx
from pydantic import Field

from .model import AnalysisFailure, ModelReply, SYSTEM
from .schema import MAX_JSON, Strict, strict_json


class ModelSettings(Strict):
    provider: str = "gemini"
    model: str
    timeout_seconds: float = Field(default=30.0, ge=0.1, le=60, allow_inf_nan=False)
    max_output_tokens: int = Field(default=4096, ge=128, le=8192)
    max_requests: int = Field(default=1, ge=1, le=100)
    input_usd_per_million: float = Field(ge=0, le=1000, allow_inf_nan=False)
    output_usd_per_million: float = Field(ge=0, le=1000, allow_inf_nan=False)
    max_request_usd: float = Field(default=0.25, gt=0, le=10, allow_inf_nan=False)
    max_run_usd: float = Field(default=1.0, gt=0, le=25, allow_inf_nan=False)


def provider_schema(value):
    """Gemini supports a JSON Schema subset; full rules remain local checks."""
    allowed = {"$defs", "$ref", "type", "title", "description", "enum", "items",
               "minItems", "maxItems", "minimum", "maximum", "anyOf", "properties",
               "additionalProperties", "required"}
    if isinstance(value, list):
        return [provider_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "const":
            result["enum"] = [item]
        elif key in {"properties", "$defs"}:
            result[key] = {name:provider_schema(child) for name,child in item.items()}
        elif key in allowed:
            result[key] = provider_schema(item)
    return result


class GeminiProvider:
    def __init__(self, settings: ModelSettings, key: str, *, transport=None):
        if settings.provider != "gemini" or not re.fullmatch(r"gemini-[a-z0-9][a-z0-9.-]{0,95}", settings.model):
            raise ValueError("unsupported provider/model identifier")
        if not key or key.strip() != key or any(ord(c) < 33 for c in key):
            raise ValueError("missing/invalid model credential")
        self.settings, self._key, self._transport = settings, key, transport
        self.calls, self.reserved_usd = 0, 0.0
        self._budget_lock = asyncio.Lock()

    @classmethod
    def from_environment(cls, max_requests=1):
        if os.environ.get("EPOCHGUARD_ALLOW_MODEL_CALLS") != "1":
            raise AnalysisFailure("MODEL_NOT_ENABLED")
        try:
            settings = ModelSettings(
                model=os.environ["EPOCHGUARD_CLAIM_MODEL"], max_requests=max_requests,
                timeout_seconds=float(os.environ.get("EPOCHGUARD_CLAIM_TIMEOUT_SECONDS", "30")),
                max_output_tokens=int(os.environ.get("EPOCHGUARD_CLAIM_MAX_OUTPUT_TOKENS", "4096")),
                input_usd_per_million=float(os.environ["EPOCHGUARD_CLAIM_INPUT_USD_PER_MILLION"]),
                output_usd_per_million=float(os.environ["EPOCHGUARD_CLAIM_OUTPUT_USD_PER_MILLION"]),
                max_request_usd=float(os.environ.get("EPOCHGUARD_CLAIM_MAX_REQUEST_USD", "0.25")),
                max_run_usd=float(os.environ.get("EPOCHGUARD_CLAIM_MAX_RUN_USD", "1")))
            return cls(settings, os.environ["GEMINI_API_KEY"])
        except (ValueError, KeyError):
            raise AnalysisFailure("INVALID_MODEL_CONFIGURATION") from None

    async def generate(self, request, schema):
        settings = self.settings
        candidate = json.dumps({"reference_date": request.reference_date, "text": request.text}, ensure_ascii=False)
        # Deliberately pessimistic planning estimate, NOT a billing guarantee.
        input_bound = len((SYSTEM + candidate + json.dumps(schema)).encode("utf-8")) + 1024
        reservation = (input_bound * settings.input_usd_per_million + settings.max_output_tokens * settings.output_usd_per_million) / 1_000_000
        async with self._budget_lock:
            if self.calls >= settings.max_requests or reservation > settings.max_request_usd or self.reserved_usd + reservation > settings.max_run_usd:
                raise AnalysisFailure("MODEL_BUDGET_EXCEEDED")
            # Failed/cancelled calls consume their reservation; no retry loophole.
            self.calls += 1
            self.reserved_usd += reservation
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": candidate}]}],
            "generationConfig": {"candidateCount": 1, "temperature": 0,
                                 "maxOutputTokens": settings.max_output_tokens,
                                 "responseMimeType": "application/json", "responseJsonSchema": provider_schema(schema)}}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.model}:generateContent"
        try:
            async with asyncio.timeout(settings.timeout_seconds):
                async with httpx.AsyncClient(timeout=settings.timeout_seconds, follow_redirects=False,
                                             trust_env=False, transport=self._transport) as client:
                    async with client.stream("POST", url, json=payload, headers={"x-goog-api-key": self._key}) as response:
                        if response.status_code != 200:
                            raise AnalysisFailure("MODEL_PROVIDER_FAILURE")
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_JSON:
                                raise AnalysisFailure("MODEL_OUTPUT_TOO_LARGE")
            record = strict_json(bytes(data))
            candidates = record["candidates"]
            if len(candidates) != 1 or candidates[0]["finishReason"] != "STOP":
                raise AnalysisFailure("MODEL_INCOMPLETE")
            parts = candidates[0]["content"]["parts"]
            text_parts = [p["text"] for p in parts if "text" in p and not p.get("thought", False)]
            if not text_parts or any("functionCall" in p for p in parts):
                raise AnalysisFailure("MODEL_INVALID_RESPONSE")
            usage = record.get("usageMetadata", {})
            incoming = usage.get("promptTokenCount")
            total = usage.get("totalTokenCount")
            if incoming is not None or total is not None:
                if type(incoming) is not int or type(total) is not int or not 0 <= incoming <= total:
                    raise AnalysisFailure("MODEL_INVALID_USAGE")
                outgoing = total - incoming  # Includes reported thought tokens.
                cost = (incoming * settings.input_usd_per_million + outgoing * settings.output_usd_per_million) / 1_000_000
            else:
                outgoing, cost = None, None
            return ModelReply("".join(text_parts), incoming, outgoing, cost)
        except asyncio.CancelledError:
            raise
        except (TimeoutError, httpx.TimeoutException):
            raise AnalysisFailure("MODEL_TIMEOUT") from None
        except AnalysisFailure:
            raise
        except Exception:
            raise AnalysisFailure("MODEL_PROVIDER_FAILURE") from None
