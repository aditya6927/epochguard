"""Separate live composition, never selected by the offline image or profile.

Reuses the explicitly opted-in 004E credential/profile boundary as well as a
second 004G opt-in. No live qualification driver is provided in this milestone.
"""
import os
from verifier.retrieval import TavilyRetriever
from verifier.multiclaim.retrieval import PyPIRetriever
from verifier.multiclaim.deployment import live_key, BudgetedSource, TAVILY, WORK_SECONDS, PYPI_SECONDS
from verifier.multiclaim.pipeline import Pipeline as EvidencePipeline
from .pipeline import Pipeline
from .app import create_app


def live_app():
    if os.getenv("EPOCHGUARD_RUN_LIVE_004G") != "1":
        raise ValueError("004G live opt-in required")
    # live_key requires the existing 004E opt-in, fixed live profile, bounded
    # runtime key file and absence of source/timeout/fixture overrides.
    key = live_key()
    python = BudgetedSource(TavilyRetriever(api_key=key, timeouts=TAVILY), "python")
    pypi = BudgetedSource(PyPIRetriever(timeout_seconds=PYPI_SECONDS), "pypi")
    return create_app(Pipeline(EvidencePipeline(python, pypi, fixture=False,
        max_requests=1, work_seconds=WORK_SECONDS, retrieval_seconds=20.5)))
