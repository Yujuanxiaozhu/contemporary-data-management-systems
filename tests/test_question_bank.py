"""S1-01..11: each db fixture runs against mock AND real Mongo when enabled."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import AutoReconnect, DuplicateKeyError

from app.core.database import ensure_indexes
from app.services import question_bank as service


def definition(kind='text', title='题目'):
    return {'type': kind, 'title': title, 'required': True, 'validation': {},
            'options': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}]
            if 'choice' in kind else []}


def create(logged, key='initial', kind='text'):
    r = logged.post('/api/questions', json={'definition': definition(kind)},
                    headers={'Idempotency-Key': key})
    assert r.status_code == 201, r.text
    return r.json()


def edit(logged, result, key, title='新版'):
    return logged.post('/api/questions/' + result['family']['question_id'] + '/versions',
        json={'parent_version_id': result['version']['question_version_id'],
              'expected_revision': result['family']['revision'], 'definition': definition(title=title)},
        headers={'Idempotency-Key': key})


@pytest.mark.parametrize('kind', ['single_choice', 'multiple_choice', 'text', 'number'])
def test_initial_family_and_default_required(logged, db, kind):
    r = create(logged, kind=kind)
    assert r['version']['version_no'] == 1
    assert r['version']['default_required'] is True
    assert r['version']['definition']['required'] is True
    assert r['family']['revision'] == 1 and r['family']['latest_pointer_valid']
    assert r['family']['latest_version_id'] == r['version']['question_version_id']
    assert db.question_versions.count_documents({}) == 1
    assert db.surveys.count_documents({}) == db.responses.count_documents({}) == 0


def test_versions_history_detail_restore_immutable(logged, db):
    one = create(logged)
    original = deepcopy(db.question_versions.find_one({}))
    two_response = edit(logged, one, 'two')
    assert two_response.status_code == 201, two_response.text
    two = two_response.json()
    three = edit(logged, two, 'three', title='第三版').json()
    qid = one['family']['question_id']
    page = logged.get(f'/api/questions/{qid}/versions?limit=2').json()
    assert [v['version_no'] for v in page['items']] == [3, 2]
    rest = logged.get(f'/api/questions/{qid}/versions', params={'cursor': page['next_cursor']}).json()
    assert [v['version_no'] for v in rest['items']] == [1]
    vid = one['version']['question_version_id']
    assert logged.get('/api/question-versions/' + vid).json() == one['version']
    body = {'source_version_id': vid, 'expected_revision': three['family']['revision']}
    restored = logged.post(f'/api/questions/{qid}/restore', json=body,
                          headers={'Idempotency-Key': 'restore'})
    assert restored.status_code == 201, restored.text
    four = restored.json()
    assert four['version']['version_no'] == 4
    assert four['version']['restored_from'] == vid
    assert four['version']['parent_version_id'] == three['version']['question_version_id']
    assert four['version']['question_version_id'] != vid
    assert four['version']['content_hash'] == one['version']['content_hash']
    retry = logged.post(f'/api/questions/{qid}/restore', json=body,
                        headers={'Idempotency-Key': 'restore'})
    assert retry.json()['version'] == four['version']
    assert db.question_versions.count_documents({}) == 4
    assert db.question_versions.find_one({'_id': original['_id']}) == original


def test_idempotency_body_resource_conflicts_and_same_content(logged, db):
    one = create(logged)
    again = create(logged)
    assert again == one
    conflict = logged.post('/api/questions', json={'definition': definition(title='其他')},
                           headers={'Idempotency-Key': 'initial'})
    assert conflict.status_code == 409
    assert conflict.json()['detail']['code'] == 'idempotency_conflict'
    second_family = create(logged, key='second-family')
    a = edit(logged, one, 'shared-edit-key')
    assert a.status_code == 201
    assert edit(logged, second_family, 'shared-edit-key').status_code == 409
    stale = edit(logged, one, 'new-key')
    assert stale.status_code == 409
    # Explicit new key, same content still expresses a new immutable version.
    same = edit(logged, a.json(), 'same-content')
    assert same.status_code == 201 and same.json()['version']['version_no'] == 3
    body = {'source_version_id': one['version']['question_version_id'], 'expected_revision': 3}
    qid = one['family']['question_id']
    assert logged.post(f'/api/questions/{qid}/restore', json=body,
                       headers={'Idempotency-Key': 'r'}).status_code == 201
    body['source_version_id'] = a.json()['version']['question_version_id']
    assert logged.post(f'/api/questions/{qid}/restore', json=body,
                       headers={'Idempotency-Key': 'r'}).status_code == 409


def test_owner_auth_same_origin_and_no_leaks(logged, db):
    one = create(logged)
    qid, vid, opid = one['family']['question_id'], one['version']['question_version_id'], one['operation_id']
    assert logged.post('/api/questions', json={'definition': definition()},
        headers={'Origin': 'https://untrusted.invalid', 'Idempotency-Key': 'x'}).status_code == 403
    assert logged.post('/api/auth/logout').status_code == 204
    assert logged.get('/api/questions').status_code == 401
    assert logged.post('/api/questions', json={'definition': definition()},
                       headers={'Idempotency-Key': 'unauthenticated'}).status_code == 401
    credentials = {'username': 'otherowner', 'password': 'test-password-only'}
    assert logged.post('/api/auth/register', json=credentials).status_code == 201
    assert logged.post('/api/auth/login', json=credentials).status_code == 200
    assert logged.get('/api/questions').json()['items'] == []
    for path in [f'/questions/{qid}', f'/questions/{qid}/versions', f'/question-versions/{vid}',
                 f'/stage2/operations/{opid}']:
        assert logged.get('/api' + path).status_code == 404
    assert edit(logged, one, 'steal').status_code == 404
    assert logged.post(f'/api/questions/{qid}/restore', json={'source_version_id': vid,
        'expected_revision': 1}, headers={'Idempotency-Key': 'steal'}).status_code == 404
    assert logged.post(f'/api/questions/{qid}/repair-latest', json={'expected_revision': 1}).status_code == 404
    assert logged.post(f'/api/stage2/operations/{opid}/resume').status_code == 404
    assert db.question_versions.count_documents({}) == 1


def test_invalid_api_and_pagination(logged, db):
    assert logged.post('/api/questions', json={'definition': definition()}).status_code == 422
    assert logged.post('/api/questions', json={'definition': definition(), 'owner_id': str(ObjectId())},
                       headers={'Idempotency-Key': 'x'}).status_code == 422
    assert logged.post('/api/questions', json={'definition': {**definition(), 'id': 'local'}},
                       headers={'Idempotency-Key': 'x'}).status_code == 422
    one = create(logged)
    second = create(logged, key='second')
    page = logged.get('/api/questions?limit=1').json()
    assert len(page['items']) == 1
    assert len(logged.get('/api/questions', params={'cursor': page['next_cursor']}).json()['items']) == 1
    for path in ['/api/questions/bad', '/api/question-versions/bad', '/api/questions?cursor=bad',
                 '/api/questions?limit=0', f"/api/questions/{one['family']['question_id']}/versions?cursor=0"]:
        assert logged.get(path).status_code == 422
    qid = one['family']['question_id']
    response = logged.post(f'/api/questions/{qid}/restore', json={
        'source_version_id': second['version']['question_version_id'], 'expected_revision': 1},
        headers={'Idempotency-Key': 'wrong-family'})
    assert response.status_code == 409
    assert db.question_versions.count_documents({}) == 2


@pytest.mark.parametrize('stage', ['reserved', 'version_inserted', 'committed', 'finalized'])
@pytest.mark.parametrize('action', ['create', 'version', 'restore'])
def test_interruption_resume_exactly_once(logged, db, monkeypatch, stage, action):
    initial = create(logged) if action != 'create' else None
    qid = initial['family']['question_id'] if initial else None
    original = deepcopy(db.question_versions.find_one({}))
    if action == 'create':
        path, body = '/api/questions', {'definition': definition()}
    elif action == 'version':
        path, body = f'/api/questions/{qid}/versions', {'definition': definition(title='v2'),
            'parent_version_id': initial['version']['question_version_id'], 'expected_revision': 1}
    else:
        path, body = f'/api/questions/{qid}/restore', {
            'source_version_id': initial['version']['question_version_id'], 'expected_revision': 1}
    def interrupt(name, op):
        if name == stage:
            raise AutoReconnect('injected interruption')
    monkeypatch.setattr(service, 'checkpoint', interrupt)
    r = logged.post(path, json=body, headers={'Idempotency-Key': 'interrupted'})
    assert r.status_code == 503, r.text
    opid = r.json()['detail']['operation_id']
    op = db.stage2_operations.find_one({'_id': ObjectId(opid)})
    before = db.question_versions.count_documents({})
    assert logged.get(f'/api/stage2/operations/{opid}').status_code == 200
    assert db.question_versions.count_documents({}) == before
    if stage == 'version_inserted':
        assert logged.get('/api/question-versions/' + str(op['version_id'])).status_code == 404
    monkeypatch.setattr(service, 'checkpoint', lambda *args: None)
    resumed = logged.post(f'/api/stage2/operations/{opid}/resume')
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['state'] == 'COMMITTED'
    retry = logged.post(path, json=body, headers={'Idempotency-Key': 'interrupted'})
    assert retry.status_code == 201, retry.text
    assert retry.json()['version'] == resumed.json()['result']['version']
    assert db.question_versions.count_documents({}) == (1 if action == 'create' else 2)
    assert retry.json()['family']['latest_pointer_valid']
    assert db.questions.find_one({'_id': op['question_id']})['_pending_version'] is None
    if original:
        assert db.question_versions.find_one({'_id': original['_id']}) == original


def test_pointer_repair_and_indexes(logged, db):
    one = create(logged)
    two = edit(logged, one, 'two').json()
    qid = one['family']['question_id']
    db.questions.update_one({'_id': ObjectId(qid)}, {'$set': {
        'latest_version_id': ObjectId(), 'committed_version_no': -1}})
    assert not logged.get('/api/questions/' + qid).json()['latest_pointer_valid']
    assert len(logged.get(f'/api/questions/{qid}/versions').json()['items']) == 2
    assert logged.post(f'/api/questions/{qid}/repair-latest', json={'expected_revision': 1}).status_code == 409
    repaired = logged.post(f'/api/questions/{qid}/repair-latest', json={'expected_revision': 2})
    assert repaired.status_code == 200
    assert repaired.json()['latest_version_id'] == two['version']['question_version_id']
    assert repaired.json()['latest_pointer_valid']
    assert logged.post(f'/api/questions/{qid}/repair-latest', json={'expected_revision': 2}).status_code == 200
    for override in [{'operation_id': ObjectId()}, {'version_no': 99}]:
        row = deepcopy(db.question_versions.find_one({}))
        row['_id'] = ObjectId()
        row.update(override)
        with pytest.raises(DuplicateKeyError):
            db.question_versions.insert_one(row)


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_creation_unique_versions(db, same_key):
    ensure_indexes(db)
    user = {'_id': ObjectId()}
    initial = service.write(db, user, 'initial', 'create', {'definition': definition()})
    qid = initial['family']['question_id']
    body = {'definition': definition(title='并发'), 'expected_revision': 1,
            'parent_version_id': initial['version']['question_version_id']}
    barrier = Barrier(6)
    def attempt(i):
        barrier.wait(timeout=10)
        try:
            return service.write(db, user, 'same' if same_key else f'key-{i}', 'version', body, qid)
        except HTTPException as exc:
            assert exc.status_code == 409, exc.detail
            return exc
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    success = [r for r in results if isinstance(r, dict)]
    assert success
    if same_key:
        assert len(success) == 6
        assert len({r['version']['question_version_id'] for r in success}) == 1
    else:
        assert len(success) == 1
    versions = list(db.question_versions.find({'question_id': ObjectId(qid)}))
    assert len(versions) == 2
    assert len({v['version_no'] for v in versions}) == 2
    # Fresh concurrent clients can retry with current revision/new key, producing serial history.
    for i in range(4):
        family = service.owned(db, qid, user)
        service.write(db, user, f'after-{i}', 'version', {**body, 'expected_revision': family['revision']}, qid)
    assert [v['version_no'] for v in service.history(db, family).sort('version_no', 1)] == list(range(1, 7))


def test_pending_blocks_pointer_repair_and_stale_resume(db, monkeypatch):
    ensure_indexes(db)
    user = {'_id': ObjectId()}
    initial = service.write(db, user, 'initial', 'create', {'definition': definition()})
    qid = initial['family']['question_id']
    body = {'definition': definition(), 'expected_revision': 1,
            'parent_version_id': initial['version']['question_version_id']}
    def stop(name, op):
        if name == 'reserved':
            raise AutoReconnect('interrupt')
    monkeypatch.setattr(service, 'checkpoint', stop)
    with pytest.raises(HTTPException) as first:
        service.write(db, user, 'first', 'version', body, qid)
    with pytest.raises(HTTPException) as blocked:
        service.write(db, user, 'second', 'version', body, qid)
    assert blocked.value.detail['code'] == 'operation_in_progress'
    with pytest.raises(HTTPException):
        service.repair_latest(db, qid, user, 1)
    monkeypatch.setattr(service, 'checkpoint', lambda *args: None)
    service.execute(db, service.get_operation(db, first.value.detail['operation_id'], user))
    with pytest.raises(HTTPException) as stale:
        service.execute(db, service.get_operation(db, blocked.value.detail['operation_id'], user))
    assert stale.value.detail['code'] == 'concurrent_modification'
    assert service.get_operation(db, blocked.value.detail['operation_id'], user)['state'] == 'FAILED'


def test_concurrent_resume_after_inserted_interruption(db, monkeypatch):
    ensure_indexes(db)
    user = {'_id': ObjectId()}
    def interrupt(name, op):
        if name == 'version_inserted':
            raise AutoReconnect('injected before commit marker')
    monkeypatch.setattr(service, 'checkpoint', interrupt)
    with pytest.raises(HTTPException) as exc:
        service.write(db, user, 'recover', 'create', {'definition': definition()})
    opid = exc.value.detail['operation_id']
    operation = service.get_operation(db, opid, user)
    assert operation['state'] == 'PREPARED'
    monkeypatch.setattr(service, 'checkpoint', lambda *args: None)
    barrier = Barrier(6)
    def resume(_):
        barrier.wait(timeout=10)
        return service.execute(db, operation)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(resume, range(6)))
    assert len({r['version']['question_version_id'] for r in results}) == 1
    assert db.question_versions.count_documents({}) == 1
    assert results[-1]['family']['latest_pointer_valid']


@pytest.mark.parametrize('stage', ['reserved', 'version_inserted', 'committed'])
def test_family_visibility_tracks_committed_versions(logged, db, monkeypatch, stage):
    """A durable operation is queryable without exposing an uncommitted family."""
    def interrupt(name, op):
        if name == stage:
            raise AutoReconnect('injected visibility boundary interruption')
    monkeypatch.setattr(service, 'checkpoint', interrupt)
    response = logged.post('/api/questions', json={'definition': definition()},
                           headers={'Idempotency-Key': 'visibility-boundary'})
    assert response.status_code == 503, response.text
    opid = response.json()['detail']['operation_id']
    operation = db.stage2_operations.find_one({'_id': ObjectId(opid)})
    qid, vid = str(operation['question_id']), str(operation['version_id'])
    before_reads = {
        'family': deepcopy(db.questions.find_one({'_id': operation['question_id']})),
        'operation': deepcopy(operation),
        'versions': list(db.question_versions.find({'question_id': operation['question_id']})),
    }
    status = logged.get(f'/api/stage2/operations/{opid}')
    assert status.status_code == 200
    committed = stage == 'committed'
    assert status.json()['state'] == ('COMMITTED' if committed else 'PREPARED')
    assert status.json()['published_result'] == (
        {'question_id': qid, 'question_version_id': vid} if committed else None)
    listing = logged.get('/api/questions?limit=1')
    detail = logged.get(f'/api/questions/{qid}')
    history = logged.get(f'/api/questions/{qid}/versions')
    version = logged.get(f'/api/question-versions/{vid}')
    assert listing.status_code == 200
    if committed:
        # The commit marker is authoritative even before revision/cache finalization.
        assert [f['question_id'] for f in listing.json()['items']] == [qid]
        assert detail.status_code == history.status_code == version.status_code == 200
        assert not detail.json()['latest_pointer_valid']
        assert [v['question_version_id'] for v in history.json()['items']] == [vid]
    else:
        assert listing.json() == {'items': [], 'next_cursor': None}
        assert detail.status_code == history.status_code == version.status_code == 404
    assert db.questions.find_one({'_id': operation['question_id']}) == before_reads['family']
    assert db.stage2_operations.find_one({'_id': operation['_id']}) == before_reads['operation']
    assert list(db.question_versions.find({'question_id': operation['question_id']})) == before_reads['versions']
    monkeypatch.setattr(service, 'checkpoint', lambda *args: None)
    resumed = logged.post(f'/api/stage2/operations/{opid}/resume')
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()['state'] == 'COMMITTED'
    assert resumed.json()['published_result'] == {'question_id': qid, 'question_version_id': vid}
    detail = logged.get(f'/api/questions/{qid}')
    assert detail.status_code == 200 and detail.json()['latest_pointer_valid']
    assert detail.json()['latest_version_id'] == vid and detail.json()['revision'] == 1
    assert [f['question_id'] for f in logged.get('/api/questions').json()['items']] == [qid]
    versions = logged.get(f'/api/questions/{qid}/versions')
    assert versions.status_code == 200
    assert [v['question_version_id'] for v in versions.json()['items']] == [vid]
    assert db.question_versions.count_documents({'question_id': operation['question_id']}) == 1
