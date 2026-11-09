"""Reproducible draft-set evaluation and stand-alone analysis, never a verdict."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

from . import baseline
from .dataset import DATA, load
from .evaluation import score
from .gemini import GeminiProvider
from .model import AnalysisFailure, FakeProvider, ModelExtractor, PROMPT_VERSION, SYSTEM
from .schema import AnalysisInput, MAX_JSON, strict_json


def digest(data):
    return hashlib.sha256(data).hexdigest()


def summary(report):
    def fmt(value):
        return "n/a" if value is None else f"{value:.3f}"
    lines = [f"Engine: {report['engine']}; split: {report['split']}; independent human review pending: {report['review_pending']}",
             f"Quality qualification: {report['qualification']}"]
    for group in ("all", "mixed", "adversarial"):
        s = report["metrics"][group]
        lines.append(f"{group}: responses={s['responses']}; claim P/R/F1={fmt(s['claim']['precision'])}/{fmt(s['claim']['recall'])}/{fmt(s['claim']['f1'])}; temporal macro-F1={fmt(s['temporal_macro_f1'])}; fresh P/R={fmt(s['fresh_evidence']['precision'])}/{fmt(s['fresh_evidence']['recall'])}; dynamic omissions={s['critical_misses']['omitted']}; dynamic nonfresh={s['critical_misses']['labeled_nonfresh']}; failures={s['analysis_failures_or_invalid_outcomes']}")
    return "\n".join(lines) + "\n"


async def evaluate(args):
    path = args.dataset or DATA / f"{args.split}.jsonl"
    cases = load(path, require_reviewed=args.require_human_reviewed)
    if any(c.split != args.split for c in cases):
        raise ValueError("dataset split mismatch")
    provider, replies = None, {}
    if args.engine == "gemini":
        provider = GeminiProvider.from_environment(args.max_requests)
        if sum(c.expected_outcome == "ANALYZED" and bool(c.text.strip()) for c in cases) > provider.settings.max_requests:
            raise AnalysisFailure("INSUFFICIENT_REQUEST_BUDGET_FOR_DATASET")
    elif args.engine == "fake":
        if args.fake_replies is None:
            raise ValueError("fake evaluation requires explicit fixture replies; never fabricate model quality")
        for line in args.fake_replies.read_bytes().splitlines():
            reply = strict_json(line)
            if set(reply) != {"case_id", "reply"} or reply["case_id"] in replies:
                raise ValueError("invalid fake reply record")
            replies[reply["case_id"]] = reply["reply"]
    records = []
    for case in cases:
        start = time.perf_counter()
        result, reply, status, reason = None, None, "ANALYZED", None
        failure_details = None
        try:
            request = AnalysisInput(text=case.text, reference_date=case.reference_date)
        except ValueError:
            status, reason = "INVALID_INPUT", "INVALID_INPUT"
        else:
            try:
                if args.engine == "baseline":
                    result = baseline.analyze(request)
                else:
                    source = provider if provider is not None else FakeProvider(replies.get(case.case_id, "{}"))
                    timeout = provider.settings.timeout_seconds if provider is not None else 30
                    result, reply = await ModelExtractor(source, timeout).analyze(request)
            except AnalysisFailure as failure:
                status, reason = "ANALYSIS_FAILED", str(failure)
                failure_details = failure.diagnostic.to_dict() if failure.diagnostic is not None else None
            except ValueError:
                status, reason = "ANALYSIS_FAILED", "BASELINE_LIMIT_EXCEEDED"
        records.append(dict(case=case, extraction=result, status=status, reason=reason, failure_details=failure_details,
                            latency_ms=(time.perf_counter()-start)*1000,
                            input_tokens=reply.input_tokens if reply else None,
                            output_tokens=reply.output_tokens if reply else None,
                            estimated_cost_usd=reply.estimated_cost_usd if reply else None))
    source_root = Path(__file__).parent
    pending = sum(c.review_status != "human_reviewed" for c in cases)
    report = {
        "report_schema":"004a.evaluation.v1", "engine":args.engine, "split":args.split,
        "qualification":"fake-adapter plumbing only" if args.engine == "fake" else "draft-label measurement; not human-reviewed quality" if pending else "measured against human-reviewed annotations",
        "review_pending":pending,
        "model_performance_pending":args.engine != "gemini" or not any(r["status"] == "ANALYZED" and r["extraction"] and r["case"].text.strip() for r in records),
        "dataset_sha256":digest(path.read_bytes()), "reference_dates":sorted({c.reference_date for c in cases}),
        "prompt_version":PROMPT_VERSION, "prompt_sha256":digest(SYSTEM.encode()),
        "implementation_sha256":{n:digest((source_root/n).read_bytes()) for n in ("baseline.py","schema.py","evaluation.py","model.py","gemini.py","dataset.py","cli.py")},
        "matching":"greedy greatest character IoU >= 0.5, ties gold/pred index, one-to-one, no fractional credit; exact metrics >= 1.0",
        "model_configuration":provider.settings.model_dump() if provider else None,
        "model_attempts":provider.calls if provider else 0,
        "reserved_planning_cost_usd":provider.reserved_usd if provider else None,
        "metrics":{
            "all":score(records),
            "mixed":score([r for r in records if any(t in r["case"].tags for t in ("mixed","multi_claim","mixed_scope"))]),
            "adversarial":score([r for r in records if "adversarial" in r["case"].tags])},
        "records":[{**{k:v for k,v in r.items() if k not in {"case","extraction"}},
                    "case_id":r["case"].case_id,"extraction":r["extraction"].model_dump() if r["extraction"] else None} for r in records]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
    args.output.with_suffix(".txt").write_text(summary(report), encoding="utf-8")
    print(summary(report), end="")
    return 0


async def analyze(args):
    raw = args.text_file.read_bytes()
    if len(raw) > MAX_JSON:
        raise ValueError("input file bound exceeded")
    request = AnalysisInput(text=raw.decode("utf-8"), reference_date=args.reference_date)
    if args.engine == "baseline":
        result = baseline.analyze(request)
    elif args.engine == "gemini":
        source = GeminiProvider.from_environment(1)
        result, _ = await ModelExtractor(source, source.settings.timeout_seconds).analyze(request)
    else:
        if args.fake_reply is None:
            raise ValueError("explicit fake output required")
        result, _ = await ModelExtractor(FakeProvider(args.fake_reply.read_text(encoding="utf-8"))).analyze(request)
    print(json.dumps({"status":"ANALYZED", "engine":args.engine,"authorization":False,
                      "analysis":result.model_dump()}, ensure_ascii=True, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("--engine", choices=("baseline","gemini","fake"), default="baseline")
    evaluation.add_argument("--split", choices=("dev","heldout"), default="heldout")
    evaluation.add_argument("--dataset", type=Path)
    evaluation.add_argument("--output", type=Path, required=True)
    evaluation.add_argument("--max-requests", type=int, default=1)
    evaluation.add_argument("--fake-replies", type=Path)
    evaluation.add_argument("--require-human-reviewed", action="store_true")
    analysis = commands.add_parser("analyze")
    analysis.add_argument("--engine", choices=("baseline","gemini","fake"), default="baseline")
    analysis.add_argument("--text-file", type=Path, required=True)
    analysis.add_argument("--reference-date", default="2026-11-08")
    analysis.add_argument("--fake-reply", type=Path)
    args = parser.parse_args()
    try:
        return asyncio.run(evaluate(args) if args.command == "evaluate" else analyze(args))
    except AnalysisFailure as failure:
        print(json.dumps({"status":"ANALYSIS_FAILED","reason":str(failure),"authorization":False}), file=sys.stderr)
    except (ValueError, OSError):
        print(json.dumps({"status":"ANALYSIS_FAILED","reason":"INVALID_INPUT_OR_CONFIGURATION","authorization":False}), file=sys.stderr)
    return 2
