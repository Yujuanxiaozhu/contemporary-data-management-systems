from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

from bson import ObjectId
import pytest
from pymongo.errors import AutoReconnect

from app.services import revisions, question_bank
from app.schemas.survey import survey_out
from test_public_responses import setup_survey, payload, url


def source_state(db, sid):
    oid = ObjectId(sid)
    return {'survey': deepcopy(db.surveys.find_one({'_id': oid})),
        'snapshots': deepcopy(list(db.survey_versions.find({'survey_id': oid}))),
        'responses': deepcopy(list(db.responses.find({'survey_id': oid}))),
        'sessions': deepcopy(list(db.sessions.find({})))}


def create_revision(client, source, key='revision'):
    return client.post('/api/surveys/' + source['id'] + '/revisions', json={
        'source_schema_version': source['schema_version'], 'expected_schema_version': source['schema_version']},
        headers={'Idempotency-Key': key})


def legacy_source(client, db):
    s = client.post('/api/surveys', json={'title': 'legacy', 'allow_anonymous': True}).json()
    assert client.post('/api/surveys/' + s['id'] + '/publish').status_code == 200
    qs = [{'id': local, 'order': i, 'type': 'text', 'title': 'same content',
           'required': False, 'options': [], 'validation': {}} for i, local in enumerate(['a', 'b'], 1)]
    db.surveys.update_one({'_id': ObjectId(s['id'])}, {'$set': {'questions': qs}, '$unset': {'question_bindings': ''}})
    db.survey_versions.update_one({'survey_id': ObjectId(s['id'])}, {'$set': {'questions': qs}, '$unset': {'question_bindings': ''}})
    return s


@pytest.mark.parametrize('closed', [False, True])
def test_revision_identity_snapshot_bindings_and_independent_lifecycle(logged, db, closed):
    s = setup_survey(logged)
    assert logged.post(url(s) + '/responses', json=payload(s)).status_code == 201
    if closed:
        assert logged.post('/api/surveys/' + s['id'] + '/close').status_code == 200
    before = source_state(db, s['id'])
    r = create_revision(logged, s);assert r.status_code == 201, r.text
    child = r.json();cid = ObjectId(child['id'])
    assert child['id'] != s['id'] and child['public_token'] != s['public_token']
    assert child['revision_of'] == s['id'] and child['revision_source_schema_version'] == s['schema_version']
    assert child['status'] == 'draft' and child['schema_version'] == 1
    snap = before['snapshots'][0]
    assert child['questions'] == snap['questions'] and child['jump_rules'] == snap['jump_rules']
    assert child['question_bindings'] == s['question_bindings']
    assert db.responses.count_documents({'survey_id': cid}) == 0
    assert db.survey_versions.count_documents({'survey_id': cid}) == 0
    raw = db.surveys.find_one({'_id': cid})
    assert not any(k in raw for k in ['_pending_schema', '_pending_binding', '_binding_commits', '_last_response_admitted_at'])
    assert db.draft_operations.count_documents({'survey_id': cid}) == 0
    assert source_state(db, s['id']) == before
    edited = logged.put('/api/surveys/' + child['id'] + '/questions/q2', json={'type': 'text', 'title': 'child only'})
    assert edited.status_code == 200
    assert edited.json()['question_bindings'][1]['question_version_id'] != child['question_bindings'][1]['question_version_id']
    assert logged.post('/api/surveys/' + child['id'] + '/publish').status_code == 200
    assert logged.put('/api/surveys/' + child['id'] + '/questions/q2', json={'type': 'text', 'title': 'blocked'}).status_code == 409
    assert db.survey_versions.find_one({'survey_id': cid})['questions'][1]['title'] == 'child only'
    assert source_state(db, s['id']) == before


def test_revision_idempotency_new_intents_and_replay_after_edit(logged, db):
    s = setup_survey(logged);a = create_revision(logged, s).json()
    assert create_revision(logged, s).json() == a
    b = create_revision(logged, s, 'other').json();assert a['id'] != b['id']
    changed = logged.put('/api/surveys/' + a['id'] + '/questions/q2', json={'type': 'text', 'title': 'edited'})
    assert changed.status_code == 200
    assert create_revision(logged, s).json() == changed.json()
    assert logged.get('/api/surveys/' + b['id']).json() == b
    bad = logged.post('/api/surveys/' + s['id'] + '/revisions', json={
        'source_schema_version': 1, 'expected_schema_version': s['schema_version']}, headers={'Idempotency-Key': 'revision'})
    assert bad.status_code == 409 and bad.json()['detail']['code'] == 'idempotency_conflict'


