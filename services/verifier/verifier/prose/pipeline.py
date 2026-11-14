"""Request-owned analysis. No gateway import, source egress or release decision."""

import asyncio
from datetime import datetime, timezone
import math
import time

from claim_analysis import baseline
from claim_analysis.model import AnalysisFailure, ModelExtractor, ModelReply
from claim_analysis.schema import AnalysisInput, Claim, Extraction
from verifier.multiclaim.coverage import qualify
from verifier.multiclaim.contract import ClaimResult
from verifier.multiclaim.policies import verify_claim
from verifier.multiclaim.demo import FixtureSource

from .audit import derive, shadow_status, units
from .schema import Proposal, Request, Resources, Result, ShadowObservation


def independent_proposals(request):
    claims = []
    for unit in units(request.text):
        if unit.kind not in {"KNOWN_FACT", "NONFACTUAL_RULE"}:
            continue
        factual = unit.kind == "KNOWN_FACT"
        claims.append(Claim(claim_id=f"c{len(claims)+1:03d}", source_text=unit.source_text,
                            start=unit.start, end=unit.end, normalized_proposition=None,
                            factuality="FACTUAL" if factual else "NON_FACTUAL",
                            temporal="DYNAMIC" if factual else "UNCERTAIN",
                            fresh_evidence="REQUIRED" if factual else "NOT_APPLICABLE",
                            uncertainty=[], temporal_reference=None))
    return Extraction(schema_version="004a.v1", claims=claims).bind(request)


class Analyzer:
    def __init__(self, *, engine="baseline", extractor=None, identity=None,
                 work_seconds=5.0, max_active=1, measure=True, shadow_sources=None,
                 clock=lambda: datetime.now(timezone.utc)):
        if engine not in {"baseline", "auditor", "fake-model", "gemini"} or ((engine in {"fake-model", "gemini"}) != isinstance(extractor, ModelExtractor)) or (engine in {"baseline", "auditor"} and extractor is not None):
            raise ValueError("invalid extractor configuration")
        if type(max_active) is not int or not 1 <= max_active <= 4 or type(work_seconds) not in {int, float} or not math.isfinite(work_seconds) or not .1 <= work_seconds <= 60:
            raise ValueError("invalid analysis bounds")
        if shadow_sources is not None and set(shadow_sources) != {"python-windows-latest-v1", "pypi-requests-reported-v1"}:
            raise ValueError("invalid fixture source registry")
        if shadow_sources is not None and any(type(source) is not FixtureSource for source in shadow_sources.values()):
            raise ValueError("shadow accepts concrete offline fixture sources only")
        if identity is not None and (not isinstance(identity, str) or not 1 <= len(identity) <= 128 or not identity.isascii() or any(ord(c) < 33 for c in identity)):
            raise ValueError("invalid extractor identity")
        self.engine, self.extractor, self.identity = engine, extractor, identity or engine
        self.work_seconds, self.max_active, self.measure = float(work_seconds), max_active, measure
        self.shadow_sources = dict(shadow_sources) if shadow_sources is not None else None
        self.clock, self._active = clock, 0

    async def analyze(self, request: Request):
        request = Request.model_validate(request.model_dump(warnings=False))
        analysis = AnalysisInput(text=request.candidate, reference_date=request.reference_date)
        started = time.perf_counter()
        proposals, observations, reply, failure, extract_ms = (), (), None, None, None
        diagnostic_stage = diagnostic_code = None

        def finish():
            result = Result(request=request, extractor=self.engine, extractor_identity=self.identity,
                extractor_status="FAILED" if failure else "INDEPENDENT_ONLY" if self.engine == "auditor" else "VALIDATED",
                failure_code=failure, diagnostic_stage=diagnostic_stage, diagnostic_code=diagnostic_code,
                proposals=proposals, **derive(request.candidate, proposals, failure),
                shadow_observations=observations, shadow_verdict=shadow_status(observations),
                resources=Resources(work_seconds=self.work_seconds,
                    elapsed_ms=(time.perf_counter()-started)*1000 if self.measure else None,
                    extractor_ms=extract_ms if self.measure else None,
                    input_tokens=reply.input_tokens if reply else None,
                    output_tokens=reply.output_tokens if reply else None,
                    estimated_cost_usd=reply.estimated_cost_usd if reply else None))
            if len(result.model_dump_json().encode("utf-8")) > 256*1024:
                raise ValueError("analysis output bound")
            return result

        if self._active >= self.max_active:
            failure = "BUSY"
            return finish()
        self._active += 1
        try:
            async with asyncio.timeout(self.work_seconds):
                before = time.perf_counter()
                if self.engine == "baseline":
                    extraction = baseline.analyze(analysis)
                elif self.engine == "auditor":
                    extraction = independent_proposals(analysis)
                else:
                    extraction, reply = await self.extractor.analyze(analysis)
                    if not isinstance(reply, ModelReply):
                        reply = None
                        raise ValueError("invalid provider metadata")
                extract_ms = (time.perf_counter()-before)*1000
                extraction = Extraction.model_validate(extraction.model_dump(warnings=False)).bind(analysis)
                if len(extraction.claims) > 8:
                    failure = "CLAIM_LIMIT"
                elif any(request.candidate.find(c.source_text) != request.candidate.rfind(c.source_text) for c in extraction.claims):
                    failure = "EXTRACTION_FAILED"
                else:
                    proposals = tuple(Proposal.model_validate({**c.model_dump(), "uncertainty": tuple(c.uncertainty)}) for c in extraction.claims)
                    audit = derive(request.candidate, proposals)
                    if self.shadow_sources is not None and audit["policy_mappings"] and all(
                        c.disposition == "COVERED_FACT" for c in audit["correspondences"] if c.unit_id in {m.unit_id for m in audit["policy_mappings"]}):
                        rows = []
                        for mapping in audit["policy_mappings"]:
                            bound, _ = qualify(mapping.canonical_text)
                            try:
                                async with asyncio.timeout(min(1.0, self.work_seconds)):
                                    source = self.shadow_sources[mapping.policy_id]
                                    if type(source) is not FixtureSource:
                                        raise ValueError("shadow source must remain offline")
                                    checked = await verify_claim(bound[0], source,
                                        request_id=request.request_id, fixture=True, clock=self.clock)
                                    checked = ClaimResult.model_validate(checked.model_dump(warnings=False))
                            except Exception:
                                checked = ClaimResult(claim=bound[0], verdict="INSUFFICIENT", reason_code="VERIFIER_ERROR",
                                                      evidence_requirements_satisfied=False, evidence=[])
                            rows.append(ShadowObservation(unit_id=mapping.unit_id, verdict=checked.verdict,
                                                          reason_code=checked.reason_code, evidence=tuple(checked.evidence),
                                                          checked_at=self.clock()))
                        observations = tuple(rows)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            failure = "DEADLINE"
        except AnalysisFailure as error:
            failure = "DEADLINE" if str(error) == "MODEL_TIMEOUT" else "EXTRACTION_FAILED"
            if error.diagnostic is not None and error.diagnostic.issues:
                diagnostic_stage, diagnostic_code = error.diagnostic.stage, error.diagnostic.issues[0].code
        except (ValueError, TypeError, AttributeError, UnicodeError):
            failure = "EXTRACTION_FAILED"
        finally:
            self._active -= 1
        if failure:
            proposals, observations = (), ()
        try:
            return finish()
        except (ValueError, UnicodeError):
            failure, proposals, observations, reply = "OUTPUT_LIMIT", (), (), None
            return finish()
