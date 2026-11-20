"""Offline JSON-size evidence, NOT a Gemini tokenizer or model-capacity test."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'services/evidence_assessment'),str(ROOT/'services/claim_analysis')]
from evidence_assessment.factory import packet
from evidence_assessment.schema import ModelAssessment


def five_sources(maximum=False):
    record={
        'claim':'The chemical symbol for gold is Au.',
        'scope':'SINGLE_FACT','assessment':'SUPPORTED',
        'explanation':'The supplied excerpts consistently identify the element.',
        'uncertainty':['This is an AI interpretation of supplied excerpts.'],
        'independence_uncertain':False,
        'source_assessments':[{'source_id':f'S{i}','stance':'SUPPORTS',
            'quote':f'Synthetic source {i} identifies the chemical symbol for gold as Au.'} for i in range(1,6)],
        'citation_ids':[f'S{i}' for i in range(1,6)]}
    if maximum:
        # Maximum field lengths admitted by today's schema; not factual labels.
        record['claim']='x'*512
        record['explanation']='x'*900
        record['uncertainty']=['x'*180 for _ in range(5)]
        for item in record['source_assessments']: item['quote']='x'*600
    ModelAssessment.model_validate(record)
    return record


def measure(name, record):
    ModelAssessment.model_validate(record)
    raw=json.dumps(record,ensure_ascii=False,separators=(',',':'))
    pretty=json.dumps(record,ensure_ascii=False,indent=2)
    assert len(raw.encode())<=16384 and len(pretty.encode())<=16384
    return {'case':name,'source_count':len(record['source_assessments']),
        'compact_characters':len(raw),'compact_utf8_bytes':len(raw.encode()),'pretty_characters':len(pretty),
        'rough_english_tokens_at_4_chars_per_token':math.ceil(len(raw)/4),
        'schema_valid':True,'within_existing_json_byte_limit':True}


def main():
    directory=Path(sys.argv[1])
    directory.mkdir(parents=True,exist_ok=False)
    rows=[measure(row['id'],row['model_record']) for row in packet()['cases']
          if row['expected'] in ('SUPPORTED','CONTRADICTED')]
    rows += [measure('five-source-compact',five_sources()),measure('five-source-schema-maxima',five_sources(True))]
    report={'schema_version':'005j.output-size-evidence.v1','measured_at':datetime.now(timezone.utc).isoformat(),
        'provider_requests':0,'tokenizer':'none','rows':rows,
        'limitation':'Character counts are exact; four-characters-per-token figures are a rough English heuristic, '
            'not Gemini token counts. Thinking tokens and live generation requirements were not measured.'}
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__': main()
