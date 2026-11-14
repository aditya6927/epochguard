"""Standalone, non-authorizing analysis and frozen draft evaluation."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import statistics

from claim_analysis.alignment import Identification
from claim_analysis.gemini import GeminiProvider
from claim_analysis.model import AnalysisFailure, FakeProvider, ModelExtractor, PROMPT_VERSION, SYSTEM
from claim_analysis.schema import strict_json
from verifier.multiclaim.demo import scenario
from verifier.policy import digest

from .dataset import DATA, file_hash, load
from .evaluation import score
from .pipeline import Analyzer
from .schema import Request


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error interpolates arbitrary argument values.
        print('{"status":"ANALYSIS_FAILED","reason":"INVALID_ARGUMENTS","authorization":false}', file=sys.stderr)
        raise SystemExit(2)


class MeasuredProvider:
    """Retain bounded usage even when the subsequent alignment/schema fails.

    No raw reply/candidate is retained here. Gemini still owns reservations and
    request limits; wrapping does not retry or refund failed attempts.
    """
    def __init__(self, provider):
        self.provider, self.last = provider, None

    async def generate(self, request, schema):
        self.last = None
        started = time.perf_counter()
        try:
            reply = await self.provider.generate(request, schema)
            self.last = {"input_tokens": reply.input_tokens, "output_tokens": reply.output_tokens,
                         "estimated_cost_usd": reply.estimated_cost_usd}
            return reply
        finally:
            if self.last is None:
                self.last = {"input_tokens": None, "output_tokens": None, "estimated_cost_usd": None}
            self.last["latency_ms"] = (time.perf_counter()-started)*1000


def request(text, reference_date, request_id):
    return Request(candidate=text, candidate_sha256=digest(text), reference_date=reference_date, request_id=request_id)


def fixtures(reference_date):
    # Explicit synthetic comparison clock; never claim a real source observation.
    clock = lambda: datetime.fromisoformat(reference_date).replace(hour=12, tzinfo=timezone.utc)
    pipeline, _ = scenario("A", clock=clock)
    return pipeline.sources, clock


def read_bounded(path):
    with Path(path).open("rb") as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise ValueError("file size limit")
    return data.decode("utf-8")


def analyzer(args, *, provider=None, fake_reply=None, reference_date="2026-11-14"):
    extractor, identity = None, args.engine
    if args.engine == "gemini":
        extractor = ModelExtractor(provider, provider.provider.settings.timeout_seconds)
        identity = provider.provider.settings.model
    elif args.engine == "fake-model":
        if fake_reply is None:
            raise ValueError("explicit fake reply required")
        extractor = ModelExtractor(FakeProvider(fake_reply))
        identity = "fake-adapter-not-model-quality"
    options = {}
    if args.shadow_fixtures:
        sources, clock = fixtures(reference_date)
        options = dict(shadow_sources=sources, clock=clock)
    return Analyzer(engine=args.engine, extractor=extractor, identity=identity,
                    work_seconds=60 if args.engine == "gemini" else 5,
                    measure=args.measure or args.engine == "gemini", **options)


def human(result):
    lines = [f"schema={result.schema_version}; authorization=false; semantic_completeness=NOT_PROVEN",
             f"sha256={result.request.candidate_sha256}; extractor={result.extractor}; status={result.overall_status}",
             f"coverage={result.coverage}; syntactic_characters={result.syntactic_covered_characters}"]
    lines.extend(f"claim {c.claim_id}: codepoints[{c.start}:{c.end}] {c.factuality}/{c.temporal}/{c.fresh_evidence}" for c in result.proposals)
    lines.extend(f"risk {u.unit_id}: codepoints[{u.start}:{u.end}] {u.kind}/{u.reason}" for u in result.risk_units)
    lines.extend(f"mapping {m.unit_id}: {m.policy_id} version={m.version}" for m in result.policy_mappings)
    lines.append("unaccounted=" + ",".join(result.unaccounted_unit_ids) + "; unsupported=" + ",".join(result.unsupported_unit_ids))
    lines.append(f"shadow={result.shadow_verdict}; fixture_only=true; failure={result.failure_code}")
    return "\n".join(lines)


async def analyze(args):
    text = read_bounded(args.text_file)
    record = request(text, args.reference_date, args.request_id)
    provider = MeasuredProvider(GeminiProvider.from_environment(1)) if args.engine == "gemini" else None
    engine = analyzer(args, provider=provider,
                      fake_reply=read_bounded(args.fake_reply) if args.fake_reply else None,
                      reference_date=args.reference_date)
    result = await engine.analyze(record)
    # JSON is an explicit source-containing CLI export. Human diagnostics omit text.
    print(result.model_dump_json(indent=2) if args.json else human(result))
    return 2 if result.overall_status == "ANALYSIS_FAILED" else 0


async def evaluate(args):
    cases = load(args.split, directory=args.dataset_dir, require_reviewed=args.require_human_reviewed)
    if args.case_ids:
        ids = args.case_ids.split(",")
        if len(ids) != len(set(ids)) or not set(ids) <= {c.case_id for c in cases}:
            raise ValueError("invalid selected cases")
        cases = [next(c for c in cases if c.case_id == case_id) for case_id in ids]
    provider = None
    if args.engine == "gemini":
        if not args.case_ids or not 1 <= len(cases) <= 10 or args.max_requests is None or not len(cases) <= args.max_requests <= 10:
            raise ValueError("explicit at most ten-case model diagnostic required")
        provider = MeasuredProvider(GeminiProvider.from_environment(args.max_requests))
    replies = {}
    if args.engine == "fake-model":
        if args.fake_replies is None or args.fake_replies.stat().st_size > 512*1024:
            raise ValueError("bounded explicit fake evaluation replies required")
        for line in args.fake_replies.read_bytes().splitlines():
            row = strict_json(line)
            if set(row) != {"case_id", "reply"} or row["case_id"] in replies:
                raise ValueError("invalid fake fixture set")
            replies[row["case_id"]] = row["reply"]
        if set(replies) != {c.case_id for c in cases}:
            raise ValueError("missing or extra fake replies")
    records, auditor_records, exports = [], [], []
    shared = analyzer(args, provider=provider) if args.engine != "fake-model" else None
    auditor = Analyzer(engine="auditor", measure=False)
    for case in cases:
        record = request(case.text, case.reference_date, case.case_id)
        # Reference-date differences cannot select endpoints or affect coverage.
        engine = shared or analyzer(args, fake_reply=replies[case.case_id], reference_date=case.reference_date)
        if args.shadow_fixtures and shared is not None:
            engine.shadow_sources, engine.clock = fixtures(case.reference_date)
        before_attempts = provider.provider.calls if provider else 0
        if provider:
            provider.last = None
        result = await engine.analyze(record)
        attempted = bool(provider and provider.provider.calls > before_attempts)
        independent = await auditor.analyze(record)
        records.append(dict(case=case, result=result))
        auditor_records.append(dict(case=case, result=independent))
        exports.append({"case_id": case.case_id, "source_sha256": case.source_sha256,
                        "analysis": result.model_dump(mode="json"),
                        "alignment_outcome": "VALIDATED" if result.extractor_status != "FAILED" else "FAILED" if result.diagnostic_stage is not None and result.diagnostic_stage.value in {"ALIGNMENT", "SOURCE_BINDING"} else "NOT_COMPLETED",
                        "model_call_attempted": attempted,
                        "provider_measurement": provider.last if attempted else None})
    implementation = Path(__file__).parent
    usage = [row["provider_measurement"] for row in exports if row["provider_measurement"] is not None]
    reported = [row for row in usage if row["input_tokens"] is not None and row["output_tokens"] is not None and row["estimated_cost_usd"] is not None]
    latency = [r["result"].resources.elapsed_ms for r in records if r["result"].resources.elapsed_ms is not None]
    report = {
        "schema_version": "004f.evaluation.v1", "engine": args.engine, "split": args.split,
        "authorization": False, "semantic_completeness": "NOT_PROVEN",
        "qualification": "FAKE_ADAPTER_ONLY" if args.engine == "fake-model" else "DRAFT_LABEL_MEASUREMENT" if any(c.review_status == "draft" for c in cases) else "HUMAN_REVIEWED_LABEL_MEASUREMENT",
        "model_quality_status": "MODEL QUALITY QUALIFICATION PENDING",
        "model_execution": "MEASURED_DIAGNOSTIC_ONLY" if provider and provider.provider.calls else "NOT_EXECUTED",
        "selected_case_ids": [c.case_id for c in cases],
        "dataset_sha256": file_hash(args.dataset_dir / f"{args.split}.jsonl"),
        "manifest_sha256": file_hash(args.dataset_dir / "manifest.json"),
        "implementation_sha256": {p.name: file_hash(p) for p in sorted(implementation.glob("*.py"))},
        "prompt_version": PROMPT_VERSION, "prompt_sha256": digest(SYSTEM),
        "identification_schema_sha256": digest(json.dumps(Identification.model_json_schema(), sort_keys=True)),
        "source_hashes": {c.case_id: c.source_sha256 for c in cases},
        "model_configuration": provider.provider.settings.model_dump() if provider else None,
        "model_attempts": provider.provider.calls if provider else 0,
        "reserved_planning_cost_usd": provider.provider.reserved_usd if provider else None,
        "analysis_latency_ms": {"median": statistics.median(latency), "max": max(latency)} if latency else None,
        "model_measurements": {
            "observed_calls": len(usage), "reported_usage_calls": len(reported),
            "input_tokens": sum(r["input_tokens"] for r in reported) if reported else None,
            "output_tokens_including_thoughts": sum(r["output_tokens"] for r in reported) if reported else None,
            "estimated_cost_usd_reported": sum(r["estimated_cost_usd"] for r in reported) if reported else None,
            "latency_ms": {"median": statistics.median(r["latency_ms"] for r in usage), "max": max(r["latency_ms"] for r in usage)} if usage else None,
            "scope": "reported subset at operator-supplied rates; failures may have unknown usage; not billing evidence",
        },
        "review_pending": sum(c.review_status == "draft" for c in cases),
        "metrics": {"extractor_only": score(records, audit_decisions=False),
                    "combined_extractor_and_auditor": score(records),
                    "independent_auditor": score(auditor_records)},
        "records": exports,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes((json.dumps(report, indent=2, ensure_ascii=True) + "\n").encode())
    metric = report["metrics"]["combined_extractor_and_auditor"]
    print(f"engine={args.engine}; cases={len(cases)}; draft_labels={report['review_pending']}; authorization=false")
    print(f"false_complete={metric['false_complete_count']}; dynamic_omitted={metric['dynamic_omitted']}; dynamic_nonfresh={metric['dynamic_incorrectly_nonfresh_or_nonfactual']}; extraction_failures={metric['extraction_failures']}")
    print("MODEL QUALITY QUALIFICATION PENDING")
    return 0


def main():
    parser = SafeParser(prog="verifier.prose", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("analyze", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--engine", choices=("baseline", "auditor", "fake-model", "gemini"), default="baseline")
        sub.add_argument("--shadow-fixtures", action="store_true")
        sub.add_argument("--measure", action="store_true")
        if name == "analyze":
            sub.add_argument("--text-file", type=Path, required=True)
            sub.add_argument("--reference-date", default="2026-11-14")
            sub.add_argument("--request-id", default="prose-cli")
            sub.add_argument("--fake-reply", type=Path)
            sub.add_argument("--json", action="store_true")
        else:
            sub.add_argument("--split", choices=("dev", "heldout"), default="dev")
            sub.add_argument("--dataset-dir", type=Path, default=DATA)
            sub.add_argument("--case-ids")
            sub.add_argument("--max-requests", type=int)
            sub.add_argument("--fake-replies", type=Path)
            sub.add_argument("--require-human-reviewed", action="store_true")
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return asyncio.run(analyze(args) if args.command == "analyze" else evaluate(args))
    except (AnalysisFailure, ValueError, TypeError, OSError, UnicodeError, RecursionError):
        print('{"status":"ANALYSIS_FAILED","reason":"INVALID_INPUT_OR_CONFIGURATION","authorization":false}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
