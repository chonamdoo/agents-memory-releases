"""Protocol-only test double; never used by a production entry point.

Legacy transport/ACL tests use deterministic storage. Real Hindsight and the
private admission processor are exercised in test_unified_contract.py separately.
"""
from agents_memory_collab.memory_engine import HindsightEngine

DOCUMENTS = {}


class ProtocolEngine:
    bank = staticmethod(HindsightEngine.bank)
    document = staticmethod(HindsightEngine.document)

    async def health(self):
        return {"contract":"agents-memory-grounded-v1", "engine":"test-double-not-hindsight"}

    async def prepare(self, source):
        return {"decision":"keep", "passages":[{"start":0,"end":len(source),"text":source}]}

    async def index(self, bank, document, prepared):
        text = "\n".join(item["text"] for item in prepared["passages"])
        DOCUMENTS[bank, document] = text
        return text

    async def read(self, bank, document):
        return DOCUMENTS.get((bank,document))

    async def delete(self, bank, document):
        DOCUMENTS.pop((bank,document),None)

    async def recall(self, bank, query):
        return [{"document_id":document,"text":text} for (b,document),text in DOCUMENTS.items()
                if b==bank and query.casefold() in text.casefold()]
