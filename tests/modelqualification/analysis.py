"""005C review packet evaluation using the existing 004A/004F implementation."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Literal
from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "services/verifier"), str(ROOT / "services/claim_analysis")]
from claim_analysis.alignment import Identification
from claim_analysis.gemini import GeminiProvider, ModelSettings
from claim_analysis.model import ModelExtractor, PROMPT_VERSION, SYSTEM
from claim_analysis.schema import strict_json
from verifier.prose.cli import MeasuredProvider, request
from verifier.prose.dataset import Case, file_hash
from verifier.prose.evaluation import score
from verifier.prose.pipeline import Analyzer
from claim_analysis.evaluation import match_spans, ratio
from modelqualification.common import SafeParser, sha, write_new

PACKET = ROOT / "tests/modelqualification/data/review-packet.v1.json"


class ReviewCase(Case):
    dataset_version: Literal["005c.dataset.v1"]
    case_id: str = Field(pattern=r"^eg005c-[0-9]{4}$")


def load_packet(path=PACKET, require_reviewed=False):
    data = Path(path).read_bytes()
    if len(data) > 256*1024:
        raise ValueError("packet bound")
    packet = strict_json(data)
    if packet["schema_version"] != "005c.review-packet.v1" or packet["annotation_provenance"] != "agent-authored synthetic drafts; independent review pending":
        raise ValueError("packet provenance")
    manifest = strict_json(Path(path).with_name("manifest.v1.json").read_bytes())
    if manifest["packet_sha256"] != sha(data.replace(b"\r\n", b"\n")):
        raise ValueError("frozen review packet changed; version and review provenance required")
    cases = [ReviewCase.model_validate_json(json.dumps(c)) for c in packet["cases"]]
    if not 1 <= len(cases) <= 24 or len({c.case_id for c in cases}) != len(cases):
        raise ValueError("packet membership")
    if require_reviewed and any(c.review_status != "human_reviewed" for c in cases):
        raise ValueError("independent human review pending")
    return cases


async def evaluate(cases, *, provider=None, real_execution=False):
    if real_execution and (provider is None or provider._transport is not None):
        raise ValueError("real execution requires unchanged live transport")
    measured = MeasuredProvider(provider) if provider is not None else None
    engines = {"deterministic_004a": Analyzer(engine="baseline", measure=False),
               "independent_004f_auditor": Analyzer(engine="auditor", measure=False)}
    if measured:
        engines["gemini"] = Analyzer(engine="gemini", extractor=ModelExtractor(measured, provider.settings.timeout_seconds),
                                     identity=provider.settings.model, work_seconds=60)
    records = {k: [] for k in engines}
    exports = []
    started = time.monotonic()
    for case in cases:
        row = {"case_id": case.case_id, "source_sha256": case.source_sha256, "engines": {}}
        for name, engine in engines.items():
            if name == "gemini":
                measured.last = None
            before = provider.calls if provider else 0
            # Entire response enters unchanged, including injections and repeated
            # spans. No independent sentence selection or fallback extractor.
            result = await engine.analyze(request(case.text, case.reference_date, case.case_id))
            records[name].append({"case": case, "result": result})
            row["engines"][name] = {
                "status": result.overall_status, "failure": result.failure_code,
                "diagnostic_stage": result.diagnostic_stage.value if result.diagnostic_stage else None,
                "diagnostic_code": result.diagnostic_code.value if result.diagnostic_code else None,
                "coverage": result.coverage, "unaccounted_units": list(result.unaccounted_unit_ids),
                "unsupported_units": list(result.unsupported_unit_ids),
                "proposals": [{"start": p.start, "end": p.end, "factuality": p.factuality, "temporal": p.temporal,
                               "fresh_evidence": p.fresh_evidence, "uncertainty": list(p.uncertainty)} for p in result.proposals],
                "model_call_attempted": bool(provider and provider.calls > before),
                "provider_measurement": measured.last if name == "gemini" else None,
            }
        exports.append(row)
    comparison = {
        "deterministic_004a": score(records["deterministic_004a"], audit_decisions=False),
        "independent_004f_auditor": score(records["independent_004f_auditor"]),
        "gemini_alone": score(records["gemini"], audit_decisions=False) if measured else None,
        "gemini_with_auditor": score(records["gemini"]) if measured else None,
    }
    for metric in comparison.values():
        if metric is not None:
            metric["dynamic_claim_recall"] = ratio(metric["dynamic_gold"] - metric["dynamic_omitted"] - metric["dynamic_incorrectly_nonfresh_or_nonfactual"], metric["dynamic_gold"])
    # All source annotations, including stable/history/nonfactual/uncertain,
    # contribute explicit classification denominators. Failed analyses score
    # zero correct; exact source matching is separately reported above.
    for name, rows in records.items():
        correct, denominator, omissions = 0, 0, []
        for row in rows:
            case, result = row["case"], row["result"]
            gold = [g.source for g in case.gold]
            pairs = dict(match_spans(gold, result.proposals))
            denominator += len(gold)
            for i, g in enumerate(gold):
                p = result.proposals[pairs[i]] if i in pairs else None
                correct += bool(p and (p.factuality, p.temporal, p.fresh_evidence) == (g.factuality, g.temporal, g.fresh_evidence))
                if p is None:
                    omissions.append({"case_id": case.case_id, "claim_id": g.claim_id})
        keys = ["gemini_alone", "gemini_with_auditor"] if name == "gemini" else [name]
        for key in keys:
            comparison[key]["classification"] = {"correct": correct, "denominator": denominator, "accuracy": ratio(correct, denominator)}
            comparison[key]["all_omissions"] = omissions
    usage = [r["engines"]["gemini"]["provider_measurement"] for r in exports if "gemini" in r["engines"] and r["engines"]["gemini"]["model_call_attempted"]]
    return {"schema_version": "005c.analysis-evaluation.v1", "authorization": False,
            "semantic_completeness": "NOT_PROVEN", "model_quality": "PENDING INDEPENDENT HUMAN REVIEW",
            "model_execution": ("REAL GEMINI DIAGNOSTIC" if real_execution else "MOCK TRANSPORT DIAGNOSTIC") if measured else "PENDING OPERATOR RUN",
            "annotation_provenance": "agent-authored synthetic drafts; independent review pending",
            "review_pending": sum(c.review_status == "draft" for c in cases), "denominator": len(cases),
            "comparison": comparison, "missing_measurements": [] if measured else ["gemini_alone", "gemini_with_auditor", "model latency, usage and cost"],
            "model_attempts": provider.calls if provider else 0, "reserved_planning_usd": provider.reserved_usd if provider else None,
            "usage": usage, "usage_scope": "per-attempt reported subset; null is unknown; estimates are not invoices",
            "elapsed_ms": round((time.monotonic()-started)*1000, 3), "cases": exports}


def live_provider(settings_path, secret_path, maximum):
    if os.getenv("EPOCHGUARD_RUN_ANALYSIS_005C") != "1" or os.getenv("EPOCHGUARD_ALLOW_MODEL_CALLS") != "1":
        raise ValueError("separate analysis authorization required")
    path = Path(secret_path).resolve(strict=True)
    if path.is_relative_to(ROOT):
        raise ValueError("private credential required outside repository")
    with path.open("rb") as stream:
        data = stream.read(259)
    if len(data) > 258:
        raise ValueError("credential bound")
    settings = ModelSettings.model_validate(strict_json(Path(settings_path).read_bytes()))
    if settings.max_requests != maximum or not 1 <= maximum <= 24:
        raise ValueError("explicit bounded request count required")
    return GeminiProvider(settings, data.decode("ascii").rstrip("\r\n"))


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--settings", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--require-human-reviewed", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not args.output.resolve().is_relative_to(ROOT / "artifacts/005c"):
            raise ValueError("ignored output directory required")
        if args.output.exists():
            raise ValueError("output already exists; preserve earlier evidence")
        cases = load_packet(require_reviewed=args.require_human_reviewed)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        provider = live_provider(args.settings, args.secret_file, args.max_requests) if args.live else None
        report = asyncio.run(evaluate(cases, provider=provider, real_execution=args.live))
        report.update(source_revision=revision,
                      dataset_sha256=file_hash(PACKET), prompt_version=PROMPT_VERSION, prompt_sha256=sha(SYSTEM),
                      identification_schema="004a.identification.v1",
                      identification_schema_sha256=sha(json.dumps(Identification.model_json_schema(), sort_keys=True)),
                      model_configuration=provider.settings.model_dump() if provider else None,
                      implementation_sha256={str(p.relative_to(ROOT)).replace("\\", "/"): file_hash(p) for d in
                          (ROOT / "tests/modelqualification", ROOT / "services/claim_analysis/claim_analysis", ROOT / "services/verifier/verifier/prose") for p in sorted(d.glob("*.py"))})
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_new(args.output, report)
        print(f"005C analysis: {len(cases)} cases; attempts={report['model_attempts']}; draft labels={report['review_pending']}; authorization=false")
    except Exception:
        parser.exit(1, "005C analysis unavailable; details withheld; no automatic retry\n")


if __name__ == "__main__":
    main()
