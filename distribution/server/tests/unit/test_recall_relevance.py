"""Invented protocol fixtures only; no benchmark corpus, model, network or DB."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from agents_memory_collab.recall_relevance import (
    merge_evidence, native_evidence, scoped_native_results,
)


def item(text, key):
    return {'id': key, 'text': text, 'score': 1 / (key + 1)}


def scoped(label, n):
    return [item(f'{label} 실험의 가상 규칙 {i}는 신호-{i}를 보관한다.', i) for i in range(n)]


def test_native_scores_are_preserved_without_substituting_reciprocal_rank():
    scores = {'final': .18, 'reranker': .012, 'semantic': None, 'keyword': 3.5}
    hit = {'id': 'native-unit-1', 'scores': dict(scores)}
    actual = native_evidence(hit, 4, ['source-b', 'source-a', 'source-a'])
    assert actual == {'native_id': 'native-unit-1', 'rank': 4,
                      'source_ids': ['source-a', 'source-b'], 'scores': scores}
    assert hit['scores'] == scores and actual['scores'] is not hit['scores']
    assert actual['scores']['reranker'] != 1 / actual['rank']


def test_nonfinite_and_non_numeric_values_do_not_enter_score_evidence():
    actual = native_evidence({'scores': {'final': float('nan'), 'reranker': True,
                                         'semantic': .6, 'keyword': None, 'payload': 'unknown'}}, 1, ['s'])
    assert actual['scores'] == {'semantic': .6, 'keyword': None}


def test_evidence_merge_keeps_distinct_native_sources_and_does_not_mutate_inputs():
    first = native_evidence({'id': 'one'}, 1, ['a'])
    second = native_evidence({'id': 'two'}, 2, ['b'])
    original = [first]
    assert merge_evidence(original, [first, second]) == [first, second]
    assert original == [first]


def test_four_relevant_sources_are_preserved_without_a_fixed_top_three():
    wanted = scoped('가상단위Alpha', 4)
    other = scoped('가상단위Beta', 2)
    inputs = [wanted[0], other[0], *wanted[1:], other[1]]
    result = scoped_native_results('가상단위Alpha 실험의 모든 규칙을 설명해 줘.', inputs)
    assert result == wanted
    assert all(a is b for a, b in zip(result, wanted))


def test_five_relevant_sources_survive_an_unrelated_high_native_rank():
    wanted = scoped('가상단위Gamma', 5)
    other = scoped('가상단위Delta', 2)
    assert scoped_native_results('가상단위Gamma 실험의 규칙은?', [other[0], *wanted, other[1]]) == wanted


def test_an_unmentioned_entity_does_not_create_a_scope_for_semantic_queries():
    inputs = scoped('가상단위Alpha', 3) + scoped('가상단위Beta', 2)
    assert scoped_native_results('복구 전에 어떤 흔적을 남겨야 할까?', inputs) is inputs


def test_semantic_paraphrase_and_unnamed_exception_are_retained():
    main = scoped('가상단위Alpha', 1)[0]
    exception = item('기본 설정의 예외는 복원 자료를 따로 보관하는 것이다.', 8)
    paraphrase = item('A rollback needs an immutable copy of its previous configuration.', 9)
    other = scoped('가상단위Beta', 1)[0]
    assert scoped_native_results('가상단위Alpha 실험의 복원 규칙을 바꿔 말해 줘.',
                                 [main, exception, paraphrase, other]) == [main, exception, paraphrase]


def test_generic_exception_subject_is_not_an_alias_that_reintroduces_noise():
    main = scoped('가상단위Alpha', 1)[0]
    exception = item('긴급 복구의 예외는 원래 증거를 두 곳에 보관하는 것이다.', 7)
    other = item('가상단위Beta 실험의 긴급 복구는 임시 증거를 사용한다.', 8)
    assert scoped_native_results('가상단위Alpha 실험의 긴급 복구 규칙은?',
                                 [main, exception, other]) == [main, exception]


def test_multiple_named_subjects_are_a_union_and_can_return_five_sources():
    first, second, third = scoped('가상단위Alpha', 2), scoped('가상단위Beta', 3), scoped('가상단위Gamma', 1)
    inputs = [*first, third[0], *second]
    assert scoped_native_results('가상단위Alpha 실험과 가상단위Beta 실험의 규칙을 함께 알려줘.', inputs) == first + second


def test_subject_position_is_not_assumed_to_be_the_first_query_word():
    first, other = scoped('가상단위Alpha', 2), scoped('가상단위Beta', 1)
    assert scoped_native_results('예외부터 설명하고 가상단위Alpha 실험의 전체 규칙을 정리해 줘.', first + other) == first


def test_explicit_alias_links_other_source_headings_without_entity_metadata():
    declaration = item("가상단위Alpha 실험(별칭 'UnitAlias')의 첫 규칙은 신호를 보관하는 것이다.", 0)
    alias_source = item("UnitAlias's second rule keeps an audit artifact.", 1)
    other = item("Project UnitOther's rule keeps a disposable note.", 2)
    assert scoped_native_results('UnitAlias의 규칙을 설명해 줘.', [declaration, alias_source, other]) == [declaration, alias_source]


def test_ambiguous_alias_falls_back_to_native_instead_of_choosing_an_entity():
    first = item("가상단위Alpha 실험(별칭 'SharedUnit')의 규칙은 붉은 신호다.", 0)
    second = item("가상단위Beta 실험(별칭 'SharedUnit')의 규칙은 푸른 신호다.", 1)
    inputs = [first, second]
    assert scoped_native_results('SharedUnit의 규칙을 알려줘.', inputs) is inputs


def test_ambiguous_alias_source_is_not_rejected_even_for_an_unambiguous_query():
    first = item("가상단위Alpha 실험(별칭 'SharedUnit')의 규칙은 붉은 신호다.", 0)
    second = item("가상단위Beta 실험(별칭 'SharedUnit')의 규칙은 푸른 신호다.", 1)
    ambiguous = item("SharedUnit's exception keeps an extra proof.", 2)
    assert scoped_native_results('가상단위Alpha 실험의 규칙은?',
                                 [first, second, ambiguous]) == [first, ambiguous]


def test_unicode_normalization_and_alias_word_boundaries():
    first = item("Project UnitAlpha's rule keeps artifact-a.", 0)
    second = item("Project UnitBeta's rule keeps artifact-b.", 1)
    inputs = [first, second]
    assert scoped_native_results('ＵｎｉｔＡｌｐｈａ rules?', inputs) == [first]
    assert scoped_native_results('UnitAlphaV2 rules?', inputs) is inputs


@pytest.mark.parametrize('letter', ['A', 'X', '가'])
def test_role_shorthand_with_one_character_does_not_establish_query_scope(letter):
    first = item(f"Project {letter}'s rule keeps one marker.", 0)
    other = item("Project UnitOther's rule keeps another marker.", 1)
    inputs = [first, other]
    assert scoped_native_results(f'What is {letter.lower()} recovery rule?', inputs) is inputs
    # Keeping the full declared name usable is distinct from accepting its
    # ambiguous shorthand (including an ordinary English article).
    assert scoped_native_results(f'Describe Project {letter} recovery rules.', inputs) == [first]


@pytest.mark.parametrize('alias', ['it', 'this', 'there', 'they', '그것', '여기', 'a', 'X'])
def test_explicit_pronoun_deictic_or_single_character_alias_keeps_native_fallback(alias):
    first = item(f"Project UnitAlpha (aka {alias})'s rule keeps one marker.", 0)
    other = item("Project UnitBeta's rule keeps another marker.", 1)
    inputs = [first, other]
    assert scoped_native_results(f'How should {alias} be recovered?', inputs) is inputs
    assert scoped_native_results('Describe Project UnitAlpha recovery rules.', inputs) == [first]


@pytest.mark.parametrize('name', ['It', 'Them', '그것'])
def test_role_prefix_does_not_make_a_pronoun_an_unambiguous_shorthand(name):
    first = item(f"Project {name}'s rule keeps one marker.", 0)
    inputs = [first, item("Project UnitBeta's rule keeps another marker.", 1)]
    assert scoped_native_results(f'How should {name.lower()} be recovered?', inputs) is inputs
    assert scoped_native_results(f'Describe Project {name} recovery rules.', inputs) == [first]


def test_generic_article_and_pronoun_queries_do_not_promote_role_names_or_aliases():
    for declaration, query in [
        ("Project A's rule keeps one marker.", 'What is a recovery rule?'),
        ("Project UnitAlpha (aka it)'s rule keeps one marker.", 'How should it be recovered?'),
    ]:
        inputs = [item(declaration, 0), item("Project UnitBeta's rule keeps another marker.", 1)]
        assert scoped_native_results(query, inputs) is inputs


@pytest.mark.parametrize('query', [
    'Do not use Project UnitAlpha; describe the other recovery policy.',
    "Don't use Project UnitAlpha; describe the other recovery policy.",
    'Project UnitAlpha should never define the requested policy.',
    'Describe recovery without Project UnitAlpha.',
    'Describe a policy other than Project UnitAlpha.',
    'Exclude Project UnitAlpha when describing the policy.',
    'Project UnitAlpha말고 다른 복구 정책을 알려 줘.',
    'Project UnitAlpha가 아닌 복구 정책은?',
    'Project UnitAlpha를 제외하고 복구 정책을 알려 줘.',
    'Project UnitAlpha를 빼고 복구 정책을 알려 줘.',
])
def test_negated_subject_mention_cannot_be_treated_as_positive_scope(query):
    inputs = [item("Project UnitAlpha's rule keeps one marker.", 0),
              item("Project UnitBeta's rule keeps another marker.", 1)]
    assert scoped_native_results(query, inputs) is inputs


def test_positive_subject_mention_with_negation_like_substring_still_scopes():
    first = item("Project UnitNotation's rule keeps one marker.", 0)
    other = item("Project UnitBeta's rule keeps another marker.", 1)
    assert scoped_native_results('Describe Project UnitNotation recovery rules.', [first, other]) == [first]


def test_memory_request_preface_is_not_mistaken_for_a_different_subject():
    first = item("Project UnitOmega's rule keeps its previous configuration.", 0)
    prefaced = item("Please remember Project UnitOmega's exception keeps an extra audit.", 1)
    separated = item("Remember:Project UnitOmega's last rule preserves a receipt.", 2)
    other = item("Project UnitOther's rule keeps an unrelated receipt.", 3)
    assert scoped_native_results('UnitOmega rules?', [first, prefaced, separated, other]) == [first, prefaced, separated]


def test_cross_reference_to_requested_subject_keeps_complete_original_text():
    main = scoped('가상단위Alpha', 1)[0]
    relationship = item('가상단위Beta 실험의 예외는 가상단위Alpha 실험과 함께 적용한다.\n추가 조건도 그대로 보관한다.', 4)
    unrelated = scoped('가상단위Gamma', 1)[0]
    actual = scoped_native_results('가상단위Alpha 실험의 예외를 알려줘.', [main, relationship, unrelated])
    assert actual == [main, relationship] and actual[1]['text'] == relationship['text']


def test_no_literal_subject_does_not_invent_entity_metadata_or_backfill():
    inputs = [item('Retain the original audit; semantic paraphrases are permitted.', 0)]
    assert scoped_native_results('자료를 재검토하려면 무엇이 필요할까?', inputs) is inputs
    assert scoped_native_results('규칙을 알려줘.', []) == []


def test_alias_declarations_do_not_cross_native_bank_or_author_boundaries():
    first = item("Project UnitAlpha (also known as SharedUnit)'s rule keeps artifact-a.", 0)
    other = item("Project UnitBeta's rule keeps artifact-b.", 1)
    independent = item("SharedUnit's rule keeps an independent artifact.", 2)
    independent_other = item("Project UnitGamma's rule keeps artifact-c.", 3)
    inputs = [first, independent, other, independent_other]
    banks = {id(first): 'bank-a', id(other): 'bank-a',
             id(independent): 'bank-b', id(independent_other): 'bank-b'}
    result = scoped_native_results('UnitAlpha rules?', inputs, lambda value: banks[id(value)])
    # The other bank has no evidence identifying this query subject. It keeps
    # Native semantic results rather than inheriting somebody else's alias.
    assert result == [first, independent, independent_other]


def test_store_filters_only_authorized_native_nominations_before_limit():
    from agents_memory_collab.store import Store
    actor = SimpleNamespace(user_id='owner')
    rows = [dict(id=f'source-{i}', text=text, kind='fact', revision=1, updated_at=None,
                 engine_bank='bank', engine_document=f'doc-{i}', project='chosen',
                 author_id='owner', author='reader') for i, text in enumerate([
        '가상단위Beta 실험의 규칙은 unrelated다.',
        *[v['text'] for v in scoped('가상단위Alpha', 5)],
    ])]
    class Pool:
        async def fetch(self, query, *params):
            assert params[0] == actor.user_id and params[1] == 'chosen'
            assert "m.user_id=$1" in query and "NOT m.deleted" in query
            if query.startswith('SELECT DISTINCT'):
                return [{'engine_bank': 'bank'}]
            assert 'engine_document=ANY' in query
            return [r for r in rows if r['engine_document'] in params[-1]]
    class Engine:
        integrated = True
        async def recall(self, bank, query):
            assert bank == 'bank' and query == '가상단위Alpha 실험의 규칙은?'
            good = [{'id': f'native-{i}', 'text': r['text'], 'source_documents': [r['engine_document']],
                     'scores': {'final': .9-i*.05, 'reranker': .6-i*.01}}
                    for i, r in enumerate(rows)]
            # An incomplete/unauthorized observation must never publish evidence.
            return [{'id': 'foreign-native-id', 'text': 'foreign-private',
                     'source_documents': ['doc-1', 'foreign-document'],
                     'scores': {'final': 1, 'reranker': 1}}, *good]
    store = Store.__new__(Store)
    store.pool, store.memory_engine = Pool(), Engine()
    async def active(who):
        assert who is actor
    store._active = active
    result = asyncio.run(store.search(actor, '가상단위Alpha 실험의 규칙은?', project='chosen', limit=5))
    assert [m['id'] for m in result['memories']] == [r['id'] for r in rows[1:]]
    for memory in result['memories']:
        assert memory['native_evidence'][0]['source_ids'] == [memory['id']]
        assert 'reranker' in memory['native_evidence'][0]['scores']
    assert 'foreign-native-id' not in str(result) and 'foreign-private' not in str(result)


def test_existing_named_type_priority_and_native_scores_remain_distinct():
    from agents_memory_collab.store import Store
    actor = SimpleNamespace(user_id='owner')
    rows = [dict(id=f'source-{i}', text=text, kind='fact', revision=1, updated_at=None,
                 engine_bank='bank', engine_document=f'doc-{i}', project='chosen',
                 author_id='owner', author='reader') for i, text in enumerate([
        'ExampleShape.width is measured in centimeters.',
        'class ExampleShape describes the shape contract.',
    ])]
    class Pool:
        async def fetch(self, query, *params):
            return [{'engine_bank': 'bank'}] if query.startswith('SELECT DISTINCT') else rows
    class Engine:
        integrated = True
        async def recall(self, bank, query):
            return [{'id': f'native-{i}', 'text': row['text'], 'source_documents': [row['engine_document']],
                     'scores': {'final': .7 - i*.1, 'reranker': .4 - i*.1}}
                    for i, row in enumerate(rows)]
    store = Store.__new__(Store)
    store.pool, store.memory_engine = Pool(), Engine()
    async def active(who):
        assert who is actor
    store._active = active
    memories = asyncio.run(store.search(actor, 'Explain model ExampleShape', project='chosen'))['memories']
    assert [m['id'] for m in memories] == ['source-1', 'source-0']
    assert memories[0]['score'] == .5
    assert memories[0]['native_evidence'][0]['scores']['final'] == .6
