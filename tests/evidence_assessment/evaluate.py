"""Frozen simulated HTTP evaluation; never selects live credentials or providers."""
import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'services/evidence_assessment'),str(ROOT/'services/claim_analysis')]
from evidence_assessment.factory import packet,offline_pipeline,PACKET_SHA256
from evidence_assessment.schema import Request


async def evaluate(directory):
    directory.mkdir(parents=True,exist_ok=False)
    data=packet()
    clock=lambda:datetime.fromisoformat(data['reference_time'])
    rows=[]
    for case in data['cases']:
        pipeline=offline_pipeline(case,clock=clock)
        started=time.perf_counter_ns()
        result=await pipeline.assess(Request(claim=case['claim']))
        row={'case':case['id'],'claim_sha256':hashlib.sha256(case['claim'].encode()).hexdigest(),
            'assessment':result.assessment,'reason_code':result.reason_code,'authorization':result.authorization,
            'source_count':len(result.sources),'citation_ids':result.citation_ids,
            'search_calls':pipeline.search.calls,'model_calls':pipeline.assessor.calls,'elapsed_ns':time.perf_counter_ns()-started}
        # Original 005I fixture and historical reports retain their broad label.
        expected_reason={'injected-instructions':'MODEL_SCHEMA_INVALID','forged-citation':'MODEL_CITATION_BINDING',
                         'forged-quotation':'MODEL_QUOTATION_BINDING'}.get(case['id'],case['expected_reason'])
        row['expectation_met']=(result.assessment==case['expected'] and result.reason_code==expected_reason and
            row['search_calls']==case['expected_search_calls'] and row['model_calls']==case['expected_model_calls'] and
            result.claim==case['claim'] and result.authorization is False)
        rows.append(row)
    report={'schema_version':'005i.offline-evaluation.v1','reason_taxonomy':'005j.v1','mode':'experimental-evidence','authorization':False,
        'simulated':True,'packet_sha256':PACKET_SHA256,'clock':data['reference_time'],'cases':rows,
        'passed':sum(row['expectation_met'] for row in rows),'total':len(rows),
        'search_calls':sum(row['search_calls'] for row in rows),'model_calls':sum(row['model_calls'] for row in rows),
        'limitation':'Simulated provider replies test plumbing/validation, not real Gemini accuracy or live source freshness.'}
    package=ROOT/'services/evidence_assessment/evidence_assessment'
    report['implementation_sha256']=hashlib.sha256(b''.join(p.relative_to(package).as_posix().encode()+b'\0'+
        p.read_bytes().replace(b'\r\n',b'\n') for p in sorted(package.rglob('*')) if p.is_file() and '__pycache__' not in p.parts)).hexdigest()
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('passed','total','search_calls','model_calls','packet_sha256')}))
    if report['passed']!=report['total']: raise SystemExit(1)


if __name__=='__main__': asyncio.run(evaluate(Path(sys.argv[1])))
