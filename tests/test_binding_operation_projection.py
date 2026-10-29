"""Read-only logical operation state, independent of preserved regressions."""
import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect

from app.services import draft_bindings
from test_draft_bindings import make_survey
from test_slice2_review_fix import stored


@pytest.mark.parametrize('lagging', [False, True])
@pytest.mark.parametrize('advanced', [False, True])
@pytest.mark.parametrize('published', [False, True])
def test_receipt_projects_committed_without_writes(logged, db, lagging, advanced, published):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    a = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'A'},
                    headers={'Idempotency-Key': 'projection-A'})
    assert a.status_code == 201, a.text
    current = a.json()
    op = db.draft_operations.find_one({'key': 'explicit:projection-A'})
    assert op['state'] == 'COMMITTED'
    assert op['_id'] in db.surveys.find_one({'_id': ObjectId(s['id'])})['_binding_commits']
    if advanced:
        b = logged.put(path + '/questions/q', json={'type': 'text', 'title': 'B'},
                       headers={'Idempotency-Key': 'projection-B'})
        assert b.status_code == 200, b.text
        current = b.json()
    if published:
        assert logged.post(path + '/publish').status_code == 200
        answer = logged.post('/api/public/surveys/' + s['public_token'] + '/responses', json={
            'schema_version': current['schema_version'], 'answers': [{'question_id': 'q', 'value': 'answer'}]})
        assert answer.status_code == 201, answer.text
    if lagging:
        db.draft_operations.update_one({'_id': op['_id']}, {'$set': {'state': 'PREPARED'}})
    before = stored(db)
    operation_path = path + '/binding-operations/' + str(op['_id'])
    for _ in range(2):
        result = logged.get(operation_path)
        assert result.status_code == 200
        assert result.json() == {
            'operation_id': str(op['_id']), 'state': 'COMMITTED',
            'result_schema_version': a.json()['schema_version'],
            'current_schema_version': current['schema_version'], 'superseded': advanced}
        assert stored(db) == before
    assert db.draft_operations.find_one({'_id': op['_id']})['state'] == ('PREPARED' if lagging else 'COMMITTED')
    if advanced:
        for _ in range(2):
            resumed = logged.post(operation_path + '/resume')
            assert resumed.status_code == 409
            assert resumed.json()['detail']['code'] == 'operation_superseded'
            assert stored(db) == before
    elif published and not lagging:
        # Preserve the previously accepted same-schema published recovery behavior.
        expected = logged.get(path).json()
        resumed = logged.post(operation_path + '/resume')
        assert resumed.status_code == 200 and resumed.json() == expected
        assert resumed.json()['status'] == 'published'
        assert stored(db) == before


def test_no_receipt_keeps_prepared_projection_read_only(logged, db, monkeypatch):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    def stop(name, op):
        if name == 'reserved':
            raise AutoReconnect('injected before binding receipt')
    monkeypatch.setattr(draft_bindings, 'checkpoint', stop)
    r = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'Pending'},
                    headers={'Idempotency-Key': 'projection-pending'})
    assert r.status_code == 503
    opid = r.json()['detail']['operation_id']
    before = stored(db)
    result = logged.get(path + '/binding-operations/' + opid)
    assert result.status_code == 200
    assert result.json() == {'operation_id': opid, 'state': 'PREPARED',
        'result_schema_version': None, 'current_schema_version': 1, 'superseded': False}
    assert stored(db) == before
