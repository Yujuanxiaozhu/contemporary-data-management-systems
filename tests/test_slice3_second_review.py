"""Deterministic survey_committed race, each on UUID mock/standalone database."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.services import draft_bindings
from test_revisions import setup_survey, create_revision, source_state


def database_state(db):
    return {name: deepcopy(list(db[name].find({}))) for name in db.list_collection_names()}


@pytest.mark.parametrize('retain_tombstone', [False, True])
def test_survey_committed_late_editor_returns_410_after_revision_delete(logged, db, monkeypatch, retain_tombstone):
    source = setup_survey(logged)
    child = create_revision(logged, source).json()
    cid = ObjectId(child['id'])
    revision_op = db.revision_operations.find_one({'result_survey_id': cid})
    if retain_tombstone:
        # Model an independently crashed revision attempt, retaining the barrier.
        db.revision_operations.update_one({'_id': revision_op['_id']},
                                         {'$addToSet': {'active_attempts': ObjectId()}})
    original_source = source_state(db, source['id'])
    arrived, release = Event(), Event()
    captured = {}
    def pause(name, op):
        if name == 'survey_committed':
            captured['operation'] = deepcopy(op)
            arrived.set()
            assert release.wait(20)
    monkeypatch.setattr(draft_bindings, 'checkpoint', pause)
    with ThreadPoolExecutor(max_workers=1) as pool:
        late = pool.submit(logged.put, '/api/surveys/' + child['id'] + '/questions/q2',
                           json={'type': 'text', 'title': 'late committed edit'},
                           headers={'Idempotency-Key': 'late-edit'})
        try:
            assert arrived.wait(15)
            raw = db.surveys.find_one({'_id': cid})
            assert captured['operation']['_id'] in raw['_binding_commits']
            assert raw['questions'][1]['title'] == 'late committed edit'
            assert logged.delete('/api/surveys/' + child['id']).status_code == 204
            marker = db.surveys.find_one({'_id': cid})
            assert (marker is not None) == retain_tombstone
            if marker is not None:
                assert marker['_revision_deleted'] is True and 'schema_version' not in marker
            after_delete = database_state(db)
        finally:
            release.set()
        response = late.result(timeout=20)
    assert response.status_code == 410, response.text
    assert response.json()['detail']['code'] == 'revision_result_deleted'
    assert database_state(db) == after_delete
    op = db.draft_operations.find_one({'_id': captured['operation']['_id']})
    with pytest.raises(HTTPException) as error:
        draft_bindings.execute(db, op)
    assert error.value.status_code == 410
    with pytest.raises(HTTPException) as error:
        draft_bindings.result_survey(db, op)
    assert error.value.status_code == 410
    assert database_state(db) == after_delete
    assert source_state(db, source['id']) == original_source
    assert logged.get('/api/surveys/' + child['id']).status_code == 404
    assert logged.get('/surveys/' + child['id'] + '/edit').status_code == 404
    assert all(s['id'] != child['id'] for s in logged.get('/api/surveys').json())
    assert logged.get('/api/public/surveys/' + child['public_token']).status_code == 404
