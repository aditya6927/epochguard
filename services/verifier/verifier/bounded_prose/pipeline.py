"""No model/extraction input. One shared bounded 004B evidence pipeline."""

from verifier.multiclaim.contract import Request as EvidenceRequest
from verifier.policy import digest
from .contract import Request, Result
from .grammar import parse, comparison_text


class Pipeline:
    def __init__(self, evidence_pipeline):
        self.evidence_pipeline = evidence_pipeline

    async def verify(self, request):
        request = Request.model_validate(request.model_dump(warnings=False))
        mappings, reason = parse(request.candidate)
        verification = None
        if mappings:
            text = comparison_text(mappings)
            verification = await self.evidence_pipeline.verify(EvidenceRequest(
                request_id=request.request_id, candidate=text, candidate_sha256=digest(text)))
        return Result(**request.model_dump(), coverage="COMPLETE" if mappings else "UNCERTAIN",
                      reason_code=reason, mappings=mappings, verification=verification)
