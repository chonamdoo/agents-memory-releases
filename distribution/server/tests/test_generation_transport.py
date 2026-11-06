import httpx
import pytest
from urllib.parse import urlsplit

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
    engine=Engine('http://127.0.0.1:19999', Processor(), integrated=True)
    hits=await engine.recall('synthetic','rule')
    assert bool(hits)==complete
    if complete:assert hits[0]['source_documents']==['a','b']


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,expected", [
    ("unsupported_integration_request", "unsupported_integration_request"),
    ("unsupported_integration_schema", "unsupported_integration_schema"),
    ("ambiguous_integration_input", "ambiguous_integration_input"),
    ("invalid_integration_identity", "invalid_integration_identity"),
    ("integration_budget", "integration_budget"),
    ("request", "request"),
    ("synthetic-secret-must-not-escape", "provider_unavailable"),
])
async def test_private_transport_exposes_only_allowlisted_typed_failure_codes(kind, expected):
    from agents_memory.jev import ProviderFailure

    class Failing:
        async def generate(self, value):
            raise ProviderFailure(kind)

    transport = httpx.ASGITransport(app=PrivateGeneration(app, Failing(), TOKEN))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        result = await client.post(PATH, headers={"Authorization": "Bearer " + TOKEN}, json={})
    assert result.status_code == 503
    assert result.json()["error"] == {
        "message": "Selected generation provider unavailable",
        "type": "provider_unavailable",
        "code": expected,
    }
    assert "synthetic-secret" not in result.text


@pytest.mark.asyncio
async def test_untyped_exception_cannot_spoof_provider_reason():
    class Spoofed(Exception):
        kind = "unsupported_integration_schema"

    class Failing:
        async def generate(self, value):
            raise Spoofed("synthetic-secret-must-not-escape")

    transport = httpx.ASGITransport(app=PrivateGeneration(app, Failing(), TOKEN))
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        result = await client.post(PATH, headers={"Authorization": "Bearer " + TOKEN}, json={})
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "provider_unavailable"
    assert "synthetic-secret" not in result.text


@pytest.mark.asyncio
@pytest.mark.parametrize("failed,observations", [(1, 1), (2, 0)])
async def test_completed_partial_or_total_consolidation_failure_cannot_confirm_index(failed, observations):
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        async def request(self, path, value=None, method=None):
            if path.endswith("/config"):
                return {"config": {
                    "retain_extraction_mode": "chunks", "enable_observations": True,
                    "enable_auto_consolidation": False,
                }}
            if "/documents/" in path:
                return {"original_text": "Synthetic retained rule.", "memory_unit_count": 2}
            if path.endswith("/consolidation/recover"):
                return {"retried_count": failed}
            if path.endswith("/consolidate"):
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            if "/operations/" in path:
                return {
                    "status": "completed",
                    "progress": {"stage": "refreshing_mental_models", "processed": 2, "total": 2},
                }
            if urlsplit(path).path.endswith("/stats"):
                return {
                    "pending_consolidation": 0, "failed_consolidation": failed,
                    "total_observations": observations,
                }
            return {}

    engine = Engine("http://127.0.0.1:19999", Processor(), integrated=True)
    prepared = {"passages": [{"start": 0, "end": 24, "text": "Synthetic retained rule."}]}
    with pytest.raises(Failure, match="memory_integration_failed"):
        await engine.index("synthetic-bank", "synthetic-document", prepared)


@pytest.mark.asyncio
@pytest.mark.parametrize("stats,code", [
    ({"pending_consolidation": 0, "failed_consolidation": 0}, "memory_integration_not_confirmed"),
    ({"pending_consolidation": 0, "failed_consolidation": False, "total_observations": 1}, "memory_integration_not_confirmed"),
])
async def test_unsupported_completed_hindsight_counters_remain_unconfirmed(stats, code):
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        async def request(self, path, value=None, method=None):
            if path.endswith("/consolidate"):
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            if "/operations/" in path:
                return {"status": "completed"}
            assert urlsplit(path).path.endswith("/stats")
            return stats

    engine = Engine("http://127.0.0.1:19999", Processor(), integrated=True)
    with pytest.raises(Failure, match=code):
        await engine.integrate("synthetic-bank")


@pytest.mark.asyncio
async def test_completed_operation_with_visible_failed_progress_is_not_success():
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        async def request(self, path, value=None, method=None):
            if urlsplit(path).path.endswith("/stats"):
                return {"failed_consolidation": 0, "pending_consolidation": 0, "total_observations": 0}
            if path.endswith("/consolidate"):
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            return {"status": "completed", "progress": {"detail": {"memories_failed": 1}}}

    engine = Engine("http://127.0.0.1:19999", Processor(), integrated=True)
    with pytest.raises(Failure, match="memory_integration_failed"):
        await engine.integrate("synthetic-bank")


