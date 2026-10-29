"""Slice 2 acceptance, independent of the preserved stage-1 test assertions."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

from bson import ObjectId
from fastapi import HTTPException
import pytest
from pymongo.errors import AutoReconnect

from app.services import draft_bindings as binding, question_bank, questions, versions, surveys


def make_survey(client):
    r = client.post('/api/surveys', json={'title': '绑定', 'allow_anonymous': True,
                                        'allow_multiple_submissions': True})
    assert r.status_code == 201, r.text
    return r.json()


def make_version(client, key='family', required=True):
    r = client.post('/api/questions', json={'definition': {'type': 'number', 'title': '年龄',
        'required': required, 'validation': {'min': 0}}}, headers={'Idempotency-Key': key})
    assert r.status_code == 201, r.text
    return r.json()


def select(client, survey, version, override=None, key='select'):
    r = client.post('/api/surveys/' + survey['id'] + '/question-references', json={
        'question_version_id': version['version']['question_version_id'], 'required_override': override,
        'expected_schema_version': survey['schema_version']}, headers={'Idempotency-Key': key})
    assert r.status_code == 201, r.text
    return r.json()


def test_two_drafts_pin_history_and_old_put_creates_new_version(logged, db):
    version = make_version(logged)
    a = select(logged, make_survey(logged), version)
    b = select(logged, make_survey(logged), version)
    old_versions = list(db.question_versions.find({}))
    local = a['questions'][0]['id']
    r = logged.put(f"/api/surveys/{a['id']}/questions/{local}", json={
        'type': 'number', 'title': '更新的年龄', 'required': True, 'validation': {'min': 0}})
    assert r.status_code == 200, r.text
    changed = r.json()
    assert changed['question_bindings'][0]['question_id'] == version['family']['question_id']
    assert changed['question_bindings'][0]['question_version_id'] != version['version']['question_version_id']
    assert changed['questions'][0]['id'] == local
    again = logged.put(f"/api/surveys/{a['id']}/questions/{local}", json={
        'type': 'number', 'title': '更新的年龄', 'required': True, 'validation': {'min': 0}})
    assert again.json()['schema_version'] == changed['schema_version']
    assert db.question_versions.count_documents({}) == 2
    assert logged.get('/api/surveys/' + b['id']).json() == b
    historical = select(logged, make_survey(logged), version)
    assert historical['questions'][0]['title'] == '年龄'
    for old in old_versions:
        assert db.question_versions.find_one({'_id': old['_id']}) == old
    assert logged.delete(f"/api/surveys/{a['id']}/questions/{local}").status_code == 200
    assert db.question_versions.count_documents({}) == 2
    assert logged.get('/api/surveys/' + b['id']).json()['question_bindings'] == b['question_bindings']


@pytest.mark.parametrize('override,expected', [(None, True), (True, True), (False, False)])
def test_required_overrides_freeze_in_snapshot(logged, db, override, expected):
    version = make_version(logged)
    survey = select(logged, make_survey(logged), version, override)
    assert survey['question_bindings'][0]['required_override'] is override
    assert survey['questions'][0]['required'] is expected
    path = '/api/surveys/' + survey['id']
    assert logged.post(path + '/publish').status_code == 200
    snapshot = deepcopy(db.survey_versions.find_one({'survey_id': ObjectId(survey['id'])}))
    assert snapshot['questions'][0]['required'] is expected
    assert snapshot['question_bindings'][0]['required_override'] is override
    changed = logged.post('/api/questions/' + version['family']['question_id'] + '/versions', json={
        'parent_version_id': version['version']['question_version_id'], 'expected_revision': 1,
        'definition': {**version['version']['definition'], 'required': False}},
        headers={'Idempotency-Key': 'default-changed'})
    assert changed.status_code == 201
    assert db.survey_versions.find_one({'_id': snapshot['_id']}) == snapshot
    assert logged.get(path).json()['questions'][0]['required'] is expected


def test_same_version_different_override_and_explicit_binding(logged, db):
    v = make_version(logged, required=False)
    a = select(logged, make_survey(logged), v, True)
    b = select(logged, make_survey(logged), v, False)
    assert a['questions'][0]['required'] and not b['questions'][0]['required']
    local = a['questions'][0]['id']
    path = f"/api/surveys/{a['id']}/questions/{local}/binding"
    body = {'question_version_id': v['version']['question_version_id'], 'required_override': None,
            'expected_schema_version': a['schema_version']}
    r = logged.put(path, json=body, headers={'Idempotency-Key': 'inherit'})
    assert r.status_code == 200, r.text
    assert not r.json()['questions'][0]['required']
    assert logged.put(path, json=body, headers={'Idempotency-Key': 'inherit'}).json() == r.json()
    assert db.question_versions.count_documents({}) == 1
    assert logged.get('/api/surveys/' + b['id']).json()['question_bindings'] == b['question_bindings']


def test_legacy_put_optional_new_family_and_idempotency(logged, db):
    survey = make_survey(logged)
    path = '/api/surveys/' + survey['id']
    body = {'id': 'stable', 'type': 'text', 'title': '第一题', 'required': False}
    a = logged.post(path + '/questions', json=body, headers={'Idempotency-Key': 'add'})
    assert a.status_code == 201, a.text
    assert logged.post(path + '/questions', json=body, headers={'Idempotency-Key': 'add'}).json() == a.json()
    old = deepcopy(db.question_versions.find_one({}))
    payload = {'type': 'text', 'title': '新含义', 'required': False, 'new_family': True}
    updated = logged.put(path + '/questions/stable', json=payload, headers={'Idempotency-Key': 'new-family'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['question_bindings'][0]['question_id'] != a.json()['question_bindings'][0]['question_id']
    assert logged.put(path + '/questions/stable', json=payload,
                      headers={'Idempotency-Key': 'new-family'}).json() == updated.json()
    assert db.question_versions.count_documents({}) == 2
    assert db.question_versions.find_one({'_id': old['_id']}) == old
    conflict = logged.put(path + '/questions/stable', json={**payload, 'title': '不同'},
                          headers={'Idempotency-Key': 'new-family'})
    assert conflict.status_code == 409


def test_required_only_old_put_and_null_override_do_not_mutate_version(logged, db):
    v = make_version(logged)
    s = select(logged, make_survey(logged), v)
    path = f"/api/surveys/{s['id']}/questions/{s['questions'][0]['id']}"
    body = {**v['version']['definition'], 'required': False}
    r = logged.put(path, json=body)
    assert r.status_code == 200 and r.json()['question_bindings'][0]['required_override'] is False
    inherited = logged.put(path, json={**body, 'required_override': None})
    assert inherited.status_code == 200 and inherited.json()['questions'][0]['required'] is True
    assert inherited.json()['question_bindings'][0]['required_override'] is None
    assert db.question_versions.count_documents({}) == 1


@pytest.mark.parametrize('closed', [False, True])
def test_all_published_structure_paths_frozen_and_data_unchanged(logged, db, closed):
    v = make_version(logged)
    s = select(logged, make_survey(logged), v, False)
    path = '/api/surveys/' + s['id'];local = s['questions'][0]['id']
    assert logged.post(path + '/publish').status_code == 200
    public = '/api/public/surveys/' + s['public_token']
    assert logged.post(public + '/responses', json={'schema_version': s['schema_version'],
        'answers': [{'question_id': local, 'value': 10}]}).status_code == 201
    if closed:
        assert logged.post(path + '/close').status_code == 200
    before = {n: list(db[n].find({})) for n in ('surveys', 'survey_versions', 'responses', 'question_versions')}
    actions = [('POST', '/questions', {'type': 'text', 'title': '不允许'}),
        ('PUT', '/questions/' + local, {'type': 'number', 'title': '不允许'}),
        ('DELETE', '/questions/' + local, None), ('POST', '/jump-rules', {}),
        ('PUT', '/jump-rules/missing', {}), ('DELETE', '/jump-rules/missing', None),
        ('POST', '/question-references', {'question_version_id': v['version']['question_version_id'],
                                        'expected_schema_version': s['schema_version']}),
        ('PUT', '/questions/' + local + '/binding', {'question_version_id': v['version']['question_version_id'],
                                                   'expected_schema_version': s['schema_version']})]
    for method, suffix, body in actions:
        r = logged.request(method, path + suffix, json=body, headers={'Idempotency-Key': suffix})
        assert r.status_code == 409, (method, suffix, r.text)
    user = db.users.find_one({'username': 'alice'});raw = db.surveys.find_one({'_id': ObjectId(s['id'])})
    for call in [lambda: questions.commit_structure(db, raw, user, {'questions': []}),
                 lambda: versions.snapshot_commit(db, raw, {'questions': []}, 'bypass'),
                 lambda: surveys.update_survey(db, s['id'], user, {'questions': []}),
                 lambda: versions.snapshot_commit(db, raw, {'status': 'draft'}, 'reopen')]:
        with pytest.raises(HTTPException) as exc:
            call()
        assert exc.value.status_code == 409
    with pytest.raises(HTTPException) as invalid_transition:
        surveys.transition(db, s['id'], user, 'draft')
    assert invalid_transition.value.status_code == 422
    for n, rows in before.items():
        assert list(db[n].find({})) == rows


def test_jump_and_local_order_preserved_and_conflict_has_no_versions(logged, db):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    q = {'id': 'source', 'type': 'single_choice', 'title': '路线',
         'options': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}]}
    assert logged.post(path + '/questions', json=q).status_code == 201
    assert logged.post(path + '/questions', json={'id': 'target', 'type': 'text', 'title': '终点'}).status_code == 201
    rule = {'id': 'jump', 'source_question_id': 'source', 'target_question_id': 'target',
            'operator': 'equals', 'value': 'a', 'priority': 1}
    assert logged.post(path + '/jump-rules', json=rule).status_code == 201
    before = db.question_versions.count_documents({})
    invalid = logged.put(path + '/questions/source', json={'type': 'text', 'title': '冲突'})
    assert invalid.status_code == 409 and db.question_versions.count_documents({}) == before
    assert logged.put(path + '/questions/source', json={**q, 'title': '路线新版'}).status_code == 200
    current = logged.get(path).json()
    assert [x['id'] for x in current['questions']] == ['source', 'target']
    assert current['jump_rules'] == [rule]
    assert logged.post(path + '/publish').status_code == 200
    assert logged.post('/api/public/surveys/' + s['public_token'] + '/next', json={
        'schema_version': current['schema_version'], 'current_question_id': 'source', 'answer': 'a'}).json()['next_question_id'] == 'target'


def test_unowned_missing_versions_and_invalid_binding_are_rejected(logged, db):
    v = make_version(logged);s = make_survey(logged);path = '/api/surveys/' + s['id']
    def ref(vid, key):
        return logged.post(path + '/question-references', json={'question_version_id': vid,
            'expected_schema_version': 1}, headers={'Idempotency-Key': key})
    assert ref(str(ObjectId()), 'missing').status_code == 404
    assert ref('invalid', 'bad').status_code == 422
    db.questions.update_one({'_id': ObjectId(v['family']['question_id'])}, {'$set': {'owner_id': ObjectId()}})
    assert ref(v['version']['question_version_id'], 'foreign').status_code == 404
    assert db.surveys.find_one({'_id': ObjectId(s['id'])})['questions'] == []


@pytest.mark.parametrize('stage', ['reserved', 'version_ready', 'resolved', 'survey_committed'])
def test_binding_interruption_recovers_without_duplicate_versions(logged, db, monkeypatch, stage):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    added = logged.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': '旧'}).json()
    original = list(db.question_versions.find({}))
    body = {'type': 'text', 'title': '新'}
    def stop(name, op):
        if name == stage:
            raise AutoReconnect('injected binding interruption')
    monkeypatch.setattr(binding, 'checkpoint', stop)
    r = logged.put(path + '/questions/q', json=body, headers={'Idempotency-Key': 'edit'})
    assert r.status_code == 503, r.text
    opid = r.json()['detail']['operation_id']
    assert logged.get(path + '/binding-operations/' + opid).status_code == 200
    monkeypatch.setattr(binding, 'checkpoint', lambda *a: None)
    resumed = logged.post(path + '/binding-operations/' + opid + '/resume')
    assert resumed.status_code == 200, resumed.text
    retry = logged.put(path + '/questions/q', json=body, headers={'Idempotency-Key': 'edit'})
    assert retry.json() == resumed.json()
    assert db.question_versions.count_documents({}) == 2
    assert resumed.json()['schema_version'] == added['schema_version'] + 1
    for old in original:
        assert db.question_versions.find_one({'_id': old['_id']}) == old


def test_slice1_child_interruption_is_resumed_by_draft_operation(logged, db, monkeypatch):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    def stop(name, op):
        if name == 'version_inserted':
            raise AutoReconnect('child version fault')
    monkeypatch.setattr(question_bank, 'checkpoint', stop)
    r = logged.post(path + '/questions', json={'type': 'text', 'title': '新'}, headers={'Idempotency-Key': 'add'})
    assert r.status_code == 503
    opid = r.json()['detail']['operation_id']
    assert db.draft_operations.find_one({'_id': ObjectId(opid)}) is not None
    monkeypatch.setattr(question_bank, 'checkpoint', lambda *a: None)
    assert logged.post(path + '/binding-operations/' + opid + '/resume').status_code == 200
    assert db.question_versions.count_documents({}) == 1


def test_publish_rejects_binding_tamper_and_legacy_draft_adapts_only_on_write(logged, db):
    s = make_survey(logged);path = '/api/surveys/' + s['id'];sid = ObjectId(s['id'])
    legacy = {'id': 'legacy', 'type': 'text', 'title': '旧草稿', 'required': False, 'order': 1,
              'options': [], 'validation': {}}
    db.surveys.update_one({'_id': sid}, {'$set': {'questions': [legacy]}, '$unset': {'question_bindings': ''}})
    assert logged.get(path).status_code == 200 and db.question_versions.count_documents({}) == 0
    assert logged.post(path + '/publish').status_code == 409
    adapted = logged.put(path + '/questions/legacy', json={'type': 'text', 'title': '旧草稿'})
    assert adapted.status_code == 200 and len(adapted.json()['question_bindings']) == 1
    db.surveys.update_one({'_id': sid}, {'$set': {'questions.0.title': '被篡改'}})
    assert logged.post(path + '/publish').status_code == 409
    assert db.survey_versions.count_documents({}) == 0


def test_history_statistics_through_legal_separate_drafts_and_legacy_snapshot(logged, db):
    v = make_version(logged)
    a = select(logged, make_survey(logged), v)
    b = select(logged, make_survey(logged), v)
    old_snapshots = []
    for s, number in [(a, 10), (b, 30)]:
        assert logged.post('/api/surveys/' + s['id'] + '/publish').status_code == 200
        assert logged.post('/api/public/surveys/' + s['public_token'] + '/responses', json={
            'schema_version': s['schema_version'], 'answers': [{'question_id': s['questions'][0]['id'], 'value': number}]}).status_code == 201
        result = logged.get('/api/surveys/' + s['id'] + '/stats')
        assert result.status_code == 200, result.text
        assert result.json()['versions'][0]['questions'][0]['statistics']['average'] == number
        old_snapshots.extend(deepcopy(list(db.survey_versions.find({'survey_id': ObjectId(s['id'])}))))
    # Old standalone snapshots lacking bindings remain interpretable.
    for snapshot in old_snapshots:
        db.survey_versions.update_one({'_id': snapshot['_id']}, {'$unset': {'question_bindings': ''}})
    legacy_before = list(db.survey_versions.find({}));responses_before = list(db.responses.find({}))
    for s in (a, b):
        assert logged.get('/api/surveys/' + s['id'] + '/stats').status_code == 200
    assert list(db.survey_versions.find({})) == legacy_before
    assert list(db.responses.find({})) == responses_before


def test_reference_conflicts_and_effective_required_validation(logged, db):
    v = make_version(logged);other = make_version(logged, key='other')
    s = select(logged, make_survey(logged), v)
    path = f"/api/surveys/{s['id']}/questions/{s['questions'][0]['id']}/binding"
    r = logged.put(path, json={'question_version_id': other['version']['question_version_id'],
        'expected_schema_version': s['schema_version']}, headers={'Idempotency-Key': 'wrong-family'})
    assert r.status_code == 409
    assert logged.get('/api/surveys/' + s['id']).json() == s
    optional = logged.post('/api/questions', json={'definition': {'type': 'text', 'title': '空值',
        'required': False, 'validation': {'max_length': 0}}}, headers={'Idempotency-Key': 'empty'}).json()
    fresh = make_survey(logged)
    r = logged.post('/api/surveys/' + fresh['id'] + '/question-references', json={
        'question_version_id': optional['version']['question_version_id'], 'required_override': True,
        'expected_schema_version': 1}, headers={'Idempotency-Key': 'unsatisfiable'})
    assert r.status_code == 422
    assert logged.get('/api/surveys/' + fresh['id']).json()['questions'] == []


def test_legacy_published_pending_is_not_auto_completed(logged, db):
    s = make_survey(logged);path = '/api/surveys/' + s['id'];sid = ObjectId(s['id'])
    assert logged.post(path + '/publish').status_code == 200
    raw = db.surveys.find_one({'_id': sid})
    old = db.survey_versions.find_one({'survey_id': sid})
    fake = deepcopy(old);fake['_id'] = ObjectId();fake['schema_version'] += 1
    pending = {'id': 'old-published-write', 'base_version': raw['schema_version'], 'base_status': 'published',
               'updates': {'questions': [], 'schema_version': fake['schema_version']}, 'snapshot': fake}
    db.surveys.update_one({'_id': sid}, {'$set': {'_pending_schema': pending}})
    before = db.surveys.find_one({'_id': sid})
    assert logged.get(path).status_code == 409
    assert logged.post(path + '/questions', json={'type': 'text', 'title': '不可恢复改题'}).status_code == 409
    assert db.surveys.find_one({'_id': sid}) == before
    assert list(db.survey_versions.find({'survey_id': sid})) == [old]


def test_concurrent_binding_resumes_and_current_structure_are_idempotent(logged, db, monkeypatch):
    s = make_survey(logged);path = '/api/surveys/' + s['id']
    def stop(name, op):
        if name == 'version_ready':
            raise AutoReconnect('after child commit')
    monkeypatch.setattr(binding, 'checkpoint', stop)
    r = logged.post(path + '/questions', json={'id': 'stable', 'type': 'text', 'title': '并发恢复'},
                    headers={'Idempotency-Key': 'once'})
    assert r.status_code == 503
    op = db.draft_operations.find_one({'_id': ObjectId(r.json()['detail']['operation_id'])})
    monkeypatch.setattr(binding, 'checkpoint', lambda *a: None)
    barrier = Barrier(4)
    def resume(_):
        barrier.wait(timeout=10)
        return binding.execute(db, op)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(resume, range(4)))
    assert {x['schema_version'] for x in results} == {2}
    assert db.question_versions.count_documents({}) == 1
    current = db.surveys.find_one({'_id': ObjectId(s['id'])})
    assert current['_binding_commits'].count(op['_id']) == 1
    assert '_pending_binding' not in current
    assert len(current['question_bindings']) == 1


def test_legal_new_draft_preserves_historical_options_and_new_family_statistics(logged, db):
    a = make_survey(logged);path_a = '/api/surveys/' + a['id']
    definition = {'id': 'q', 'type': 'single_choice', 'title': '旧选项',
                  'options': [{'id': 'a', 'label': '旧苹果'}, {'id': 'b', 'label': '旧香蕉'}]}
    a = logged.post(path_a + '/questions', json=definition).json()
    assert logged.post(path_a + '/publish').status_code == 200
    assert logged.post('/api/public/surveys/' + a['public_token'] + '/responses', json={
        'schema_version': a['schema_version'], 'answers': [{'question_id': 'q', 'value': 'a'}]}).status_code == 201
    old_snapshots = deepcopy(list(db.survey_versions.find({'survey_id': ObjectId(a['id'])})))
    old_answers = deepcopy(list(db.responses.find({'survey_id': ObjectId(a['id'])})))
    selected = {'version': {'question_version_id': a['question_bindings'][0]['question_version_id']}}
    b = select(logged, make_survey(logged), selected)
    path_b = '/api/surveys/' + b['id'];local = b['questions'][0]['id']
    # Meaning/type changes are explicit new-family intent, in a separate legal draft.
    b = logged.put(path_b + '/questions/' + local,
                   json={'type': 'number', 'title': '年龄', 'new_family': True}).json()
    assert b['question_bindings'][0]['question_id'] != a['question_bindings'][0]['question_id']
    assert logged.post(path_b + '/publish').status_code == 200
    assert logged.post('/api/public/surveys/' + b['public_token'] + '/responses', json={
        'schema_version': b['schema_version'], 'answers': [{'question_id': local, 'value': 42}]}).status_code == 201
    old_stats = logged.get(path_a + '/stats').json()['versions'][0]['questions'][0]['statistics']
    new_stats = logged.get(path_b + '/stats').json()['versions'][0]['questions'][0]['statistics']
    assert old_stats['options'][0]['label'] == '旧苹果' and old_stats['options'][0]['count'] == 1
    assert new_stats['average'] == 42
    assert list(db.survey_versions.find({'survey_id': ObjectId(a['id'])})) == old_snapshots
    assert list(db.responses.find({'survey_id': ObjectId(a['id'])})) == old_answers


def test_family_cas_conflict_audited_without_stranding_draft(logged, db, monkeypatch):
    v = make_version(logged);s = select(logged, make_survey(logged), v)
    path = '/api/surveys/' + s['id'];local = s['questions'][0]['id']
    fired = []
    def concurrent_family_change(name, op):
        if name == 'reserved' and not fired:
            fired.append(True)
            user = db.users.find_one({'username': 'alice'})
            question_bank.write(db, user, 'external', 'version', {
                'definition': {**v['version']['definition'], 'title': '外部新版'},
                'parent_version_id': v['version']['question_version_id'], 'expected_revision': 1},
                v['family']['question_id'])
    monkeypatch.setattr(binding, 'checkpoint', concurrent_family_change)
    payload = {**v['version']['definition'], 'title': '本草稿编辑'}
    r = logged.put(path + '/questions/' + local, json=payload, headers={'Idempotency-Key': 'conflict'})
    assert r.status_code == 409, r.text
    raw = db.surveys.find_one({'_id': ObjectId(s['id'])})
    assert '_pending_binding' not in raw and raw['schema_version'] == s['schema_version']
    assert raw['question_bindings'][0]['question_version_id'] == ObjectId(v['version']['question_version_id'])
    assert db.draft_operations.find_one({'key': 'explicit:conflict'})['state'] == 'FAILED'
    retried = logged.put(path + '/questions/' + local, json=payload, headers={'Idempotency-Key': 'fresh'})
    assert retried.status_code == 200, retried.text
    assert db.question_versions.count_documents({}) == 3
