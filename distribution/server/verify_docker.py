import argparse
import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from agents_memory_collab.client import Remote, Replica

parser=argparse.ArgumentParser(description='Isolated local Docker smoke test; synthetic data only')
parser.add_argument('--work',type=Path,required=True)
parser.add_argument('--image',default='agents-memory-collaboration:0.2.0-qa')
args=parser.parse_args()
root=args.work.absolute()
if root.exists() and any(root.iterdir()):raise SystemExit('Use a new empty verification directory')
(root/'evidence').mkdir(parents=True,mode=0o700)
prefix='am-collab-qa-'+uuid4().hex[:8]
with socket.socket() as listener:
    listener.bind(('127.0.0.1',0))
    port=listener.getsockname()[1]
base = ['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY','-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
def run(*args):
    return subprocess.run([*base,*args],check=True,capture_output=True,text=True).stdout.strip()
def secret(name,text):
    p=root/name
    if p.exists():p.unlink()
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)
    return str(p)
password=secrets.token_urlsafe(24)
dbenv=secret('docker-db.env',f'POSTGRES_USER=audit\nPOSTGRES_DB=postgres\nPOSTGRES_PASSWORD={password}\n')
serverenv=secret('docker-server.env',f'AM_COLLAB_DATABASE_URL=postgresql://audit:{password}@db:5432/postgres\n')
network=prefix
containers=[]
replicas=[]
try:
    run('network','create',network)
    run('run','-d','--name',prefix+'-db','--network',network,'--network-alias','db','--env-file',dbenv,
        'pgvector/pgvector@sha256:c29f30688a9ad961691bdf0ec1650717cc132a5814619d80f80463d6e4c42e47')
    containers.append(prefix+'-db')
    for _ in range(120):
        try:
            run('exec',containers[0],'pg_isready','-U','audit','-d','postgres');break
        except subprocess.CalledProcessError:time.sleep(.25)
    else:raise RuntimeError('isolated database startup timed out')
    url=f'http://127.0.0.1:{port}'
    run('run','-d','--name',prefix+'-server','--network',network,'--env-file',serverenv,
        '-p',f'127.0.0.1:{port}:18350','--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges:true',
        args.image,'serve','--host','0.0.0.0','--port','18350','--public-url',url,
        '--e5-dir','/models/e5','--e5-manifest','/app/e5-assets.sha256.json')
    containers.append(prefix+'-server')
    for _ in range(120):
        try:
            with urlopen(url+'/healthz',timeout=2) as response: health=json.load(response)
            break
        except OSError:time.sleep(.25)
    else:raise RuntimeError('isolated service startup timed out')
    def account(name):
        path='/tmp/'+name+'.json'
        run('exec',containers[1],'python','-m','agents_memory_collab.cli','account','--name',name,'--output',path)
        value=json.loads(run('exec',containers[1],'cat',path))
        return Remote(url,value['token'])
    owner=account('SyntheticOwner')
    device=owner.request('/v1/devices',{'name':'SyntheticLaptop'})
    a=Replica(root/'docker-a.sqlite',owner)
    b=Replica(root/'docker-b.sqlite',Remote(url,device['token']))
    replicas += [a,b]
    a.connect();b.connect()
    mid=a.stage('app','Synthetic PR policy',kind='summary',session_id='synthetic-session')['memory_id']
    a.cycle();b.cycle()
    assert a.list_memories()==b.list_memories()
    assert b.list_memories()[0]['session_id']=='synthetic-session'
    assert owner.request('/v1/recall',{'query':'PR policy','project':'app'})['memories'][0]['id']==mid
    other=account('SyntheticMember')
    tid=owner.request('/v1/teams',{'name':'SyntheticTeam'})['id']
    basepath='/v1/teams/'+tid
    pid=owner.request(basepath+'/projects',{'name':'app'})['id']
    invite=owner.request(basepath+'/invites',{'projects':[pid]})['invite']
    other.request('/v1/invites/accept',{'invite':invite})
    owner.request(basepath+'/sharing',{'mappings':[{'source_project':'app','project_id':pid}]},method='PUT')
    assert other.request(basepath+'/search',{'query':'PR policy'})['memories'][0]['id']==mid
    owner.request(basepath+'/sharing',{'mappings':[]},method='PUT')
    assert other.request(basepath+'/search',{'query':'PR policy'})['memories']==[]
    evidence={'health':health,'two_replicas_equal':True,'session_preserved':True,'semantic_query_executed':True,
              'team_query_then_unshare':True,'read_only_rootfs':True,
              'image_id':run('image','inspect',args.image,'--format','{{.Id}}')}
    (root/'evidence/docker-smoke.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence))
finally:
    for replica in replicas:replica.close()
    for name in reversed(containers):
        logs=subprocess.run([*base,'logs',name],capture_output=True,text=True,check=False)
        (root/'evidence'/('docker-'+name+'.log')).write_text((logs.stdout+logs.stderr).replace(password,'[redacted]'))
        run('rm','-f','-v',name)
    run('network','rm',network)
