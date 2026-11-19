"""Reuse 005C's fixed-host relay and exact strict adapter with a trusted plan."""
import copy
import httpx
from claim_analysis.schema import strict_json
from modelqualification.relay import Relay, create_app
from modelqualification.common import sha
from .common import read_runtime, read_plan, scenarios, MODEL_CASES, live_guards, runtime_code_hash


class CombinedRelay(Relay):
    def __init__(self, runtime, plan, *, transport=None):
        if runtime.live:
            live_guards()
        super().__init__(runtime.settings, live=runtime.live, transport=transport)
        self.outputs, self.prompts = scenarios(plan, runtime)
        self.live_scenarios = set(MODEL_CASES)

    def observe(self, body, scenario, row):
        super().observe(body, scenario, row)
        if row.get("candidate_sha256") is not None:
            row["matches_intended_text"] = row["candidate_sha256"] == sha(self.outputs[scenario])

    def report(self):
        return super().report() | {"runtime_code_sha256":runtime_code_hash()}

    async def simulated(self, request):
        prompt = strict_json(request.content)["contents"][0]["parts"][0]["text"]
        name = next(k for k, v in self.prompts.items() if v == prompt)
        if name == "provider_error":
            return httpx.Response(400, json={"error": {"code": 400, "status": "INVALID_ARGUMENT", "message": "synthetic provider failure"}})
        part = {"text": self.outputs[name], "thoughtSignature": "c3ludGhldGlj"}
        candidate = {"content": {"role": "model", "parts": [part]}, "finishReason": "STOP", "index": 0}
        value = {"candidates": [candidate], "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 30}}
        if name in {"malformed", "two_candidates"}:
            value["candidates"].append(copy.deepcopy(candidate))
        elif name == "file_neighbor":
            candidate["content"]["parts"].append({"fileData": {"fileUri": "https://example.invalid/file", "mimeType": "image/png"}})
        elif name == "file_same_part":
            part["fileData"] = {"fileUri": "https://example.invalid/file", "mimeType": "image/png"}
        elif name == "detached_signature":
            candidate["content"]["parts"].append({"thoughtSignature": part.pop("thoughtSignature")})
        elif name == "thinking":
            candidate["content"]["parts"].append({"thought": True, "text": "SYNTHETIC_PRIVATE_REASONING"})
        elif name == "tool":
            part["functionCall"] = {"name": "synthetic", "args": {}}
        return httpx.Response(200, json=value)


def app():
    runtime = read_runtime()
    if runtime.live:
        live_guards()
    return create_app(CombinedRelay(runtime, read_plan(runtime)))
