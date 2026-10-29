import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect

from app.services import question_bank
from test_draft_bindings import make_survey, make_version, select


@pytest.mark.parametrize('kind', ['single_choice', 'multiple_choice', 'text', 'number'])
def test_bank_pages_four_types_versions_restore_and_summary(logged, db, kind):
    definition = {'type': kind, 'title': '<script>unsafe</script>', 'required': False}
    if 'choice' in kind:definition['options'] = [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}]
    r = logged.post('/api/questions', json={'definition': definition}, headers={'Idempotency-Key': 'create'})
    assert r.status_code == 201;v = r.json();qid = v['family']['question_id']
    family = logged.get('/api/questions').json()['items'][0]
    assert family['title'] == definition['title'] and family['type'] == kind
    assert family['version_count'] == 1 and family['latest_version_no'] == 1 and family['updated_at']
    page = logged.get('/question-bank/' + qid)
    assert page.status_code == 200 and '<script>unsafe</script>' not in page.text
    assert 'bank-question-form' in page.text and 'version-history' in page.text
    a = select(logged, make_survey(logged), v, False)
    newer = logged.post('/api/questions/' + qid + '/versions', json={'definition': {**definition, 'title': 'v2'},
        'parent_version_id': v['version']['question_version_id'], 'expected_revision': 1}, headers={'Idempotency-Key': 'v2'})
    assert newer.status_code == 201
    restore = {'source_version_id': v['version']['question_version_id'], 'expected_revision': 2}
    r = logged.post('/api/questions/' + qid + '/restore', json=restore, headers={'Idempotency-Key': 'restore'})
    assert r.status_code == 201 and r.json()['version']['restored_from'] == v['version']['question_version_id']
    assert logged.post('/api/questions/' + qid + '/restore', json=restore, headers={'Idempotency-Key': 'restore'}).json()['version'] == r.json()['version']
    assert logged.get('/api/surveys/' + a['id']).json()['question_bindings'] == a['question_bindings']
    assert logged.get('/api/questions/' + qid).json()['version_count'] == 3


def test_bank_page_access_pending_visibility_and_no_cross_owner(logged, db, monkeypatch):
    assert logged.get('/question-bank').status_code == 200
    def stop(name, op):
        if name == 'reserved':raise AutoReconnect('pending family')
    monkeypatch.setattr(question_bank, 'checkpoint', stop)
    r = logged.post('/api/questions', json={'definition': {'type': 'text', 'title': 'hidden'}}, headers={'Idempotency-Key': 'pending'})
    assert r.status_code == 503
    op = db.stage2_operations.find_one({'_id': ObjectId(r.json()['detail']['operation_id'])});qid = str(op['question_id'])
    assert logged.get('/api/questions').json()['items'] == []
    assert logged.get('/question-bank/' + qid).status_code == 404
    assert logged.get('/api/questions/' + qid + '/versions').status_code == 404
    monkeypatch.setattr(question_bank, 'checkpoint', lambda *args: None)
    assert logged.post('/api/stage2/operations/' + str(op['_id']) + '/resume').status_code == 200
    assert logged.get('/question-bank/' + qid).status_code == 200
    logged.post('/api/auth/register', json={'username': 'other', 'password': 'password123'})
    logged.post('/api/auth/login', json={'username': 'other', 'password': 'password123'})
    assert logged.get('/question-bank/' + qid).status_code == 404
    assert logged.get('/api/questions').json()['items'] == []
    logged.post('/api/auth/logout')
    assert logged.get('/question-bank', follow_redirects=False).status_code == 303


@pytest.mark.parametrize('override', [None, True, False])
def test_picker_render_fixed_history_required_and_readonly(logged, db, override):
    v = make_version(logged);s = select(logged, make_survey(logged), v, override)
    path = '/surveys/' + s['id'] + '/edit';page = logged.get(path)
    assert page.status_code == 200
    assert 'id="bank-picker"' in page.text and 'required_override' in page.text
    assert v['version']['question_version_id'] in page.text and '固定版本 v1' in page.text
    assert logged.post('/api/surveys/' + s['id'] + '/publish').status_code == 200
    page = logged.get(path)
    assert 'id="question-form"' not in page.text and 'id="rule-form"' not in page.text
    assert 'id="bank-picker"' not in page.text and 'data-revision-source' in page.text
    assert '修改 published 问卷会生成新的历史版本' not in page.text
    assert 'data-revision-source' in logged.get('/dashboard').text