@pytest.mark.asyncio
async def test_review_failure_preserves_source_free_audit():
    from agents_memory.jev import ProviderFailure
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    audit = {"admission_policy_version": 5, "admission_complete": True, "decision": "review_required"}

    class Processor:
        contract = "agents-memory-grounded-v1"

        async def process(self, source):
            error = ProviderFailure("review_required")
            error.audit = audit
            raise error

    engine = HindsightEngine("http://127.0.0.1:19999", Processor())
    with pytest.raises(Failure, match="memory_requires_review") as caught:
        await engine.prepare("Synthetic rule with uncertainty.")
    assert caught.value.status == 422
    assert caught.value.details == {"audit": audit}


@pytest.mark.asyncio
async def test_same_document_recovers_after_a_permanent_consolidation_outage():
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        def __init__(self):
            super().__init__("http://127.0.0.1:19999", Processor(), integrated=True)
            self.document = None
            self.retains = self.recoveries = 0
            self.failed = self.observations = 0
            self.outage = True

        async def request(self, path, value=None, method=None):
            if path.endswith("/config"):
                return {"config": {"retain_extraction_mode": "chunks",
                                   "enable_observations": True, "enable_auto_consolidation": False}}
            if "/documents/" in path:
                return self.document
            if path.endswith("/memories"):
                self.retains += 1
                item = value["items"][0]
                self.document = {"original_text": item["content"], "document_metadata": item["metadata"],
                                 "memory_unit_count": 1}
                return {"async": False}
            if path.endswith("/consolidation/recover"):
                self.recoveries += 1
                self.failed = 0
                return {"retried_count": 1}
            if path.endswith("/consolidate"):
                self.failed = int(self.outage)
                self.observations = int(not self.failed)
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            if "/operations/" in path:
                return {"status": "completed"}
            if urlsplit(path).path.endswith("/stats"):
                return {"failed_consolidation": self.failed, "pending_consolidation": 0,
                        "total_observations": self.observations}
            return {}

    engine = Engine()
    text = "Synthetic retained release rule."
    prepared = {"passages": [{"start": 0, "end": len(text), "text": text}],
                "metadata": {"operation_id": "synthetic-immutable-operation"}}
    with pytest.raises(Failure, match="memory_integration_failed"):
        await engine.index("synthetic-bank", "same-document", prepared)
    assert engine.observations == 0
    engine.outage = False
    assert await engine.index("synthetic-bank", "same-document", prepared) == text
    assert engine.failed == 0 and engine.observations == 1
    assert engine.document["document_metadata"] == prepared["metadata"]
    assert engine.retains == engine.recoveries == 1


@pytest.mark.asyncio
async def test_cached_healthy_stats_cannot_hide_a_new_consolidation_failure():
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        completed = False

        async def request(self, path, value=None, method=None):
            if path.endswith("/consolidate"):
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            if "/operations/" in path:
                self.completed = True
                return {"status": "completed"}
            return {"failed_consolidation": int(self.completed and urlsplit(path).query == "refresh=true"),
                    "pending_consolidation": 0, "total_observations": 1}

    engine = Engine("http://127.0.0.1:19999", Processor(), integrated=True)
    with pytest.raises(Failure, match="memory_integration_failed"):
        await engine.integrate("synthetic-bank")


@pytest.mark.asyncio
async def test_completed_consolidation_without_observations_cannot_confirm_a_new_memory():
    from agents_memory_collab.memory_engine import HindsightEngine
    from agents_memory_collab.models import Failure

    text = "Synthetic retained release rule."

    class Processor:
        contract = "agents-memory-grounded-v1"

    class Engine(HindsightEngine):
        async def request(self, path, value=None, method=None):
            if path.endswith("/config"):
                return {"config": {"retain_extraction_mode": "chunks",
                                   "enable_observations": True, "enable_auto_consolidation": False}}
            if "/documents/" in path:
                return {"original_text": text, "memory_unit_count": 1}
            if path.endswith("/consolidate"):
                return {"operation_id": "00000000-0000-0000-0000-000000000001"}
            if "/operations/" in path:
                return {"status": "completed"}
            if urlsplit(path).path.endswith("/stats"):
                return {"failed_consolidation": 0, "pending_consolidation": 0, "total_observations": 0}
            return {}

    engine = Engine("http://127.0.0.1:19999", Processor(), integrated=True)
    prepared = {"passages": [{"start": 0, "end": len(text), "text": text}]}
    with pytest.raises(Failure, match="memory_integration_empty"):
        await engine.index("synthetic-bank", "synthetic-document", prepared)