def test_revision_uses_authoritative_snapshot_not_current_structure(logged, db):
    s = setup_survey(logged)
    db.surveys.update_one({'_id': ObjectId(s['id'])}, {'$set': {'questions.0.title': 'bad cache'}})
    before = source_state(db, s['id']);r = create_revision(logged, s)
    assert r.status_code == 201 and r.json()['questions'] == before['snapshots'][0]['questions']
    assert r.json()['questions'][0]['title'] != 'bad cache'
    assert source_state(db, s['id']) == before


@pytest.mark.parametrize('stage', ['prepared', 'resolved', 'survey_inserted', 'committed'])
def test_revision_interruption_resume_and_receipts(logged, db, monkeypatch, stage):
    s = setup_survey(logged);before = source_state(db, s['id'])
    def stop(name, op):
        if name == stage:raise AutoReconnect('injected revision interruption')
    monkeypatch.setattr(revisions, 'checkpoint', stop)
    r = create_revision(logged, s);assert r.status_code == 503, r.text
    opid = r.json()['detail']['operation_id'];path = '/api/surveys/' + s['id'] + '/revision-operations/' + opid
    op_before = db.revision_operations.find_one({'_id': ObjectId(opid)})
    assert logged.get(path).status_code == 200
    assert db.revision_operations.find_one({'_id': ObjectId(opid)}) == op_before
    monkeypatch.setattr(revisions, 'checkpoint', lambda *args: None)
    a = logged.post(path + '/resume');assert a.status_code == 200, a.text
    assert logged.post(path + '/resume').json() == a.json()
    assert create_revision(logged, s).json() == a.json()
    assert db.surveys.count_documents({'revision_of': ObjectId(s['id'])}) == 1
    assert source_state(db, s['id']) == before


def test_legacy_conversion_distinct_positions_reused_across_intents(logged, db):
    s = legacy_source(logged, db);before = source_state(db, s['id'])
    a = create_revision(logged, s);assert a.status_code == 201, a.text
    a = a.json();assert a['question_bindings'][0]['question_id'] != a['question_bindings'][1]['question_id']
    assert db.question_versions.count_documents({}) == 2
    b = create_revision(logged, s, 'another').json()
    assert a['question_bindings'] == b['question_bindings'] and a['id'] != b['id']
    assert db.question_versions.count_documents({}) == 2
    assert source_state(db, s['id']) == before
    plan = db.revision_operations.find_one({'key': 'revision'})['plans']
    assert {x['source']['local_question_id'] for x in plan} == {'a', 'b'}
    assert all(x['source']['survey_id'] == s['id'] for x in plan)
    other = legacy_source(logged, db);c = create_revision(logged, other).json()
    assert set(x['question_id'] for x in c['question_bindings']).isdisjoint(x['question_id'] for x in a['question_bindings'])


@pytest.mark.parametrize('child_fault', [False, True])
def test_legacy_conversion_failure_resumes_without_duplicate_versions(logged, db, monkeypatch, child_fault):
    s = legacy_source(logged, db);before = source_state(db, s['id'])
    def stop(name, op):
        if name == ('version_inserted' if child_fault else 'legacy_ready'):
            raise AutoReconnect('injected legacy conversion')
    monkeypatch.setattr(question_bank if child_fault else revisions, 'checkpoint', stop)
    r = create_revision(logged, s);assert r.status_code == 503
    opid = r.json()['detail']['operation_id']
    monkeypatch.setattr(question_bank if child_fault else revisions, 'checkpoint', lambda *args: None)
    resumed = logged.post('/api/surveys/' + s['id'] + '/revision-operations/' + opid + '/resume')
    assert resumed.status_code == 200, resumed.text
    assert db.question_versions.count_documents({}) == 2
    assert create_revision(logged, s).json() == resumed.json()
    assert source_state(db, s['id']) == before


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_revision_creation_standalone(logged, db, same_key):
    s = setup_survey(logged);user = db.users.find_one({'username': 'alice'});barrier = Barrier(4)
    before = source_state(db, s['id'])
    def worker(i):
        barrier.wait(timeout=10)
        return revisions.create(db, s['id'], user, {'source_schema_version': s['schema_version'],
            'expected_schema_version': s['schema_version']}, 'same' if same_key else 'intent-' + str(i))
    with ThreadPoolExecutor(max_workers=4) as pool:results = list(pool.map(worker, range(4)))
    assert len({x['_id'] for x in results}) == (1 if same_key else 4)
    assert db.surveys.count_documents({'revision_of': ObjectId(s['id'])}) == (1 if same_key else 4)
    assert source_state(db, s['id']) == before


