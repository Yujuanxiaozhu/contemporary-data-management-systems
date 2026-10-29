"""Independent review regressions; all original tests remain unchanged."""
from copy import deepcopy
from types import SimpleNamespace

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.services import draft_bindings as binding, question_bank as bank
from test_draft_bindings import make_survey, make_version, select


def stored(db):
    return {name: deepcopy(list(db[name].find({}))) for name in (
        'surveys', 'survey_versions', 'responses', 'questions', 'question_versions',
        'draft_operations', 'stage2_operations')}


@pytest.mark.parametrize('published', [False, True])
@pytest.mark.parametrize('lagging_state', [False, True])
def test_superseded_resume_preserves_every_record(logged, db, published, lagging_state):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    a = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'A'},
                    headers={'Idempotency-Key': 'A'})
    assert a.status_code == 201
    op = db.draft_operations.find_one({'key': 'explicit:A'})
    b = logged.put(path + '/questions/q', json={'type': 'text', 'title': 'B'},
                   headers={'Idempotency-Key': 'B'})
    assert b.status_code == 200
    assert b.json()['schema_version'] > a.json()['schema_version']
    if published:
        assert logged.post(path + '/publish').status_code == 200
    if lagging_state:
        # A receipt is authoritative even if the final operation marker lagged.
        db.draft_operations.update_one({'_id': op['_id']}, {'$set': {'state': 'PREPARED'}})
    before = stored(db)
    operation_path = path + '/binding-operations/' + str(op['_id'])
    status = logged.get(operation_path)
    assert status.status_code == 200
    assert status.json()['result_schema_version'] == a.json()['schema_version']
    assert status.json()['current_schema_version'] == b.json()['schema_version']
    assert status.json()['superseded'] is True
    for _ in range(2):
        resumed = logged.post(operation_path + '/resume')
        assert resumed.status_code == 409
        assert resumed.json()['detail']['code'] == 'operation_superseded'
        assert resumed.json()['detail']['next_action'] == 'read_current_survey'
        assert 'questions' not in resumed.json()
    if not published:
        replay = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'A'},
                             headers={'Idempotency-Key': 'A'})
        assert replay.status_code == 409
        assert replay.json()['detail']['code'] == 'operation_superseded'
    assert stored(db) == before
    current = logged.get(path).json()
    assert current['questions'][0]['title'] == 'B'
    assert current['schema_version'] == b.json()['schema_version']


def test_same_structure_published_resume_returns_current_document(logged, db):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    a = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'A'},
                    headers={'Idempotency-Key': 'A'})
    assert a.status_code == 201
    op = db.draft_operations.find_one({'key': 'explicit:A'})
    assert logged.post(path + '/publish').status_code == 200
    expected = logged.get(path).json();before = stored(db)
    result = logged.post(path + '/binding-operations/' + str(op['_id']) + '/resume')
    assert result.status_code == 200
    assert result.json() == expected
    assert result.json()['status'] == 'published'
    assert stored(db) == before


@pytest.mark.parametrize('key', [None, 'float-edit'])
@pytest.mark.parametrize('override', [None, True, False])
def test_numeric_representation_creates_exact_version(logged, db, key, override):
    v = make_version(logged)
    # The helper version has integer min=0; use the requested 1/1.0 boundary.
    v = logged.post('/api/questions/' + v['family']['question_id'] + '/versions', json={
        'parent_version_id': v['version']['question_version_id'], 'expected_revision': 1,
        'definition': {**v['version']['definition'], 'validation': {'min': 1}}},
        headers={'Idempotency-Key': 'integer'}).json()
    s = select(logged, make_survey(logged), v, override)
    original = deepcopy(list(db.question_versions.find({})))
    path = '/api/surveys/' + s['id'] + '/questions/' + s['questions'][0]['id']
    payload = {**s['questions'][0], 'validation': {'min': 1.0}}
    headers = {'Idempotency-Key': key} if key else {}
    result = logged.put(path, json=payload, headers=headers)
    assert result.status_code == 200, result.text
    changed = result.json();bound = changed['question_bindings'][0]
    assert bound['question_version_id'] != v['version']['question_version_id']
    new = db.question_versions.find_one({'_id': ObjectId(bound['question_version_id'])})
    assert type(new['definition']['validation']['min']) is float
    assert bound['content_hash'] == new['content_hash'] == bank.digest(new['definition'])
    assert new['content_hash'] != v['version']['content_hash']
    assert bound['effective_hash'] == bank.digest(binding.definition(changed['questions'][0]))
    assert changed['question_bindings'][0]['required_override'] is override
    count = db.question_versions.count_documents({})
    assert logged.put(path, json=payload, headers=headers).json() == changed
    assert db.question_versions.count_documents({}) == count
    assert logged.post('/api/surveys/' + s['id'] + '/publish').status_code == 200
    snapshot = db.survey_versions.find_one({'survey_id': ObjectId(s['id'])})
    assert type(snapshot['questions'][0]['validation']['min']) is float
    assert snapshot['question_bindings'][0]['effective_hash'] == bound['effective_hash']
    for old in original:
        assert db.question_versions.find_one({'_id': old['_id']}) == old


