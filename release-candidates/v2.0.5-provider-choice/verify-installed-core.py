import asyncio, importlib, json, os, sys, tempfile, threading, zipfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

wheel, build = map(Path, sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='am-v205-installed-', dir='/tmp') as root:
    root=Path(root); target=root/'installed'
    with zipfile.ZipFile(wheel) as z:
        private_sources=[n for n in z.namelist() if n.endswith('.py') and n not in {'agents_memory/__init__.py','agents_memory/runtime_launcher.py'}]
        assert not private_sources
        z.extractall(target)
    sys.path.insert(0,str(target))
    for name in json.loads(build.read_text())['modules']:
        module=importlib.import_module('agents_memory.'+name)
        assert Path(module.__file__).is_relative_to(target) and module.__file__.endswith('.pyc')
    from agents_memory.memory_content import PROJECT_KINDS
    from agents_memory.memory_processor import from_environment
    from agents_memory.local_llm import local_client
    from agents_memory.jev import ProviderFailure
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path=='/v1/chat/completions' and self.headers['Authorization']=='Bearer local'
            calls.append(payload)
            questions=json.loads(payload['messages'][1]['content'])['questions']; answers={}
            for name,q in questions.items():
                if q['type']=='noul': answers[name]={'type':'noul','noul':0.0 if name.startswith('injection') else 1.0}
                else:
                    chosen=next(k for k in q['criteria'] if k in PROJECT_KINDS)
                    answers[name]={'type':'choice','choice':chosen,'probabilities':{k:float(k==chosen) for k in q['criteria']}}
            response={'model':'test-local','choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps({'answers':answers})}}]}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(response).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever);thread.start()
    try:
        os.environ.update(AM_MEMORY_PROVIDER='local',AM_MEMORY_MODEL='test-local',AM_MEMORY_DEPLOYMENT_MODE='local',AM_MEMORY_LOCAL_URL=f'http://127.0.0.1:{server.server_port}/v1',AM_MEMORY_JEV_KEY_FILE='/must/not/be/read')
        result=asyncio.run(from_environment().process('The database uses PostgreSQL 18.'))
        assert result['decision']=='keep' and result['passages'][0]['text']=='The database uses PostgreSQL 18.'
        assert result['audit']['provider']=='local' and result['audit']['confidence_kind']=='model_self_reported'
        assert len(calls)==1
        for mode in ['personal-server','team-server','company-server']:
            os.environ['AM_MEMORY_DEPLOYMENT_MODE']=mode
            try: from_environment()
            except ProviderFailure as e: assert 'local_provider_requires_local_deployment' in str(e)
            else: raise AssertionError('cloud local admitted')
        assert len(calls)==1
    finally:server.shutdown();server.server_close();thread.join()
    fake=root/'fake-claude';fake.write_text('#!'+sys.executable+'\nimport json,sys\nsys.stdin.read()\nprint(json.dumps({"type":"result","subtype":"success","is_error":False,"structured_output":{"answers":{"q":{"type":"noul","noul":0.9}}},"modelUsage":{"test-cli":{}}}))\n');fake.chmod(0o700)
    client=local_client('test-cli',host='claude',executable=fake,workdir=root/'runs')
    result=client.system_one('synthetic',{'q':{'type':'noul','instructions':'yes?'}})
    assert result.provider=='local' and list((root/'runs').iterdir())==[]
    print(json.dumps({'python':sys.version.split()[0],'private_modules':len(json.loads(build.read_text())['modules']),'installed_http_processor':'PASS','installed_cli_wrapper':'PASS','server_rejection':'PASS','actual_model_calls':0}))
