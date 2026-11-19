"""Arithmetic and benchmark safety tests; gateway evidence comes from qualify.py."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gatecompare.benchmark import load_dataset, payload, sha, quantiles, summarize, protected_outcome, check_inventory
from gatecompare.qualify import Ownership, environment, execute


def test_frozen_labels_and_explicit_denominators(tmp_path):
    cases = load_dataset()
    assert len(cases) == 24
    assert sum(c['truth'] == 'unsafe' for c in cases) == 8
    assert sum(c['truth'] == 'unknown' for c in cases) == 4
    assert sum(c['truth'] == 'correct' for c in cases) == 12
    assert sum(c['category'] == 'supported' for c in cases) == 6
    assert sum(c['unnecessary_refusal'] for c in cases) == 5
    changed = tmp_path/'changed.json'
    changed.write_text('{}')
    with pytest.raises(ValueError): load_dataset(changed)


def test_baseline_retains_matching_bifrost_builtins_without_epochguard():
    check_inventory({'gateway':['compat','epochguard','routing'], 'gateway-control':['compat','routing']})


@pytest.mark.parametrize('loaded', [
    {'gateway':['compat'], 'gateway-control':['compat']},
    {'gateway':['epochguard'], 'gateway-control':['epochguard']},
    {'gateway':['epochguard','semantic_cache'], 'gateway-control':[]},
    {'gateway':['epochguard','routing'], 'gateway-control':[]}])
def test_unprotected_or_cached_inventory_cannot_impersonate_comparison(loaded):
    with pytest.raises(ValueError): check_inventory(loaded)


@pytest.mark.parametrize('case', load_dataset(), ids=lambda c: c['id'])
def test_exact_candidate_wire_binding(case):
    wire = payload(case)
    assert json.loads(wire)['messages'][0]['content'].encode() == case['candidate'].encode()
    assert payload(case) == wire
    assert 'fallbacks' not in json.loads(wire)


def test_nearest_rank_quantiles_keep_negative_matched_deltas():
    assert quantiles([])['p95_ms'] is None
    assert quantiles([-3_000_000, 1_000_000, 2_000_000]) == {
        'n': 3, 'p50_ms': 1, 'p95_ms': 2, 'mean_ms': 0}
    assert quantiles(list(range(1, 101)))['p95_ms'] == 95/1e6


def arithmetic_rows(cases):
    # Synthetic input to arithmetic tests only; never written as measured data.
    rows = []
    for case in cases:
        row = {'case': case['id'], 'repetition': 0, 'added_latency_ns': 2_000_000}
        for path in ('unprotected', 'protected'):
            delivered = path == 'unprotected' or case['expected'] == 'ALLOW'
            row[path] = {'status': 200 if delivered else 403 if case['expected'] == 'REJECT' else 503,
                'outcome': 'DELIVERED' if path == 'unprotected' else case['expected'],
                'candidate_content_reached_client': delivered,
                'content_sha256': sha(case['candidate'].encode()) if delivered else None,
                'request_sha256': sha(payload(case)), 'provider_requests': 1,
                'source_invocations': {'python':0, 'pypi':0} if path == 'unprotected' else case['sources'],
                'elapsed_ns': 1_000_000 if path == 'unprotected' else 3_000_000}
        rows.append(row)
    return rows


def test_metric_arithmetic_and_category_denominators():
    cases = load_dataset()
    report = summarize(cases, arithmetic_rows(cases), 1)
    assert report['expectations_met']
    overall = report['overall']
    assert overall['unsafe_answers_delivered'] == {
        'denominator_cases':8, 'denominator_observations':8, 'unprotected':8, 'protected':0}
    assert overall['safe_but_unnecessary_refusals']['protected'] == 5
    assert overall['missing_plugin_refusals']['protected'] == 1
    assert overall['unknown_or_inconclusive_answers_delivered']['unprotected'] == 4
    assert overall['latency']['matched_added']['p95_ms'] == 2
    assert sum(r['matched_pairs'] for r in report['categories'].values()) == 24


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'delta', 'request', 'content', 'provider', 'source', 'outcome'])
def test_incomplete_or_mismatched_measurements_cannot_pass(mutation):
    cases = load_dataset()
    rows = copy.deepcopy(arithmetic_rows(cases))
    if mutation == 'missing': rows.pop()
    elif mutation == 'duplicate': rows[-1] = rows[0]
    elif mutation == 'delta': rows[0]['added_latency_ns'] = 0
    elif mutation == 'request': rows[0]['protected']['request_sha256'] = '0'*64
    elif mutation == 'content': rows[0]['protected']['content_sha256'] = '0'*64
    elif mutation == 'provider': rows[0]['unprotected']['provider_requests'] = 0
    elif mutation == 'source': rows[0]['unprotected']['source_invocations']['python'] = 1
    else: rows[0]['protected']['outcome'] = 'UNAVAILABLE'
    try:
        assert summarize(cases, rows, 1)['expectations_met'] is False
    except ValueError:
        pass


def test_protected_content_and_minimal_envelope_checks():
    body = {'object':'chat.completion', 'choices':[{'index':0,'finish_reason':'stop',
        'message':{'role':'assistant','content':'test'}}]}
    assert protected_outcome(200, body, 'test') == ('ALLOW', True)
    for modified in [dict(body, usage={}), {'choices':[]}, dict(body, object='other')]:
        with pytest.raises(ValueError): protected_outcome(200, modified, 'test')
    with pytest.raises(ValueError): protected_outcome(200, body, 'other')
    with pytest.raises(ValueError): protected_outcome(503, {'error':{'message':'test'}}, 'test')


def test_no_inherited_live_configuration(monkeypatch):
    for name in ('GEMINI_API_KEY', 'TAVILY_API_KEY', 'EPOCHGUARD_005E_ALLOW_MODEL', 'COMPOSE_FILE', 'SOME_SECRET'):
        monkeypatch.setenv(name, 'PRIVATE_UNUSED')
    assert 'PRIVATE_UNUSED' not in json.dumps(environment())


def test_ownership_is_exclusive_and_foreign_resources_are_preserved(tmp_path):
    with Ownership(tmp_path/'ownership'):
        with pytest.raises(FileExistsError):
            with Ownership(tmp_path/'ownership'): pass
    assert not (tmp_path/'ownership/owner.lock').exists()
    commands = []
    def invoke(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout='foreign' if command[1:3] == ['ps','-aq'] else '', stderr='')
    with pytest.raises(RuntimeError): execute(tmp_path/'run', invoke=invoke)
    assert not any('down' in c or 'up' in c for c in commands)
    assert (tmp_path/'run/failure.json').exists()
