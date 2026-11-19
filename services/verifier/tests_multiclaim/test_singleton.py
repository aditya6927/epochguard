"""Whole-candidate consistency is required before either source may be called."""
import asyncio
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from verifier.bounded_prose.contract import Request as ProseRequest, Result as ProseResult
from verifier.bounded_prose.grammar import parse
from verifier.bounded_prose.pipeline import Pipeline as ProsePipeline
from verifier.claim_report import from_result
from verifier.contract import SOURCE_URL
from verifier.multiclaim.contract import BoundClaim, ClaimResult, Coverage, Result, PYPI_URL
from verifier.multiclaim.coverage import qualify
from verifier.multiclaim.demo import FixtureSource, PYTHON, PYPI, make_request, pypi_claim
from verifier.multiclaim.pipeline import Pipeline, aggregate
from verifier.policy import claim_text, digest
from verifier.prose.mapping import PYTHON_FORMS, PYPI_FORMS
from verifier.retrieval import RetrievalFailure

NOW = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
FIXTURES = next((p / 'tests/conformance' for p in Path(__file__).resolve().parents
                 if (p / 'tests/conformance').exists()), Path('/app/conformance'))
CAPTURED = json.loads((FIXTURES / '005ds-before.json').read_text())
FORMS = ((claim_text('{v}'), *PYTHON_FORMS), (pypi_claim('{v}'), *PYPI_FORMS))


def engine(fault='none', versions=('3.88.7', '3.88.6')):
    class Sequential(FixtureSource):
        async def retrieve(self):
            if fault == 'missing' and self.calls == 1:
                self.calls += 1
                raise RetrievalFailure()
            version = versions[min(self.calls, len(versions)-1)]
            template = PYTHON if self.url == SOURCE_URL else PYPI
            self.content = template.replace('3.88.7' if self.url == SOURCE_URL else '2.88.7', version)
            if fault == 'malformed' and self.calls == 1:
                self.content = 'invalid evidence'
            return await super().retrieve()
    sources = [Sequential(SOURCE_URL, PYTHON, clock=lambda: NOW),
               Sequential(PYPI_URL, PYPI, clock=lambda: NOW)]
    return Pipeline(*sources, fixture=True, clock=lambda: NOW), sources


def verify(mode, text, pipeline):
    if mode == 'multi':
        return asyncio.run(pipeline.verify(make_request(text, '005ds-regression')))
    return asyncio.run(ProsePipeline(pipeline).verify(ProseRequest(
        request_id='005ds-regression', candidate=text, candidate_sha256=digest(text))))


@pytest.mark.parametrize('mode', ['multi', 'prose'])
@pytest.mark.parametrize('policy', [0, 1])
@pytest.mark.parametrize('order', ['forward', 'reverse', 'identical'])
@pytest.mark.parametrize('fault', ['none', 'missing', 'malformed'])
def test_conflicting_observations_never_retrieved(mode, policy, order, fault):
    versions = (('3.88.7', '3.88.6') if policy == 0 else ('2.88.7', '2.88.6'))
    if order == 'reverse': versions = tuple(reversed(versions))
    if order == 'identical': versions = (versions[0], versions[0])
    forms = FORMS[policy]
    text = '\n'.join(forms[0].format(v=v) for v in versions)
    pipeline, sources = engine(fault, versions)
    result = verify(mode, text, pipeline)
    if mode == 'multi':
        assert result.coverage.status == 'UNCERTAIN'
        assert result.coverage.reason_code == 'REPEATED_CLAIM'
        assert result.coverage.required_claim_ids == [] and result.claims == []
        assert result.extraction is None and result.verdict == 'INSUFFICIENT'
    else:
        assert result.coverage == 'UNCERTAIN' and result.reason_code == 'REPEATED_CLAIM'
        assert result.mappings == [] and result.verification is None
        report = from_result(result.model_dump(mode='json'), profile='fixture', generated_at=NOW)
        assert report.coverage == 'UNCERTAIN' and report.claims == [] and report.authorization is False
    assert [s.calls for s in sources] == [0, 0]


PAIRS = [(a, b, v, w) for forms, versions in zip(FORMS, [('3.88.7', '3.88.6'), ('2.88.7', '2.88.6')])
         for a, b in itertools.product(forms, repeat=2)
         for v, w in [versions, versions[::-1], (versions[0], versions[0])]]


