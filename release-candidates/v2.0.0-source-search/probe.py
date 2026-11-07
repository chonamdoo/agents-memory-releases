"""Reproduce one omitted source fact with the real owned Hindsight runtime.

Run with the private Core installed/on PYTHONPATH and the candidate SDK installed.
The receipt must identify an explicitly isolated synthetic runtime. Fixed judgment
probabilities exercise the actual processor; no external Jev call is made.
"""
import argparse
import ast
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import httpx2

from agents_memory.memory_processor import GroundedProcessor
from agents_memory.jev import ProviderResult
from agents_memory_collab.memory_engine import HindsightEngine
from agents_memory_collab.models import Operation
from agents_memory_collab.store import Store
from agents_memory_collab.web import create_app


class FixedJudge:
    def __init__(self, second_score):
        self.second_score = second_score
        self.calls = 0

    def system_one(self, state, questions, **kwargs):
        self.calls += 1
        assert [item['text'] for item in state['items']] == [
            'The cache TTL is 37 seconds.', 'The namespace is cache-v7.']
        answers = {}
        for name, question in questions.items():
            kind, index = name.rsplit('_', 1)
            score = .98 if int(index) == 0 else self.second_score
            if question['type'] == 'choice':
                probabilities = {label: 0.0 for label in question['criteria']}
                probabilities.update(project_fact=score, personal_content=1-score)
                answers[name] = {'type': 'choice', 'choice': max(probabilities, key=probabilities.get),
                                 'probabilities': probabilities}
            else:
                answers[name] = {'type': 'noul', 'noul': score if kind == 'remember' else .01}
        return ProviderResult('synthetic-fixed-probabilities-not-real-Jev', answers, 0)


async def main(args):
    receipt = json.loads(args.receipt.read_text())
    assert receipt['synthetic_only'] is True
    fixture = Path(__file__).resolve().parents[2] / 'distribution/server/tests/test_recall_evidence.py'
    tree = ast.parse(fixture.read_text())
    function = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == 'test_different_native_fragments_of_identical_sources_share_one_result_slot')
    assignment = next(n for n in function.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'body' for t in n.targets))
    source = ast.literal_eval(assignment.value)
    target = source.splitlines()[1]
    query = 'What is the cache namespace?'
    report = {'schema': 'original-source-discovery-mechanism-v1',
              'fixture': {'path': str(fixture.relative_to(fixture.parents[3])),
                          'line': assignment.lineno,
                          'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest()},
              'source': source, 'target': target, 'query': query,
              'external_jev_calls': 0, 'quality_gate_pass_claimed': False,
              'processing': receipt['processing'],
              'judgment': 'fixed probabilities through production GroundedProcessor',
              'retrieval': 'real Hindsight, E5, BGE and PostgreSQL; original search uses PostgreSQL FTS',
              'arms': {}}
    for name, score in [('omitted', .08), ('retained_control', .98)]:
        judge = FixedJudge(score)
        engine = HindsightEngine(receipt['hindsight_url'], GroundedProcessor(judge),
                                 integrated=receipt['processing'] == 'integrated')
        store = Store(receipt['dsn'], memory_engine=engine)
        await store.open()
        try:
            assert Path(await store.pool.fetchval('SHOW data_directory')).resolve() == Path(receipt['pg_data']).resolve()
            key = await store.create_account('Synthetic original source probe ' + name)
            actor = await store.authenticate(key['token'])
            op = Operation(op_id=uuid4(), memory_id=uuid4(), project='source-search-probe',
                           text=source, source_id='existing-cache-fixture', session_id='synthetic-session')
            app = create_app(store, 'http://127.0.0.1:18350')
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app),
                    base_url='http://127.0.0.1:18350',
                    headers={'Authorization': 'Bearer ' + key['token']}) as client:
                pushed = await client.post('/v1/sync/ops', json={'operations': [op.model_dump(mode='json')]})
                assert pushed.status_code == 200, pushed.text
                row = await store.pool.fetchrow('SELECT * FROM am_collab.memories WHERE user_id=$1 AND id=$2', actor.user_id, op.memory_id)
                document = await engine.document_record(row['engine_bank'], row['engine_document'])
                recalled = await client.post('/v1/recall', json={'project': op.project, 'query': query})
                assert recalled.status_code == 200, recalled.text
                calls_before = judge.calls
                store.memory_engine = None
                found = await client.post('/v1/sources/search', json={'project': op.project, 'query': query})
                assert found.status_code == 200, found.text
                result = found.json()
                assert judge.calls == calls_before
                assert result['sources'][0]['body'] == source
                assert result['sources'][0]['body_sha256'] == hashlib.sha256(source.encode()).hexdigest()
                assert result['sources'][0]['id'] == str(op.op_id)
            report['arms'][name] = {'second_passage_score': score,
                'published_memory': row['text'], 'native_document_text': document['original_text'],
                'recall': recalled.json(), 'source_search': result,
                'source_query_processing_calls': judge.calls-calls_before,
                'works_with_memory_engine_unconfigured': True}
        finally:
            await store.close()
    omitted, control = report['arms']['omitted'], report['arms']['retained_control']
    report['checks'] = {
        'omitted_fact_absent_from_published_memory': target not in omitted['published_memory'],
        'omitted_fact_absent_from_native_document': target not in omitted['native_document_text'],
        'omitted_fact_absent_from_recall': all(target not in m['text'] for m in omitted['recall']['memories']),
        'omitted_fact_found_in_original': target in omitted['source_search']['sources'][0]['body'],
        'retained_control_in_recall': any(target in m['text'] for m in control['recall']['memories']),
        'same_full_source_in_both_arms': omitted['source_search']['sources'][0]['body'] == control['source_search']['sources'][0]['body'] == source}
    report['passed'] = all(report['checks'].values())
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps({'passed': report['passed'], 'checks': report['checks']}))
    assert report['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
