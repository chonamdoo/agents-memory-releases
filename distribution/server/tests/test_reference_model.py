"""Small requirements model. Does not import product code or share its SQL."""
from copy import deepcopy


class Spec:
    def __init__(self):
        self.records = {}
        self.accepted = {}

    def commit(self, intent):
        op_id = intent['op_id']
        if op_id in self.accepted:
            assert self.accepted[op_id] == intent, 'operation identity reused for a different intent'
            return
        mid = intent['memory_id']
        old = self.records.get(mid)
        previous = old['revision'] if old else 0
        assert previous == intent['base_revision'], 'conflict requires explicit resolution'
        if old:
            assert (old['project'], old['kind']) == (intent['project'], intent['kind'])
        self.records[mid] = {'project': intent['project'], 'kind': intent['kind'],
            'text': None if intent['deleted'] else intent['text'], 'deleted': bool(intent['deleted']), 'revision': previous+1}
        self.accepted[op_id] = deepcopy(intent)

    def compare(self, actual):
        assert actual == self.records, 'persistent state violates independently specified intent'

    @staticmethod
    def allowed_ids(keys, member_projects, resources, owner):
        return {rid for rid, value in resources.items()
                if 'read' in keys and value['owner'] == owner and value['project'] in member_projects}


def test_oracle_rejects_deliberate_missing_duplicate_corrupt_and_unauthorized():
    import pytest
    spec = Spec()
    op = {'op_id': 'o1', 'memory_id': 'm1', 'project': 'p', 'kind': 'summary', 'text': 'fixed expected text', 'deleted': False, 'base_revision': 0}
    spec.commit(op)
    with pytest.raises(AssertionError):
        spec.compare({})
    wrong = deepcopy(spec.records)
    wrong['duplicate'] = deepcopy(wrong['m1'])
    with pytest.raises(AssertionError):
        spec.compare(wrong)
    wrong = deepcopy(spec.records)
    wrong['m1']['text'] = 'corrupt'
    with pytest.raises(AssertionError):
        spec.compare(wrong)
    allowed = spec.allowed_ids({'read'}, {'p'}, {'r1': {'project': 'p', 'owner': 'alice'}, 'r2': {'project': 'q', 'owner': 'alice'}}, 'alice')
    assert allowed == {'r1'}
    with pytest.raises(AssertionError):
        assert {'r1', 'r2'} <= allowed