def test_revision_owner_input_and_missing_snapshot_errors(logged, db):
    s = setup_survey(logged);path = '/api/surveys/' + s['id'] + '/revisions'
    assert logged.post(path, json={'source_schema_version': 1, 'expected_schema_version': 1}).status_code == 422
    db.survey_versions.delete_many({'survey_id': ObjectId(s['id'])})
    r = create_revision(logged, s);assert r.status_code == 409 and r.json()['detail']['code'] == 'revision_snapshot_required'
    assert db.revision_operations.count_documents({}) == 0
    logged.post('/api/auth/register', json={'username': 'another', 'password': 'password123'})
    logged.post('/api/auth/login', json={'username': 'another', 'password': 'password123'})
    assert create_revision(logged, s).status_code == 404


def test_delete_revision_does_not_resurrect_on_key_replay(logged, db):
    s = setup_survey(logged);a = create_revision(logged, s).json()
    assert logged.delete('/api/surveys/' + a['id']).status_code == 204
    r = create_revision(logged, s);assert r.status_code == 410
    assert db.surveys.find_one({'_id': ObjectId(a['id'])}) is None


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_legacy_revisions_reuse_deterministic_conversion(logged, db, same_key):
    s = legacy_source(logged, db);user = db.users.find_one({'username': 'alice'});barrier = Barrier(4)
    before = source_state(db, s['id'])
    def worker(i):
        barrier.wait(timeout=10)
        return revisions.create(db, s['id'], user, {'source_schema_version': s['schema_version'],
            'expected_schema_version': s['schema_version']}, 'one' if same_key else 'legacy-intent-' + str(i))
    with ThreadPoolExecutor(max_workers=4) as pool:children = list(pool.map(worker, range(4)))
    assert len({x['_id'] for x in children}) == (1 if same_key else 4)
    assert len({x['question_bindings'][0]['question_version_id'] for x in children}) == 1
    assert db.question_versions.count_documents({}) == 2
    assert source_state(db, s['id']) == before


def test_revision_insert_interruption_preserves_later_edits_and_blocks_early_delete(logged, db, monkeypatch):
    s = setup_survey(logged)
    def stop(name, op):
        if name == 'survey_inserted':raise AutoReconnect('after revision insert')
    monkeypatch.setattr(revisions, 'checkpoint', stop)
    r = create_revision(logged, s);assert r.status_code == 503
    opid = r.json()['detail']['operation_id'];op = db.revision_operations.find_one({'_id': ObjectId(opid)})
    cid = str(op['result_survey_id'])
    assert logged.delete('/api/surveys/' + cid).status_code == 409
    changed = logged.put('/api/surveys/' + cid + '/questions/q2', json={'type': 'text', 'title': 'after insert'})
    assert changed.status_code == 200
    monkeypatch.setattr(revisions, 'checkpoint', lambda *args: None)
    resumed = logged.post('/api/surveys/' + s['id'] + '/revision-operations/' + opid + '/resume')
    assert resumed.status_code == 200 and resumed.json() == changed.json()


@pytest.mark.parametrize('corruption', ['unhashable_local_id', 'bindings_null', 'binding_fields_missing', 'binding_id_invalid'])
def test_invalid_source_shape_rejected_before_revision_writes(logged, db, corruption):
    s = legacy_source(logged, db);sid = ObjectId(s['id'])
    snapshot = db.survey_versions.find_one({'survey_id': sid})
    if corruption == 'unhashable_local_id':snapshot['questions'][0]['id'] = {'invalid': 'id'}
    elif corruption == 'bindings_null':snapshot['question_bindings'] = None
    elif corruption == 'binding_fields_missing':snapshot['question_bindings'] = [{}]
    else:snapshot['question_bindings'] = [{'local_question_id': 'a', 'question_id': 'bad',
        'question_version_id': ObjectId(), 'content_hash': 'bad', 'effective_hash': 'bad'}]
    db.survey_versions.replace_one({'_id': snapshot['_id']}, snapshot)
    before = source_state(db, s['id']);r = create_revision(logged, s)
    assert r.status_code == 409 and r.json()['detail']['code'] == 'revision_source_invalid'
    assert db.revision_operations.count_documents({}) == 0
    assert db.question_versions.count_documents({}) == 0
    assert source_state(db, s['id']) == before
