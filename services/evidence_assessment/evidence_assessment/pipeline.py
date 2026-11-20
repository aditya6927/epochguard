import asyncio
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re

from .config import Budget, Failure
from .schema import Request, Result

DISCLAIMER="Search excerpts can omit context; AI interpretation is not independent proof."


def local_scope(claim):
    """Conservative English MVP admission, not general semantic extraction."""
    text=claim.strip()
    if ("\n" in text or "\t" in text or "?" in text or ";" in text or
        len(re.findall(r"[.!](?:\s|$)",text))>1 or
        re.search(r"\b(and|but|whereas|also)\b",text,re.I) or
        re.match(r"^(he|she|it|they|this|that|these|those|who|what|why|how|please)\b",text,re.I) or
        re.search(r"\b(best|worst|excellent|beautiful|i think|i believe)\b",text,re.I)):
        return False
    return True


class Pipeline:
    def __init__(self, search, assessor, settings, *, simulated, clock=lambda:datetime.now(timezone.utc)):
        self.search,self.assessor,self.settings,self.clock=search,assessor,settings,clock
        self.simulated,self.budget,self.active=simulated,Budget(settings),0

    def result(self, claim, reason, explanation, *, sources=(), assessment="INSUFFICIENT_EVIDENCE", citations=(), uncertainty=()):
        return Result(claim=claim,evidence_mode="simulated" if self.simulated else "live",assessment=assessment,
            reason_code=reason,explanation=explanation,sources=list(sources),citation_ids=list(citations),
            uncertainty=[*uncertainty,DISCLAIMER][:6],assessed_at=self.clock())

    async def assess(self, request):
        request=Request.model_validate(request.model_dump())
        claim=request.claim
        if not local_scope(claim):
            return self.result(claim,"SCOPE_ABSTENTION","Enter one self-contained, externally checkable English factual statement.")
        if self.active>=2:
            return self.result(claim,"BUSY","The local assessor is busy; no assessment was completed.")
        self.active+=1
        sources=[]
        try:
            async with asyncio.timeout(42):
                await self.budget.admit()
                sources=await self.search.retrieve(claim)
                if len(sources)<2 or len({s.publisher_group for s in sources})<2:
                    return self.result(claim,"INSUFFICIENT_SOURCES","The search did not provide two distinct usable publisher groups.",sources=sources)
                # Exact/near copies do not supply independent corroboration.
                for i,source in enumerate(sources):
                    for other in sources[:i]:
                        if SequenceMatcher(None,source.snippet.casefold(),other.snippet.casefold()).ratio()>=.88:
                            return self.result(claim,"DUPLICATED_EVIDENCE","The excerpts may repeat the same source material.",sources=sources)
                assessed=await self.assessor.assess(claim,sources,self.clock())
                reply,diagnostic=assessed.record,assessed.diagnostics
                actual={s.id:s for s in sources}
                evaluated={s.source_id:s for s in reply.source_assessments}
                if reply.claim!=claim:
                    raise diagnostic.failure("MODEL_CLAIM_MISMATCH",(("claim",),))
                if len(evaluated)!=len(reply.source_assessments) or set(evaluated)!=set(actual):
                    raise diagnostic.failure("MODEL_SOURCE_COVERAGE",(("source_assessments",),))
                if len(set(reply.citation_ids))!=len(reply.citation_ids) or not set(reply.citation_ids)<=set(actual):
                    raise diagnostic.failure("MODEL_CITATION_BINDING",(("citation_ids",),))
                for index,item in enumerate(reply.source_assessments):
                    key=item.source_id
                    if item.quote and item.quote not in actual[key].snippet:
                        raise diagnostic.failure("MODEL_QUOTATION_BINDING",(("source_assessments",index,"quote"),))
                    if item.stance in {"SUPPORTS","CONTRADICTS"} and len(item.quote.strip())<20:
                        raise diagnostic.failure("MODEL_QUOTATION_BINDING",(("source_assessments",index,"quote"),))
                if reply.scope!="SINGLE_FACT":
                    return self.result(claim,"SCOPE_ABSTENTION","The model could not resolve this as one self-contained factual statement.",sources=sources)
                if reply.assessment=="INSUFFICIENT_EVIDENCE":
                    return self.result(claim,"MODEL_ABSTENTION",reply.explanation,sources=sources,citations=reply.citation_ids,uncertainty=reply.uncertainty)
                wanted="SUPPORTS" if reply.assessment=="SUPPORTED" else "CONTRADICTS"
                relevant=[item for item in evaluated.values() if item.stance!="IRRELEVANT"]
                if any(item.stance!=wanted for item in relevant):
                    return self.result(claim,"SOURCE_DISAGREEMENT","The source assessments conflict or leave relevant evidence unresolved.",sources=sources)
                cited=[evaluated[key] for key in reply.citation_ids]
                if (reply.independence_uncertain or len(cited)<2 or any(s.stance!=wanted for s in cited) or
                    len({actual[s.source_id].publisher_group for s in cited})<2):
                    return self.result(claim,"INSUFFICIENT_CORROBORATION","Independent relevant corroboration could not be established.",sources=sources)
                return self.result(claim,"AI_EVIDENCE_ASSESSMENT",reply.explanation,sources=sources,assessment=reply.assessment,
                                   citations=reply.citation_ids,uncertainty=reply.uncertainty)
        except asyncio.CancelledError:
            raise
        except Failure as error:
            return self.result(claim,str(error),"The evidence or model response was unavailable or could not be safely validated.",sources=sources)
        except TimeoutError:
            return self.result(claim,"ASSESSMENT_TIMEOUT","The assessment deadline expired; no conclusion was established.",sources=sources)
        except Exception:
            return self.result(claim,"ASSESSMENT_ERROR","The assessment could not be completed.",sources=[])
        finally:
            self.active-=1
