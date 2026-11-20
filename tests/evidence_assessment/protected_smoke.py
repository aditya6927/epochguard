"""Existing protected G path regression; isolated project, no Explorer involved."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests'))
from gatecompare.qualify import environment

PROJECT = 'epochguard-005i-protected'


def main():
    directory = ROOT/'artifacts/005i'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-protected')
    directory.mkdir(parents=True, exist_ok=False)
    env = environment()
    stages = []
    def run(command):
        value = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=240,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        stages.append({'command': command, 'exit_code': value.returncode})
        if value.returncode: raise RuntimeError('protected smoke stage failed; diagnostics withheld')
        return value.stdout.decode()
    def resources():
        return {kind:run(['docker',*command,'--filter','label=com.docker.compose.project='+PROJECT]).split()
                for kind,command in (('containers',['ps','-aq']),('networks',['network','ls','-q']),('volumes',['volume','ls','-q']))}
    if any(resources().values()): raise RuntimeError('existing project resources; no resources changed')
    images = {tag:run(['docker','image','inspect',tag,'--format','{{.Id}}']).strip()
              for tag in ('epochguard-dev:002a','epochguard-verifier:004g')}
    overlay = directory/'images.json'
    overlay.write_text(json.dumps({'services': {
        **{s:{'image':images['epochguard-dev:002a']} for s in ('key-init','provider','gateway','gateway-control','ingress','ingress-unsafe')},
        **{s:{'image':images['epochguard-verifier:004g']} for s in ('verifier','qualification-client')}}}),encoding='utf-8')
    compose = ['docker','compose','--env-file','dev/lab.compose.env','--project-name',PROJECT,
               '-f','compose.verify.004g.yaml','-f',str(overlay)]
    report = {'baseline':run(['git','rev-parse','HEAD']).strip(), 'images':images, 'simulated':True}
    try:
        run(compose+['up','-d','--wait','ingress','ingress-unsafe'])
        code = "import json; import prose_runner as p; p.ready(); p.ready('ingress-unsafe',503); p.infer('supported'); p.infer('older',p.B,403); p.infer('unsupported',p.A+' Extra unsupported prose.',503); p.infer('missing-plugin',p.A,503,'ingress-unsafe'); p.infer('provider-error','PRIVATE_PROVIDER_SENTINEL',400,role='system'); print(json.dumps(p.rows))"
        report['cases'] = json.loads(run(compose+['run','--rm','--no-deps','qualification-client','python','-c',code]))
        assert len(report['cases'])==5
    finally:
        run(compose+['down','--volumes','--remove-orphans'])
        report['cleanup'] = resources()
        report['stages'] = stages
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        assert not any(report['cleanup'].values())
    print('5/5 actual protected-gateway outcomes passed; disposable signing volume cleanup verified.')


if __name__=='__main__': main()
