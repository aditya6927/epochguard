"""Native Gemini resource boundary; never an evidence or release authority."""
import asyncio
import os
import time
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from claim_analysis.schema import strict_json
from .response_observations import observe_envelope
from .response_shapes import SHAPE_PROMPTS, response as shape_response
from .common import OUTPUTS, PROMPTS, read_settings, sha
from .adapter import adapt
from .adapter_shapes import ADAPTER_PROMPTS, response as adapter_response

DEADLINE, RUN_SECONDS, REQUEST_LIMIT, RESPONSE_LIMIT = 15, 300, 8192, 65536


class Relay:
    def __init__(self, settings, *, live=False, transport=None):
        settings.preflight(live)
        if live and transport is not None:
            raise ValueError("live transport replacement forbidden")
        self.settings, self.live, self.transport = settings, live, transport
        self.records, self.reserved, self.active = [], 0.0, False
        self.rejections = {}
        self.started = time.monotonic()

    async def generate(self, data, key):
        row, started, phase = None, time.monotonic(), "request_size"
        try:
            if len(data) > REQUEST_LIMIT:
                raise ValueError()
            value = strict_json(data)
            phase = "root_fields"
            # No tools, cached content, arbitrary native/system instructions or
            # candidate-selected API options can pass this cost boundary.
            if set(value) != {"model", "contents", "generationConfig"} or value["model"] != self.settings.model or len(value["contents"]) != 1:
                raise ValueError()
            content = value["contents"][0]
            phase = "content_fields"
            if set(content) != {"role", "parts"} or content["role"] != "user" or len(content["parts"]) != 1 or set(content["parts"][0]) != {"text"}:
                raise ValueError()
            prompt = content["parts"][0]["text"]
            phase = "prompt"
            scenario = next(name for name, text in (PROMPTS | SHAPE_PROMPTS | ADAPTER_PROMPTS).items() if prompt == text)
            if self.live and scenario not in OUTPUTS:
                raise ValueError()
            config = value["generationConfig"]
            phase = "generation_config"
            if set(config) != {"maxOutputTokens"} or type(config["maxOutputTokens"]) is not int or config["maxOutputTokens"] != self.settings.output_tokens:
                raise ValueError()
            reservation = self.settings.reservation(len(data))
            phase = "admission"
            if (self.active or len(self.records) >= self.settings.max_requests or
                time.monotonic() - self.started >= RUN_SECONDS or reservation > self.settings.max_request_usd or
                self.reserved + reservation > self.settings.max_run_usd or (self.live and not key)):
                raise ValueError()
            # No await between admission and reservation. Failures/cancellation
            # retain the reservation; no refund, reset endpoint or retry.
            self.active = True
            self.reserved += reservation
            row = {"scenario": scenario, "transport": "real_https" if self.live else "simulated_gemini",
                   "real_provider_invocation_attempted": self.live, "state": "failed",
                   "failure": "transport", "http_status": None, "candidate_sha256": None,
                   "matches_intended_text": None, "input_tokens": None, "output_tokens_including_thoughts": None,
                   "finite_grammar_observation": None,
                   "estimated_cost_usd": None, "request_sha256": sha(data), "reservation_usd": reservation}
            self.records.append(row)
            transport = self.transport if self.transport is not None else None if self.live else httpx.MockTransport(self.simulated)
            async with asyncio.timeout(min(DEADLINE, RUN_SECONDS - (time.monotonic() - self.started))):
                async with httpx.AsyncClient(transport=transport, timeout=DEADLINE, trust_env=False, follow_redirects=False) as client:
                    async with client.stream("POST", "https://generativelanguage.googleapis.com/v1beta/models/" + self.settings.model + ":generateContent",
                                             content=data, headers={"Content-Type": "application/json", "x-goog-api-key": key}) as response:
                        body = bytearray()
                        async for chunk in response.aiter_bytes():
                            body.extend(chunk)
                            if len(body) > RESPONSE_LIMIT:
                                row["failure"] = "body_limit"
                                raise ValueError()
                        row["http_status"] = response.status_code
                        row.update(state="completed" if response.status_code == 200 else "failed",
                                   failure=None if response.status_code == 200 else "provider_http")
                        if response.status_code == 200:
                            self.observe(bytes(body), scenario, row)
                            if self.settings.response_mode == "strict-005ct":
                                projected, diagnostic = adapt(bytes(body))
                                row["adapter"] = diagnostic
                                if projected is None:
                                    return self.error(502)
                                return Response(projected, status_code=200, media_type="application/json")
                        # Unadapted successes and genuine HTTP failures retain
                        # their original bytes/status. No model output repair.
                        return Response(bytes(body), status_code=response.status_code, media_type="application/json")
        except asyncio.CancelledError:
            if row is not None:
                row.update(state="cancelled", failure="cancelled")
            raise
        except (TimeoutError, httpx.TimeoutException):
            if row is not None:
                row["failure"] = "timeout"
            return self.error(504)
        except Exception:
            if row is None:
                self.rejections[phase] = self.rejections.get(phase, 0) + 1
            return self.error(502 if row is not None else 429)
        finally:
            if row is not None:
                row["elapsed_ms"] = round((time.monotonic() - started) * 1000, 3)
                self.active = False

    def observe(self, body, scenario, row):
        # Original-envelope telemetry does not authorize the projection/release.
        try:
            value = strict_json(body)
        except Exception:
            row["response_structure"] = {"schema_version": "005cr.response-shape.v1", "parse_outcome": "INVALID_JSON"}
            return
        try:
            usage = value.get("usageMetadata", {})
            incoming, total = usage.get("promptTokenCount"), usage.get("totalTokenCount")
            if type(incoming) is int and type(total) is int and 0 <= incoming <= total:
                row.update(input_tokens=incoming, output_tokens_including_thoughts=total-incoming,
                           estimated_cost_usd=(incoming*self.settings.input_usd_per_million + (total-incoming)*self.settings.output_usd_per_million)/1_000_000)
        except Exception:
            pass  # Unknown usage is independent of malformed candidate structure.
        try:
            observe_envelope(value, scenario, row)
        except Exception:
            row["response_structure"] = {"schema_version": "005cr.response-shape.v1", "parse_outcome": "OBSERVATION_UNAVAILABLE"}

    @staticmethod
    def error(status):
        return JSONResponse({"error": {"code": status, "status": "UNAVAILABLE", "message": "Qualification provider unavailable."}}, status_code=status)

    async def simulated(self, request):
        prompt = strict_json(request.content)["contents"][0]["parts"][0]["text"]
        name = next(name for name, text in (PROMPTS | SHAPE_PROMPTS | ADAPTER_PROMPTS).items() if prompt == text)
        if name in ADAPTER_PROMPTS:
            return httpx.Response(200, content=adapter_response(name), headers={"Content-Type": "application/json"})
        if name in SHAPE_PROMPTS:
            return httpx.Response(200, content=shape_response(name), headers={"Content-Type": "application/json"})
        if name == "timeout":
            raise httpx.ReadTimeout("simulated")
        if name == "provider_error":
            return httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "simulated private provider error"}})
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"text": OUTPUTS[name]}]},
                                                       "finishReason": "STOP", "index": 0}],
                                         "modelVersion": "SIMULATED_METADATA_005C", "responseId": "SIMULATED_METADATA_005C"})

    def report(self):
        return {"schema_version": "005c.transport.v1", "real_provider": self.live,
                "response_mode": self.settings.response_mode,
                "attempted": len(self.records), "completed": sum(r["state"] == "completed" for r in self.records),
                "failed": sum(r["state"] == "failed" for r in self.records),
                "cancelled": sum(r["state"] == "cancelled" for r in self.records),
                "reserved_planning_usd": self.reserved, "records": self.records,
                "rejections": self.rejections,
                "count_scope": "one relay HTTPS submission attempt; not independent inference or billing evidence"}


def create_app(relay):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    async def health():
        return {"ready": True}

    @app.get("/report")
    async def report():
        return relay.report()

    @app.post("/v1beta/models/{model}:generateContent")
    async def generate(model: str, request: Request):
        if model != relay.settings.model or request.url.query:
            return relay.error(400)
        try:
            async with asyncio.timeout(2):
                data = bytearray()
                async for chunk in request.stream():
                    data.extend(chunk)
                    if len(data) > REQUEST_LIMIT:
                        return relay.error(413)
            return await relay.generate(bytes(data), request.headers.get("x-goog-api-key", ""))
        except Exception:
            return relay.error(502)

    return app


def app():
    live = os.getenv("EPOCHGUARD_005C_MODE") == "live"
    if live and os.getenv("EPOCHGUARD_RUN_MODEL_005C") != "1":
        raise ValueError("separate model opt-in required")
    return create_app(Relay(read_settings("/run/qualification/settings.json"), live=live))