@pytest.mark.parametrize('first,second,v,w', PAIRS)
def test_all_nine_forms_cannot_repeat_policy(first, second, v, w):
    text = first.format(v=v)+'\t'+second.format(v=w)
    assert parse(text) == ([], 'REPEATED_CLAIM')
    pipeline, sources = engine()
    result = verify('prose', text, pipeline)
    assert result.mappings == [] and result.verification is None
    assert [s.calls for s in sources] == [0, 0]
    # The exact-template mode also refuses paraphrases instead of admitting a
    # partial claim; it continues to accept only its original two forms.
    pipeline, sources = engine()
    exact = verify('multi', text, pipeline)
    assert exact.coverage.status == 'UNCERTAIN' and exact.claims == []
    assert [s.calls for s in sources] == [0, 0]


def test_actual_captured_supported_records_cannot_be_forged():
    multi = CAPTURED['multi']
    # These are the two genuine individually supported results captured before
    # remediation, not invented verdicts or mismatched evidence identities.
    assert [r['verdict'] for r in multi['claims']] == ['SUPPORTED', 'SUPPORTED']
    required = [BoundClaim.model_validate(r['claim']) for r in multi['claims']]
    claims = [ClaimResult.model_validate_json(json.dumps(r)) for r in multi['claims']]
    coverage = Coverage.model_validate(multi['coverage'])
    assert aggregate(required, claims, coverage, NOW) == 'INSUFFICIENT'
    assert aggregate(required, [claims[0]], coverage, NOW) == 'INSUFFICIENT'
    for record, model in [(multi, Result), (CAPTURED['prose'], ProseResult)]:
        with pytest.raises(ValidationError):
            model.model_validate_json(json.dumps(record))
    report = from_result(CAPTURED['prose'], profile='fixture', generated_at=NOW)
    assert report.claims == [] and report.authorization is False


@pytest.mark.parametrize('mode', ['multi', 'prose'])
@pytest.mark.parametrize('text,expected', [
    (claim_text('3.88.7'), 'SUPPORTED'), (pypi_claim(), 'SUPPORTED'),
    (claim_text('3.88.7')+'\n'+pypi_claim(), 'SUPPORTED'),
    (pypi_claim()+'\t'+claim_text('3.88.7'), 'SUPPORTED'),
    (claim_text('3.88.6')+'\n'+pypi_claim(), 'CONTRADICTED')])
def test_valid_distinct_policies_preserve_binding(mode, text, expected):
    python = FixtureSource(SOURCE_URL, PYTHON, clock=lambda: NOW)
    pypi = FixtureSource(PYPI_URL, PYPI, clock=lambda: NOW)
    result = verify(mode, text, Pipeline(python, pypi, fixture=True, clock=lambda: NOW))
    assert result.candidate == text and result.candidate_sha256 == digest(text)
    checked = result if mode == 'multi' else result.verification
    assert checked.verdict == expected
    assert len({r.claim.policy_id for r in checked.claims}) == len(checked.claims)
    for r in checked.claims:
        s = r.claim.source
        assert checked.candidate[s.start:s.end] == s.source_text
        assert r.claim.candidate_sha256 == digest(checked.candidate)
        assert r.evidence[0].url == (SOURCE_URL if r.claim.policy_id.startswith('python-') else PYPI_URL)


@pytest.mark.parametrize('mode', ['multi', 'prose'])
def test_valid_two_policy_unavailable(mode):
    python = FixtureSource(SOURCE_URL, PYTHON, clock=lambda: NOW)
    pypi = FixtureSource(PYPI_URL, PYPI, unavailable=True, clock=lambda: NOW)
    result = verify(mode, claim_text('3.88.7')+'\n'+pypi_claim(),
                    Pipeline(python, pypi, fixture=True, clock=lambda: NOW))
    checked = result if mode == 'multi' else result.verification
    assert checked.verdict == 'INSUFFICIENT' and len(checked.claims) == 2


def test_eight_is_still_wire_limit_not_policy_cardinality():
    from verifier.multiclaim.contract import MAX_CLAIMS
    assert MAX_CLAIMS == 8
    assert Coverage(status='COMPLETE', reason_code='EXACT_TEMPLATES',
                    required_claim_ids=[f'c{i:03d}' for i in range(1, 9)])
    for count in (2, 8, 9):
        text = '\n'.join(claim_text(f'3.88.{i}') for i in range(count))
        assert qualify(text)[1].reason_code == 'REPEATED_CLAIM'
        assert parse(text) == ([], 'REPEATED_CLAIM')
