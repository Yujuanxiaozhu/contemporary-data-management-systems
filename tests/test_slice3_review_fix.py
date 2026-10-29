"""Isolated mock + standalone Mongo regressions for slice3 review defects."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import AutoReconnect, DuplicateKeyError
import pytest

from app.services import revisions
from test_revisions import setup_survey, create_revision, source_state


def prepared(logged, db, monkeypatch):
    s = setup_survey(logged)
    def stop(name, op):
        if name == 'prepared':
            raise AutoReconnect('prepared interruption')
    monkeypatch.setattr(revisions, 'checkpoint', stop)
    r = create_revision(logged, s)
    assert r.status_code == 503
    monkeypatch.setattr(revisions, 'checkpoint', lambda *a: None)
    return s, db.revision_operations.find_one({'_id': ObjectId(r.json()['detail']['operation_id'])})


def test_late_recovery_cannot_resurrect_deleted_revision(logged, db, monkeypatch):
    s, op = prepared(logged, db, monkeypatch)
    paused, release = Event(), Event()
    before = source_state(db, s['id'])
    def stop(name, operation):
        if name == 'before_survey_insert' and not paused.is_set():
            paused.set()
            assert release.wait(15)
    monkeypatch.setattr(revisions, 'checkpoint', stop)
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(revisions.execute, db, deepcopy(op))
        try:
            assert paused.wait(10)
            child = revisions.execute(db, deepcopy(op))
            cid = str(child['_id'])
            assert logged.delete('/api/surveys/' + cid).status_code == 204
            barrier = db.surveys.find_one({'_id': child['_id']})
            assert barrier['_revision_deleted'] is True
            assert 'questions' not in barrier and barrier['public_token'] == child['public_token']
            assert logged.get('/api/surveys/' + cid).status_code == 404
            assert logged.get('/surveys/' + cid + '/edit').status_code == 404
            assert all(x['id'] != cid for x in logged.get('/api/surveys').json())
            assert cid not in logged.get('/dashboard').text
            assert logged.get('/api/public/surveys/' + child['public_token']).status_code == 404
            path = '/api/surveys/' + s['id'] + '/revision-operations/' + str(op['_id'])
            assert logged.get(path).json()['state'] == 'COMMITTED'
            assert logged.post(path + '/resume').status_code == 410
        finally:
            release.set()
        with pytest.raises(HTTPException) as error:
            late.result(timeout=15)
        assert error.value.status_code == 410
    assert db.surveys.find_one({'_id': op['result_survey_id']}) is None
    assert db.revision_operations.find_one({'_id': op['_id']})['result_deleted'] is True
    assert create_revision(logged, s).status_code == 410
    assert source_state(db, s['id']) == before


def test_crashed_attempt_retains_hidden_barrier_and_replay_is_safe(logged, db):
    s = setup_survey(logged)
    child = create_revision(logged, s).json()
    op = db.revision_operations.find_one({'key': 'revision'})
    db.revision_operations.update_one({'_id': op['_id']}, {'$addToSet': {'active_attempts': ObjectId()}})
    assert logged.delete('/api/surveys/' + child['id']).status_code == 204
    assert db.surveys.find_one({'_id': ObjectId(child['id'])})['_revision_deleted']
    for _ in range(2):
        assert create_revision(logged, s).status_code == 410
        assert logged.get('/api/surveys/' + child['id']).status_code == 404
    assert all(x['id'] != child['id'] for x in logged.get('/api/surveys').json())


@pytest.mark.parametrize('fault', ['before_insert', 'after_insert', 'read_after_insert', 'duplicate_winner_read'])
def test_initial_operation_write_unknown_confirmation(logged, db, monkeypatch, fault):
    s = setup_survey(logged)
    cls = type(db.revision_operations)
    original_insert, original_find = cls.insert_one, cls.find_one
    fired = False
    read_fault = False
    def insert(collection, doc, *args, **kwargs):
        nonlocal fired, read_fault
        if collection.name == 'revision_operations' and not fired:
            fired = True
            if fault == 'before_insert':
                raise AutoReconnect('before write')
            result = original_insert(collection, doc, *args, **kwargs)
            if fault == 'after_insert':
                raise AutoReconnect('ack lost after successful insert')
            if fault in ('read_after_insert', 'duplicate_winner_read'):
                read_fault = True
                if fault == 'duplicate_winner_read':
                    raise DuplicateKeyError('winner exists')
            return result
        return original_insert(collection, doc, *args, **kwargs)
    def find(collection, *args, **kwargs):
        nonlocal read_fault
        if collection.name == 'revision_operations' and read_fault:
            read_fault = False
            raise AutoReconnect('state read unavailable')
        return original_find(collection, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(cls, 'insert_one', insert)
        patch.setattr(cls, 'find_one', find)
        r = create_revision(logged, s)
    assert r.status_code == 503, r.text
    opid = r.json()['detail']['operation_id']
    stored = db.revision_operations.find_one({'_id': ObjectId(opid)})
    assert (stored is None) == (fault == 'before_insert')
    assert db.surveys.count_documents({'revision_of': ObjectId(s['id'])}) == 0
    path = '/api/surveys/' + s['id'] + '/revision-operations/' + opid
    if stored is None:
        assert logged.get(path).status_code == 404  # not durable; retry original key
        child = create_revision(logged, s)
        assert child.status_code == 201
        assert str(db.revision_operations.find_one({'key': 'revision'})['_id']) == opid
    else:
        child = logged.post(path + '/resume')
        assert child.status_code == 200, child.text
    assert create_revision(logged, s).json() == child.json()
    assert db.surveys.count_documents({'revision_of': ObjectId(s['id'])}) == 1


@pytest.mark.parametrize('fault', ['dict', 'duplicate', 'mismatch', 'empty', 'integer', 'missing', 'extra'])
def test_corrupt_binding_local_ids_rejected_without_writes(logged, db, fault):
    s = setup_survey(logged)
    query = {'survey_id': ObjectId(s['id']), 'schema_version': s['schema_version']}
    snap = db.survey_versions.find_one(query)
    values = snap['question_bindings']
    if fault == 'dict': values[0]['local_question_id'] = {'bad': 'id'}
    elif fault == 'duplicate': values[1]['local_question_id'] = values[0]['local_question_id']
    elif fault == 'mismatch': values[0]['local_question_id'] = 'unmatched'
    elif fault == 'empty': values[0]['local_question_id'] = ''
    elif fault == 'integer': values[0]['local_question_id'] = 1
    elif fault == 'missing': values.pop()
    else: values.append(deepcopy(values[0]))
    db.survey_versions.replace_one(query, snap)
    before = {name: deepcopy(list(db[name].find({}))) for name in db.list_collection_names()}
    response = create_revision(logged, s)
    assert response.status_code == 409 and response.json()['detail']['code'] == 'revision_source_invalid'
    after = {name: deepcopy(list(db[name].find({}))) for name in db.list_collection_names()}
    assert after == before


def test_multiple_retained_tombstones_keep_unique_public_tokens(logged, db):
    s = setup_survey(logged)
    for key in ['delete-one', 'delete-two']:
        child = create_revision(logged, s, key).json()
        op = db.revision_operations.find_one({'key': key})
        db.revision_operations.update_one({'_id': op['_id']}, {'$addToSet': {'active_attempts': ObjectId()}})
        assert logged.delete('/api/surveys/' + child['id']).status_code == 204
        assert create_revision(logged, s, key).status_code == 410
    assert db.surveys.count_documents({'_revision_deleted': True}) == 2
    assert len(logged.get('/api/surveys').json()) == 1
