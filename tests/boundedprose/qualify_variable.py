"""005H: extend the existing G gateway profile with immutable offline evidence."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from gatecompare.qualify import environment, Ownership, write
from boundedprose.variable_matrix import profiles, cases, runtime_hash, sha, validate

PROJECT="epochguard-005h"
PREFIX="epochguard-005h"
COMPOSE=["docker","compose","--env-file","dev/lab.compose.env","-f","compose.verify.004g.yaml",
         "-f","tests/boundedprose/variable.compose.yaml","--project-name",PROJECT]


def source_hash():
    paths=[*(ROOT/'tests/boundedprose').glob('*.py'),ROOT/'tests/boundedprose/Dockerfile.variable',
        ROOT/'tests/boundedprose/variable.compose.yaml',ROOT/'compose.verify.004g.yaml',
        *(ROOT/'tests/gatecompare').glob('*.py'),*(ROOT/'services/verifier/verifier').rglob('*.py'),
        *(ROOT/'plugins/epochguard').glob('*.go'),*(ROOT/'internal/ingress').glob('*.go'),
        *(ROOT/'cmd/provider-fixture').glob('*.go'),*(ROOT/'cmd/receipt-relay').glob('*.go'),
        ROOT/'cmd/protected-ingress/main.go',ROOT/'services/claim_analysis/claim_analysis/schema.py',
        *(ROOT/'services/verifier').glob('Dockerfile*'),ROOT/'services/verifier/requirements.lock',
        ROOT/'dev/Dockerfile',ROOT/'dev/Dockerfile.checks',ROOT/'dev/prose/gateway.json',
        ROOT/'dev/live/gateway-control.json',ROOT/'plugins/epochguard/go.mod',ROOT/'plugins/epochguard/go.sum',ROOT/'go.mod']
    return sha(b''.join(p.relative_to(ROOT).as_posix().encode()+b'\0'+p.read_bytes().replace(b'\r\n',b'\n') for p in sorted(set(paths))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true',help='rebuild isolated native/004C/004E/004G dependencies')
    parser.add_argument('--builder',help='native Buildx builder; defaults to Docker selection')
    args=parser.parse_args()
    root=ROOT/'artifacts/005h'
    env=environment()
    with Ownership(root):
        directory=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8])
        directory.mkdir(parents=True)
        stages=[]

        def run(stage, command, *, timeout=240, check=True):
            print(stage,flush=True)
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,encoding='utf-8',timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            stages.append({'stage':stage,'command':command,'exit_code':result.returncode})
            if check and result.returncode: raise RuntimeError('005H stage failed')
            return result

        def resources():
            return {name:run('inspect-'+name,['docker',*command,'--filter','label=com.docker.compose.project='+PROJECT]).stdout.split()
                    for name,command in (('containers',['ps','-aq']),('volumes',['volume','ls','-q']),('networks',['network','ls','-q']))}

        # Refuse foreign resources before entering any owned cleanup region.
        if any(resources().values()): raise RuntimeError('005H project already exists; no resources changed')
        digest=source_hash()
        revision=run('revision',['git','rev-parse','HEAD']).stdout.strip()
        if args.build:
            command=['docker','buildx','build']+(['--builder',args.builder] if args.builder else [])+['--load']
            run('build-native',command+['-t',PREFIX+'-dev:002a','-f','dev/Dockerfile','.'],timeout=1800)
            for name,base in (('004c',None),('004e','004c'),('004g','004e')):
                cmd=['docker','build','-t',PREFIX+'-verifier:'+name,'-f','services/verifier/Dockerfile.'+name]
                if base: cmd+=['--build-arg','VERIFIER_BASE='+PREFIX+'-verifier:'+base]
                run('build-'+name,cmd+['.'],timeout=1800)
        run('build-variable',['docker','build','-t',PREFIX+'-verifier:005h','-f','tests/boundedprose/Dockerfile.variable',
            '--build-arg','VERIFIER_BASE='+PREFIX+'-verifier:004g','.'],timeout=600)
        images={}
        for tag in (PREFIX+'-dev:002a',PREFIX+'-verifier:005h'):
            identity=run('image-identity',['docker','image','inspect','--format','{{.Id}}',tag]).stdout.strip()
            if not re.fullmatch(r'sha256:[0-9a-f]{64}',identity): raise ValueError('immutable image required')
            images[tag]=identity
        env.update(EPOCHGUARD_005H_NATIVE_IMAGE=images[PREFIX+'-dev:002a'],EPOCHGUARD_005H_IMAGE=images[PREFIX+'-verifier:005h'])
        summaries=[]
        try:
            for profile in profiles():
                target=directory/profile.name
                target.mkdir()
                write(target/'profile.json',asdict(profile))
                env['EPOCHGUARD_005H_PROFILE']=(target/'profile.json').as_posix()
                cleanup=False

                def role(who, action, *extra):
                    return json.loads(run(profile.name+'-'+action,COMPOSE+['run','--rm','--no-deps','-T',
                        'qualification-'+who,'python','-m','boundedprose.variable_client',action,*extra]).stdout)
                try:
                    services=['ingress','ingress-unsafe']+(['ingress-faults'] if profile.mode=='receipts' else [])
                    run(profile.name+'-start',COMPOSE+['up','-d','--wait',*services])
                    before=role('operator','report')
                    expected_runtime=runtime_hash(ROOT/'services/verifier/verifier',ROOT/'tests/boundedprose',ROOT/'tests/gatecompare')
                    if before['runtime_sha256']!=expected_runtime or before['records'] or any(before['source_invocations'].values()):
                        raise ValueError('stale image or startup retrieved evidence')
                    readiness=role('client','ready')
                    if profile.mode=='receipts':
                        rows=[]
                        for index,case in enumerate(cases(profile)):
                            role('operator','control','--fault',case.relay_fault)
                            rows+=role('client','client','--case',str(index))['cases']
                        client={'profile':profile.name,'cases':rows,'private_services_inaccessible':True}
                    else:
                        client=role('client','client')
                    observed=role('operator','report')
                    write(target/'client.json',client)
                    write(target/'observations.json',observed)
                    summary=validate(profile,client,observed)
                    summary['readiness']=readiness
                finally:
                    result=run(profile.name+'-cleanup',COMPOSE+['down','--volumes','--remove-orphans'],check=False)
                    remaining=resources()
                    cleanup=result.returncode==0 and not any(remaining.values())
                    write(target/'cleanup.json',{'completed':cleanup,'remaining':remaining})
                if not cleanup: raise RuntimeError('cleanup incomplete')
                summary['cleanup_completed']=True
                write(target/'report.json',summary)
                summaries.append(summary)
            if source_hash()!=digest: raise ValueError('source changed during qualification')
            counterfactuals=[]
            for earlier,later,changed in [('lower','python-only','python'),('python-only','pypi-only','pypi')]:
                original=next(r for r in json.loads((directory/earlier/'client.json').read_text())['cases'] if r['case']=='two-supported')
                updated=next(r for r in json.loads((directory/later/'client.json').read_text())['cases'] if r['case']=='older-'+changed)
                if original['candidate_sha256']!=updated['candidate_sha256'] or original['outcome']!='ALLOW' or updated['outcome']!='REJECT':
                    raise ValueError('same-text evidence counterfactual failed')
                counterfactuals.append({'from':earlier,'to':later,'changed_source':changed,
                    'candidate_sha256':original['candidate_sha256'],'before':original['outcome'],'after':updated['outcome']})
            report={'schema_version':'005h.qualification.v1','source_revision':revision,'source_sha256':digest,
                'images':images,'fixture':True,'real_model':False,'policy':'004g.v1/bounded-prose-v1','receipt':'004g.receipt.v2',
                'profile_count':len(summaries),'case_count':sum(s['case_count'] for s in summaries),'profiles':summaries,
                'outcomes':{name:sum(s['outcomes'][name] for s in summaries) for name in ('ALLOW','REJECT','UNAVAILABLE','INGRESS_REFUSED')},
                'source_invocations':{name:sum(s['source_invocations'][name] for s in summaries) for name in ('python','pypi')},
                'expectations_met':True,'cleanup_completed':True,'runtime_sha256':expected_runtime,'same_text_counterfactuals':counterfactuals,
                'scope':'controlled provider, fixed synthetic evidence via simulated HTTP, actual pinned gateway/Go/Python/v2 release; no real-world accuracy or origin-freshness claim'}
            write(directory/'report.json',report)
        finally:
            write(directory/'stages.json',stages)
        print('005H VARIABLE-EVIDENCE OFFLINE QUALIFICATION COMPLETE')
        print(directory.relative_to(ROOT))


if __name__=='__main__':
    try: main()
    except Exception: raise SystemExit('005H incomplete; inspect sanitized artifacts; no live calls or automatic retries') from None
