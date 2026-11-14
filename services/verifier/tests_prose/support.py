import asyncio
import json

from claim_analysis.model import FakeProvider, ModelExtractor
from verifier.prose.cli import request
from verifier.prose.pipeline import Analyzer

PYTHON = "Python.org lists Python 3.88.7 as its latest stable Windows release."
PYPI = "PyPI reports requests version 2.88.7."


def reply(quotes, *, factuality="FACTUAL", temporal="DYNAMIC", fresh="REQUIRED", normalized=None):
    return json.dumps({"schema_version": "004a.identification.v1", "claims": [
        {"claim_id": f"c{i:03d}", "source_text": quote, "normalized_proposition": normalized,
         "factuality": factuality, "temporal": temporal, "fresh_evidence": fresh,
         "uncertainty": [], "temporal_reference": None} for i, quote in enumerate(quotes, 1)]})


def analyze(text, quotes, **kwargs):
    extractor = ModelExtractor(FakeProvider(reply(quotes, **kwargs)))
    result = asyncio.run(Analyzer(engine="fake-model", extractor=extractor).analyze(request(text, "2026-11-14", "offline")))
    assert result.authorization is False and result.semantic_completeness == "NOT_PROVEN"
    return result
