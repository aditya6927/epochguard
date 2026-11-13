"""Optional single-source observation probe. No retries, model or gateway calls."""

import argparse
import asyncio
from datetime import datetime, timezone
import os

from verifier.policy import primary_label
from verifier.retrieval import TavilyRetriever
from verifier.settings import TimeoutSettings

from .policies import pypi_version, reference, validate_page
from .retrieval import PyPIRetriever


async def observe(source):
    if os.getenv("EPOCHGUARD_RUN_LIVE_004B") != "1":
        raise ValueError("live opt-in required")
    python = source == "python"
    # Never permit a test endpoint to masquerade as a live source.
    if python and (os.getenv("EPOCHGUARD_TEST_TAVILY_ENDPOINT") or os.getenv("EPOCHGUARD_TEST_MODE")):
        raise ValueError("live test override forbidden")
    retriever = (TavilyRetriever(api_key=os.getenv("TAVILY_API_KEY", ""), timeouts=TimeoutSettings(
        tavily_api_seconds=19, retrieval_seconds=20, verification_seconds=22)) if python else
        PyPIRetriever(timeout_seconds=4))
    async with asyncio.timeout(22 if python else 5):
        page = validate_page(await retriever.retrieve(), python=python, fixture=False)
        if not -2 <= (datetime.now(timezone.utc) - page.retrieved_at).total_seconds() <= 60:
            raise ValueError("stale observation")
        version = primary_label(page.content)[0] if python else pypi_version(page.content)
        return reference(page, version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["python", "pypi"], required=True)
    args = parser.parse_args()
    try:
        record = asyncio.run(observe(args.source))
    except Exception:
        parser.exit(2, "004B source observation unavailable\n")
    print(record.model_dump_json())


if __name__ == "__main__":
    main()
