"""Export exact generation schemas, or explicitly opt in to bounded API probes.

No raw provider output, credentials, headers or error messages are recorded.
Alternative schemas are diagnostic-only, never automatic production fallbacks.
"""

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

import httpx

from .gemini import GeminiProvider, provider_schema
from .model import AnalysisFailure, ModelExtractor
from .schema import AnalysisInput, Extraction


DEFAULT_VARIANTS = ("original", "no_max_items")
VARIANTS = DEFAULT_VARIANTS + ("no_titles", "no_numeric_bounds", "nullable_type_union", "inline_refs")


def canonical(schema):
    return json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")


def remove_keywords(value, keys):
    if isinstance(value, list):
        return [remove_keywords(v, keys) for v in value]
    if not isinstance(value, dict):
        return value
    return {k:remove_keywords(v, keys) for k,v in value.items() if k not in keys}


def nullable_types(value):
    if isinstance(value, list):
        return [nullable_types(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k:nullable_types(v) for k,v in value.items()}
    branches = result.get("anyOf")
    if branches == [{"type":"string"}, {"type":"null"}]:
        del result["anyOf"]
        result["type"] = ["string", "null"]
    return result


def inline_refs(schema):
    definitions = schema.get("$defs", {})
    def expand(value, active=()):
        if isinstance(value, list):
            return [expand(v, active) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            name = value["$ref"].removeprefix("#/$defs/")
            if value["$ref"] != "#/$defs/"+name or name not in definitions or name in active or len(value) != 1:
                raise ValueError("unsupported or cyclic diagnostic reference")
            return expand(definitions[name], active+(name,))
        return {k:expand(v, active) for k,v in value.items() if k != "$defs"}
    return expand(schema)


def generation_schemas():
    strict = Extraction.model_json_schema()
    original = provider_schema(strict, omit_array_bounds=False)
    reduced = provider_schema(strict)
    return {
        "original":original,
        "no_max_items":reduced,
        # Each further probe changes ONE factor relative to no_max_items.
        "no_titles":remove_keywords(reduced, {"title"}),
        "no_numeric_bounds":remove_keywords(reduced, {"minimum", "maximum"}),
        "nullable_type_union":nullable_types(reduced),
        "inline_refs":inline_refs(reduced)}


class StatusTransport(httpx.AsyncBaseTransport):
    """Observe only HTTP status; delegate TLS/network to normal httpx transport."""
    def __init__(self):
        self.delegate = httpx.AsyncHTTPTransport(retries=0)
        self.status = None

    async def handle_async_request(self, request):
        response = await self.delegate.handle_async_request(request)
        self.status = response.status_code
        return response

    async def aclose(self):
        await self.delegate.aclose()


class ProbeProvider(GeminiProvider):
    """Same transport/budget path, selected schema from the fixed local matrix."""
    def select_schema(self, schema):
        self.selected_schema = copy.deepcopy(schema)

    def _generation_schema(self, schema):
        return self.selected_schema


async def probe(provider, schemas, selected, *, transport_factory=StatusTransport):
    # Fixed synthetic input: never read a candidate, dataset label or URL from CLI.
    request = AnalysisInput(text="The stock is available.", reference_date="2026-11-08")
    rows = []
    for name in selected:
        provider.select_schema(schemas[name])
        transport = transport_factory()
        provider._transport = transport
        before = provider.calls
        start = time.perf_counter()
        failure, failure_details, valid, usage = None, None, False, None
        try:
            _, reply = await ModelExtractor(provider, provider.settings.timeout_seconds).analyze(request)
            valid = True
            usage = {"input_tokens":reply.input_tokens, "output_tokens":reply.output_tokens,
                     "estimated_cost_usd":reply.estimated_cost_usd}
        except AnalysisFailure as error:
            failure = str(error)
            failure_details = error.diagnostic.to_dict() if error.diagnostic is not None else None
        finally:
            await transport.aclose()
        rows.append({"variant":name, "http_status":transport.status,
                     "http_accepted":transport.status == 200, "strict_analysis_valid":valid,
                     "failure_code":failure, "failure_details":failure_details, "attempts":provider.calls-before,
                     "latency_ms":(time.perf_counter()-start)*1000, "usage":usage})
        if failure in {"MODEL_BUDGET_EXCEEDED", "MODEL_TIMEOUT"} or transport.status in {401,403,429} or (transport.status is not None and transport.status >= 500):
            break  # Do not burn more quota on auth/rate/network availability problems.
        if transport.status is None:
            break
    return rows


async def run(args):
    selected = args.variants
    if len(set(selected)) != len(selected) or args.max_requests < len(selected) or args.max_requests > len(VARIANTS):
        raise ValueError("unique variants and a sufficient bounded request budget required")
    schemas = generation_schemas()
    # Preflight all model opt-in/settings before creating a misleading live report.
    provider = ProbeProvider.from_environment(args.max_requests) if args.live else None
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"diagnostic_schema":"004a.gemini-schema.v1", "mode":"live" if args.live else "offline_export",
                "selected_variants":selected, "live_qualification_pending":True,
                "model":provider.settings.model if provider else None,
                "schemas":{}, "results":[]}
    for name in selected:
        schema = schemas[name]
        (args.output/f"{name}.json").write_text(json.dumps(schema,indent=2)+"\n",encoding="utf-8")
        manifest["schemas"][name] = {"sha256":hashlib.sha256(canonical(schema)).hexdigest(),
                                   "canonical_bytes":len(canonical(schema)),
                                   "relative_to":"original" if name == "no_max_items" else "no_max_items" if name != "original" else None}
    if provider is not None:
        manifest["results"] = await probe(provider, schemas, selected)
        manifest["model_configuration"] = provider.settings.model_dump()
        manifest["attempts"] = provider.calls
        manifest["reserved_planning_cost_usd"] = provider.reserved_usd
        # Only the adapter's actual default schema can be qualified by this tool.
        manifest["live_qualification_pending"] = not any(r["variant"] == "no_max_items" and r["strict_analysis_valid"] for r in manifest["results"])
    (args.output/"report.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2))
    if provider is not None:
        by_name = {r["variant"]:r for r in manifest["results"]}
        # Original 400 is a comparison result, not failure of the candidate test.
        if "no_max_items" not in by_name or not by_name["no_max_items"]["strict_analysis_valid"]:
            return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--live",action="store_true",help="also requires existing environment model-call opt-in/key/rates")
    parser.add_argument("--variants",nargs="+",choices=VARIANTS,default=list(DEFAULT_VARIANTS))
    parser.add_argument("--max-requests",type=int,default=2)
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except AnalysisFailure as error:
        print(json.dumps({"status":"DIAGNOSTIC_FAILED","reason":str(error)}),file=sys.stderr)
    except (ValueError,OSError):
        print(json.dumps({"status":"DIAGNOSTIC_FAILED","reason":"INVALID_CONFIGURATION_OR_OUTPUT_PATH"}),file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