@pytest.mark.parametrize('corruption', ['definition', 'effective_hash', 'content_hash'])
def test_publish_rejects_numeric_binding_hash_mismatch(logged, db, corruption):
    v = make_version(logged);s = select(logged, make_survey(logged), v, False)
    sid = ObjectId(s['id']);raw = db.surveys.find_one({'_id': sid})
    if corruption == 'definition':
        raw['questions'][0]['validation']['min'] = 0.0
        # Even matching the tampered effective hash cannot authorize a new definition.
        raw['question_bindings'][0]['effective_hash'] = bank.digest(binding.definition(raw['questions'][0]))
    else:
        raw['question_bindings'][0][corruption] = '0' * 64
    db.surveys.replace_one({'_id': sid}, raw)
    before = stored(db)
    result = logged.post('/api/surveys/' + s['id'] + '/publish')
    assert result.status_code == 409
    assert result.json()['detail']['code'] == 'binding_mismatch'
    assert stored(db) == before


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_nonfinite_published_answer_rejected_independently(logged, db, value):
    v = make_version(logged);s = select(logged, make_survey(logged), v)
    assert logged.post('/api/surveys/' + s['id'] + '/publish').status_code == 200
    before = stored(db)
    payload = ('{"schema_version":' + str(s['schema_version']) + ',"answers":[{"question_id":"'
               + s['questions'][0]['id'] + '","value":' + value + '}]}')
    result = logged.post('/api/public/surveys/' + s['public_token'] + '/responses',
                         content=payload, headers={'Content-Type': 'application/json'})
    assert result.status_code == 422
    detail = result.json()['detail']
    assert detail['valid'] is False and detail['errors']
    assert all('code' in error and 'message' in error for error in detail['errors'])
    assert value not in result.text
    assert stored(db) == before


def test_exact_normalization_and_plan_are_numeric_type_sensitive(monkeypatch):
    integer = bank.normalize({'type': 'number', 'title': 'Boundary', 'validation': {'min': 1}})
    floating = bank.normalize({'type': 'number', 'title': 'Boundary', 'validation': {'min': 1.0}})
    assert type(integer['validation']['min']) is int
    assert type(floating['validation']['min']) is float
    assert bank.digest(integer) != bank.digest(floating)
    assert not binding.exact_match(integer, floating)
    qid, vid = ObjectId(), ObjectId()
    version = {'_id': vid, 'question_id': qid, 'definition': integer, 'content_hash': bank.digest(integer)}
    monkeypatch.setattr(bank, 'get_version', lambda *args: version)
    monkeypatch.setattr(bank, 'owned', lambda *args: {'_id': qid, 'revision': 1})
    survey = {'questions': [], 'question_bindings': [{'local_question_id': 'q', 'question_id': qid,
        'question_version_id': vid, 'content_hash': version['content_hash'], 'required_override': None}]}
    plans = binding.plans_for(None, survey, {'_id': ObjectId()}, {
        'questions': [{**floating, 'id': 'q', 'order': 1}]})
    assert plans[0]['action'] == 'version'
    assert type(plans[0]['body']['definition']['validation']['min']) is float


def test_exact_match_rejects_nonfinite_and_ignores_dictionary_order():
    assert binding.exact_match({'x': 1, 'y': 2}, {'y': 2, 'x': 1})
    assert not binding.exact_match({'x': float('nan')}, {'x': float('nan')})


def test_publish_compares_exact_expected_definition_in_pure_logic(monkeypatch):
    definition = bank.normalize({'type': 'number', 'title': 'Boundary', 'validation': {'min': 1}})
    qid, vid = ObjectId(), ObjectId()
    version = {'_id': vid, 'question_id': qid, 'definition': definition, 'content_hash': bank.digest(definition)}
    monkeypatch.setattr(bank, 'get_version', lambda *args: version)
    q = {**deepcopy(definition), 'id': 'q', 'order': 1}
    q['validation']['min'] = 1.0
    survey = {'questions': [q], 'jump_rules': [], 'question_bindings': [{
        'local_question_id': 'q', 'question_id': qid, 'question_version_id': vid,
        'required_override': None, 'content_hash': version['content_hash'],
        'effective_hash': bank.digest(binding.definition(q))}]}
    with pytest.raises(HTTPException) as error:
        binding.validate_publish(None, survey, {'_id': ObjectId()})
    assert error.value.status_code == 409 and error.value.detail['code'] == 'binding_mismatch'
