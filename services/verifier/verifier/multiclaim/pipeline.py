"""Bounded non-authorizing API and pure whole-response aggregation."""

import asyncio
from datetime import datetime, timezone

from claim_analysis.schema import AnalysisInput, Extraction

from .contract import BoundClaim, ClaimResult, Coverage, Request, Result, PYTHON_POLICY, PYPI_POLICY
from .coverage import qualify, uncertain
from .policies import insufficient, verify_claim
from verifier.policy import digest


def agrees(extraction, required):
    fields = ("claim_id", "source_text", "start", "end", "factuality", "temporal", "fresh_evidence")
    return len(extraction.claims) == len(required) and all(
        all(getattr(actual, key) == getattr(expected.source, key) for key in fields)
        for actual, expected in zip(extraction.claims, required))


def aggregate(required: list[BoundClaim], results: list[ClaimResult], coverage: Coverage, checked_at: datetime):
    """Only independently validated contradictions take precedence over missing neighbors.

    Invalid result sets (duplicate/order/binding/schema) invalidate the whole set.
    Missing results cannot pass but do not erase a valid, independent contradiction.
    A failed extraction/coverage boundary produces INSUFFICIENT before any comparison.
    """
    try:
        coverage = Coverage.model_validate(coverage.model_dump(warnings=False))
        required = [BoundClaim.model_validate(c.model_dump(warnings=False)) for c in required]
        results = [ClaimResult.model_validate(r.model_dump(warnings=False)) for r in results]
        ids = [c.source.claim_id for c in required]
        if coverage.status != "COMPLETE" or not required or ids != coverage.required_claim_ids:
            return "INSUFFICIENT"
        positions = []
        for result in results:
            index = ids.index(result.claim.source.claim_id)
            if result.claim != required[index]:
                return "INSUFFICIENT"
            positions.append(index)
            for evidence in result.evidence:
                if not -2 <= (checked_at - evidence.observed_at).total_seconds() <= 60:
                    return "INSUFFICIENT"
        if positions != sorted(set(positions)):
            return "INSUFFICIENT"
        if any(r.verdict == "CONTRADICTED" for r in results):
            return "CONTRADICTED"
        if len(results) == len(required) and all(r.verdict == "SUPPORTED" for r in results):
            return "SUPPORTED"
    except (ValueError, TypeError, AttributeError):
        pass
    return "INSUFFICIENT"


class Pipeline:
    """One instance per event loop; callers own its two trusted retrievers.

    Admission is immediate and bounded (no unbounded waiter queue). Claim work is
    sequential per request: at most max_requests simultaneous retrievals overall.
    The shared work deadline includes extraction and every evidence operation.
    """
    def __init__(self, python_source, pypi_source, *, fixture=False, max_requests=4,
                 work_seconds=5.0, retrieval_seconds=4.0, clock=lambda: datetime.now(timezone.utc)):
        if type(max_requests) is not int or not 1 <= max_requests <= 16:
            raise ValueError("invalid concurrency limit")
        if not 0.01 <= retrieval_seconds <= work_seconds <= 60:
            raise ValueError("invalid deadlines")
        self.sources = {PYTHON_POLICY: python_source, PYPI_POLICY: pypi_source}
        self.fixture, self.max_requests = fixture, max_requests
        self.work_seconds, self.retrieval_seconds, self.clock = work_seconds, retrieval_seconds, clock
        self._active = 0

    async def verify(self, request: Request, *, extractor=None) -> Result:
        # Revalidation defeats mutated nested models/model_copy bypasses at the public API.
        request = Request.model_validate(request.model_dump(warnings=False))
        required, coverage = qualify(request.candidate)
        extraction, extraction_status, binding_status = None, "NOT_RUN", "NOT_RUN"
        results = []

        def finish():
            checked_at = self.clock()
            return Result(request_id=request.request_id, candidate=request.candidate,
                          candidate_sha256=request.candidate_sha256, extraction=extraction,
                          extraction_status=extraction_status, binding_status=binding_status,
                          coverage=coverage, claims=results,
                          verdict=aggregate(required, results, coverage, checked_at), checked_at=checked_at)

        if digest(request.candidate) != request.candidate_sha256:
            coverage = uncertain("HASH_MISMATCH")
            return finish()
        if coverage.status != "COMPLETE":
            return finish()
        if self._active >= self.max_requests:
            results = []
            # Keep complete grammar evidence but mark every required claim unavailable below.
            extraction = Extraction(schema_version="004a.v1", claims=[c.source for c in required])
            extraction_status, binding_status = "TRUSTED_GRAMMAR", "VALID"
            results = [insufficient(c, "VERIFIER_ERROR") for c in required]
            return finish()
        self._active += 1
        try:
            async with asyncio.timeout(self.work_seconds):
                analysis = AnalysisInput(text=request.candidate, reference_date=self.clock().date().isoformat())
                try:
                    if extractor is not None and request.extraction is not None:
                        raise ValueError("ambiguous extraction input")
                    if extractor is not None:
                        extraction, _ = await extractor.analyze(analysis)
                        if extraction is None:
                            raise ValueError("missing extraction")
                    else:
                        extraction = request.extraction
                    if extraction is None:
                        extraction = Extraction(schema_version="004a.v1", claims=[c.source for c in required])
                        extraction_status = "TRUSTED_GRAMMAR"
                    else:
                        extraction = Extraction.model_validate(extraction.model_dump(warnings=False))
                        extraction_status = "VALIDATED"
                except Exception:
                    extraction, extraction_status = None, "FAILED"
                    coverage = uncertain("EXTRACTION_FAILURE")
                    return finish()
                try:
                    extraction.bind(analysis)
                    binding_status = "VALID"
                except Exception:
                    extraction, binding_status = None, "FAILED"
                    coverage = uncertain("SOURCE_BINDING_FAILURE")
                    return finish()
                if not agrees(extraction, required):
                    coverage = uncertain("EXTRACTION_CONFLICT")
                    return finish()
                for claim in required:
                    try:
                        async with asyncio.timeout(self.retrieval_seconds):
                            result = await verify_claim(claim, self.sources[claim.policy_id],
                                                        request_id=request.request_id, fixture=self.fixture,
                                                        clock=self.clock)
                    except TimeoutError:
                        result = insufficient(claim, "RETRIEVAL_TIMEOUT")
                    except Exception:
                        result = insufficient(claim, "VERIFIER_ERROR")
                    results.append(result)
        except TimeoutError:
            if extraction is None:
                extraction_status, coverage = "FAILED", uncertain("EXTRACTION_FAILURE")
            else:
                results.extend(insufficient(c, "RETRIEVAL_TIMEOUT") for c in required[len(results):])
        finally:
            self._active -= 1
        return finish()
