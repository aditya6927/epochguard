"""Synthetic original envelopes for real native gateway projection tests only."""
import copy
import json
from .common import OUTPUTS, SUPPORTED
from .response_shapes import envelope


def fixtures():
    def signed(text=SUPPORTED):
        return envelope(parts=[{"text": text, "thoughtSignature": "c3ludGhldGlj"}])

    cases = {name: (signed(text), outcome, True) for (name, text), outcome in
             zip(OUTPUTS.items(), ("ALLOW", "REJECT", "UNAVAILABLE", "UNAVAILABLE"))}
    cases["plain"] = (envelope(), "ALLOW", True)
    cases["file_neighbor"] = (envelope(parts=[signed()["candidates"][0]["content"]["parts"][0],
                                            {"fileData": {"mimeType": "image/png", "fileUri": "https://example.invalid/file"}}]), "PROVIDER_ERROR", False)

    def mutated(name, change):
        value = signed()
        change(value, value["candidates"][0], value["candidates"][0]["content"], value["candidates"][0]["content"]["parts"][0])
        cases[name] = (value, "PROVIDER_ERROR", False)

    mutated("file_same_part", lambda v, c, t, p: p.update(fileData={"fileUri": "https://example.invalid/file"}))
    mutated("two_candidates", lambda v, c, t, p: v["candidates"].append(copy.deepcopy(c)))
    mutated("detached_signature", lambda v, c, t, p: t["parts"].append({"thoughtSignature": p.pop("thoughtSignature")}))
    mutated("thinking_neighbor", lambda v, c, t, p: t["parts"].append({"thought": True, "text": "SYNTHETIC_THINKING"}))
    mutated("tool", lambda v, c, t, p: p.update(functionCall={"name": "synthetic", "args": {}}))
    cases["missing_plugin"] = (signed(), "INGRESS_REFUSED", False)
    mutated("grounding", lambda v, c, t, p: c.update(groundingMetadata={}))
    mutated("citation", lambda v, c, t, p: c.update(citationMetadata={}))
    mutated("candidate_unknown", lambda v, c, t, p: c.update(syntheticMetadata="SYNTHETIC"))
    mutated("part_unknown", lambda v, c, t, p: p.update(syntheticMetadata="SYNTHETIC"))
    mutated("max_tokens", lambda v, c, t, p: c.update(finishReason="MAX_TOKENS"))
    mutated("unknown_finish", lambda v, c, t, p: c.update(finishReason="SYNTHETIC"))
    mutated("empty_text", lambda v, c, t, p: p.update(text=""))
    mutated("signature_bad", lambda v, c, t, p: p.update(thoughtSignature="?"))
    mutated("signature_empty", lambda v, c, t, p: p.update(thoughtSignature=""))
    mutated("signature_excess", lambda v, c, t, p: p.update(thoughtSignature="AAAA" * 4097))
    mutated("text_excess", lambda v, c, t, p: p.update(text="x" * 8193))
    mutated("usage_unknown", lambda v, c, t, p: v["usageMetadata"].update(syntheticMetadata={}))
    mutated("wrong_type", lambda v, c, t, p: c.update(index=False))
    mutated("inline_data", lambda v, c, t, p: p.update(inlineData={"mimeType": "image/png", "data": "eA=="}))
    mutated("thinking_same_part", lambda v, c, t, p: p.update(thought=True))
    mutated("safety", lambda v, c, t, p: c.update(safetyRatings=[]))
    mutated("prompt_feedback", lambda v, c, t, p: v.update(promptFeedback={}))
    cases["malformed"] = (b'{"candidates":', "PROVIDER_ERROR", False)
    cases["duplicate"] = (b'{"candidates":[],"candidates":[]}', "PROVIDER_ERROR", False)
    cases["missing"] = ({}, "PROVIDER_ERROR", False)
    mutated("alias", lambda v, c, t, p: v.update(usage_metadata={}))
    mutated("nontext_usage", lambda v, c, t, p: v["usageMetadata"].update(promptTokensDetails=[{"modality": "IMAGE", "tokenCount": 1}]))
    mutated("tool_usage", lambda v, c, t, p: v["usageMetadata"].update(toolUsePromptTokenCount=1))
    cases["invalid_utf8"] = (b'{"candidates":"\xff"}', "PROVIDER_ERROR", False)
    return cases


FIXTURES = fixtures()
ADAPTER_PROMPTS = {"adapter_" + name: "005C-T synthetic original envelope: " + name for name in FIXTURES}
BATCHES = tuple(range(1, (len(FIXTURES) + 5) // 6 + 1))


def batch(number):
    return list(ADAPTER_PROMPTS)[(number-1)*6:number*6]


def response(name):
    value = FIXTURES[name.removeprefix("adapter_")][0]
    return value if type(value) is bytes else json.dumps(value, separators=(",", ":")).encode()
