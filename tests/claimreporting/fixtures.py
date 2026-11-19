import copy
from datetime import datetime, timedelta, timezone
from verifier.bounded_prose.pipeline import Pipeline
from verifier.bounded_prose.contract import Request
from verifier.multiclaim.pipeline import Pipeline as EvidencePipeline
from verifier.multiclaim.demo import FixtureSource, PYTHON, PYPI
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import PYPI_URL
from verifier.policy import digest
from verifier.retrieval import Page

TIME = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
PY = "Python.org currently lists Python 3.88.7 as its latest stable Windows release."
PI = "PyPI reports requests version 2.88.7."

# name, original fixture text, fault, expected protected decision, scores, reasons
CASES = [
    ("python-supported", PY, "none", "ALLOW", [100], ["MATCHED_OBSERVATION"]),
    ("python-older", PY.replace("3.88.7", "3.88.6"), "none", "REJECT", [0], ["OLDER_THAN_OBSERVATION"]),
    ("pypi-supported", PI, "none", "ALLOW", [100], ["MATCHED_OBSERVATION"]),
    ("pypi-older", PI.replace("2.88.7", "2.88.6"), "none", "REJECT", [0], ["OLDER_THAN_OBSERVATION"]),
    ("two-supported", PY+"\n"+PI, "none", "ALLOW", [100,100], ["MATCHED_OBSERVATION"]*2),
    ("mixed-contradiction", PY+"\n"+PI.replace("2.88.7", "2.88.6"), "none", "REJECT", [100,0], ["MATCHED_OBSERVATION","OLDER_THAN_OBSERVATION"]),
    ("ahead", PI.replace("2.88.7", "2.88.8"), "none", "UNAVAILABLE", [None], ["CLAIM_AHEAD_OF_SOURCE"]),
    ("malformed-evidence", PI, "malformed", "UNAVAILABLE", [None], ["INSUFFICIENT_EVIDENCE"]),
    ("unavailable-evidence", PY, "unavailable", "UNAVAILABLE", [None], ["RETRIEVAL_FAILURE"]),
    ("expired-source", PY, "expired", "UNAVAILABLE", [None], ["STALE_OBSERVATION"]),
    ("missing-source", PI, "identity", "UNAVAILABLE", [None], ["RETRIEVAL_FAILURE"]),
    ("wrong-source-mode", PI, "mode", "UNAVAILABLE", [None], ["RETRIEVAL_FAILURE"]),
    ("paraphrase", "The newest stable Python for Windows is version 3.88.7.", "none", "UNAVAILABLE", [], []),
    ("neighbor", PY+" The Moon is made of cheese.", "none", "UNAVAILABLE", [], []),
    ("reordered-input", PI+"\t"+PY, "none", "ALLOW", [100,100], ["MATCHED_OBSERVATION"]*2),
    ("reordered-mappings", PY+"\n"+PI, "map-order", "UNAVAILABLE", [None,None], ["INVALID_RECORD"]*2),
    ("missing-mapping", PY, "map-missing", "UNAVAILABLE", [None], ["INVALID_RECORD"]),
    ("malformed-mapping", PY, "map-offset", "UNAVAILABLE", [None], ["INVALID_RECORD"]),
    ("wrong-original-digest", PY, "hash", "UNAVAILABLE", [], []),
    ("wrong-evidence-digest", PY, "evidence-hash", "UNAVAILABLE", [None], ["INVALID_RECORD"]),
    ("expired-bound-evidence", PY, "bound-expired", "UNAVAILABLE", [None], ["STALE_OBSERVATION"]),
    ("ambiguous-source", PY, "ambiguous", "UNAVAILABLE", [None], ["AMBIGUOUS_EVIDENCE"]),
    # Same frozen text; 005D-S corrects its formerly admitted repeated policy.
    ("eight-claims", "\n".join([PY.replace("3.88.7", "3.88."+str(i)) for i in range(7,-1,-1)]), "none", "UNAVAILABLE", [], []),
]


async def snapshot(text, fault):
    python = FixtureSource(SOURCE_URL, PYTHON, clock=lambda: TIME)
    pypi = FixtureSource(PYPI_URL, PYPI, clock=lambda: TIME)
    if fault == "malformed": pypi.content = "not JSON"
    if fault == "unavailable": python.unavailable = True
    if fault == "expired": python.clock = lambda: TIME-timedelta(seconds=61)
    if fault == "identity": pypi.url = "https://unexpected.invalid/"
    if fault == "ambiguous": python.content += "Latest Python 3 Release - Python 3.88.8\n"
    if fault == "mode":
        async def wrong(): return Page(PYPI_URL, PYPI, TIME, "offline-fixture", "pypi_live")
        pypi.retrieve = wrong
    pipeline = Pipeline(EvidencePipeline(python, pypi, fixture=True, clock=lambda: TIME))
    result = await pipeline.verify(Request(request_id="005d-offline", candidate=text, candidate_sha256=digest(text)))
    value = result.model_dump(mode="json")
    if fault == "map-order": value["mappings"].reverse()
    if fault == "map-missing": value["mappings"] = []
    if fault == "map-offset": value["mappings"][0]["start"] = 1
    if fault == "hash": value["candidate_sha256"] = "0"*64
    if fault == "evidence-hash": value["verification"]["claims"][0]["evidence"][0]["content_sha256"] = "0"*64
    if fault == "bound-expired":
        e = value["verification"]["claims"][0]["evidence"][0]
        e["observed_at"] = e["retrieved_at"] = (TIME-timedelta(seconds=61)).isoformat()
        value["verification"]["verdict"] = "INSUFFICIENT"
    return value, copy.deepcopy(result.model_dump(mode="json"))
