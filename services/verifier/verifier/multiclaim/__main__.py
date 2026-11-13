"""Offline CLI only. No environment-selected live sources or model calls."""

import argparse
import asyncio
import json
from pathlib import Path

from claim_analysis.schema import strict_json
from verifier.contract import SOURCE_URL

from .contract import PYPI_URL, Request
from .demo import FixtureSource, PYPI, PYTHON, run_demo
from .pipeline import Pipeline


async def run(args):
    if args.request:
        # Bounded read before JSON decoding; strict_json rejects duplicate keys/nonfinite values.
        with Path(args.request).open("rb") as stream:
            data = stream.read(65537)
        request = Request.model_validate(strict_json(data))
        pipeline = Pipeline(FixtureSource(SOURCE_URL, PYTHON), FixtureSource(PYPI_URL, PYPI), fixture=True)
        records = [("custom-fixture", await pipeline.verify(request))]
    else:
        records = [record async for record in run_demo()]
    for case, result in records:
        if args.json:
            print(json.dumps({"case": case, "result": result.model_dump(mode="json")}))
        else:
            print(f"{case}: {result.verdict}; coverage={result.coverage.status}/{result.coverage.reason_code}; "
                  f"claims={','.join(c.verdict for c in result.claims) or 'none'}; mode=fixture")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", help="004b.v1 JSON file; uses synthetic demo evidence only")
    parser.add_argument("--json", action="store_true", help="emit full typed records, including supplied candidate")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, TypeError, OSError, RecursionError):
        parser.exit(2, "004B input rejected\n")


if __name__ == "__main__":
    main()
