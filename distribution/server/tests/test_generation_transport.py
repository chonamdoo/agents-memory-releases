import httpx
import pytest

from agents_memory_collab.generation_transport import PATH, PrivateGeneration

TOKEN = "synthetic-private-token-" + "x" * 40


class Generator:
    def __init__(self):self.calls=0
    async def generate(self,value):
        self.calls+=1
        return {"choices":[{"message":{"content":"generated synthetic memory"}}]}


async def app(scope,receive,send):
    await send({"type":"http.response.start","status":404,"headers":[]})
    await send({"type":"http.response.body","body":b''})


@pytest.mark.asyncio
@pytest.mark.parametrize('peer,token,headers,status',[
    ('127.0.0.1',TOKEN,{},200),
    ('127.0.0.1','ordinary-account-key',{},404),
    ('203.0.113.1',TOKEN,{},404),
    ('127.0.0.1',TOKEN,{'Origin':'https://example.invalid'},404),
    ('127.0.0.1',TOKEN,{'Cookie':'synthetic=1'},404),
])
async def test_generation_requires_private_loopback_nonce(peer,token,headers,status):
    generator=Generator()
    transport=httpx.ASGITransport(app=PrivateGeneration(app,generator,TOKEN),client=(peer,1234))
    async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1') as client:
        result=await client.post(PATH,headers={'Authorization':'Bearer '+token,**headers},json={'messages':[]})
    assert result.status_code==status
    assert generator.calls==int(status==200)


@pytest.mark.asyncio
async def test_private_transport_does_not_expose_provider_error_or_credentials():
    class Failing:
        async def generate(self,value):raise RuntimeError('synthetic-secret-must-not-escape')
    transport=httpx.ASGITransport(app=PrivateGeneration(app,Failing(),TOKEN))
    async with httpx.AsyncClient(transport=transport,base_url='http://127.0.0.1') as client:
        result=await client.post(PATH,headers={'Authorization':'Bearer '+TOKEN},json={})
    assert result.status_code==503 and 'synthetic-secret' not in result.text


@pytest.mark.asyncio
@pytest.mark.parametrize('complete',[False,True])
async def test_generated_text_needs_every_source_document(complete):
    from agents_memory_collab.memory_engine import HindsightEngine
    class Processor:
        contract='agents-memory-grounded-v1'
    class Engine(HindsightEngine):
        async def request(self,*args,**kwargs):
            return {'results':[{'id':'synthetic-observation','text':'An integrated synthetic rule.',
                    'type':'observation','source_fact_ids':['fact-a','fact-b']}],
                    'source_facts':{'fact-a':{'document_id':'a'},**({'fact-b':{'document_id':'b'}} if complete else {})}}
    engine=Engine('http://127.0.0.1:19999',Processor(),generative=True)
    hits=await engine.recall('synthetic','rule')
    assert bool(hits)==complete
    if complete:assert hits[0]['source_documents']==['a','b']
