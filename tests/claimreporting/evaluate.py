"""Reproduce fixed synthetic 005D reports, never network or live evidence."""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"tests"), str(ROOT/"services/verifier"), str(ROOT/"services/claim_analysis")]
from claimreporting.fixtures import CASES, TIME, snapshot
from verifier.claim_report import from_result
from verifier.claim_report.presentation import render


async def evaluate(directory):
    directory.mkdir(parents=True, exist_ok=False)
    reports = []
    for name, text, fault, outcome, scores, reasons in CASES:
        value, _ = await snapshot(text, fault)
        report = from_result(value, profile="fixture", generated_at=TIME)
        assert [c.freshness_score for c in report.claims] == scores, name
        assert [c.score_reason for c in report.claims] == reasons, name
        (directory/(name+".json")).write_text(report.model_dump_json(indent=2)+"\n", encoding="utf-8")
        (directory/(name+".html")).write_text(render(report), encoding="utf-8")
        reports.append({"case": name, "expected_protected_outcome": outcome, "scores": scores, "reasons": reasons})
    (directory/"evaluation.json").write_text(json.dumps({"fixture": True, "authorization": False, "cases": reports}, indent=2)+"\n", encoding="utf-8")
    print("005D fixed offline reporting cases passed:",len(reports))


if __name__ == "__main__":
    try:
        asyncio.run(evaluate(Path(sys.argv[1])))
    except Exception:
        raise SystemExit("005D evaluation unavailable; no external calls performed") from None
