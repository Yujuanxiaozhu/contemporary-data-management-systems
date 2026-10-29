"""Slice-2 smoke extension: real HTTP, fixed snapshots and immutable versions."""
from copy import deepcopy

from bson import ObjectId
from pymongo import MongoClient


def verify_bindings(client, check, survey, uri, name):
    assert name.startswith('survey_test_smoke_')
    created = client.post('/api/questions', json={'definition': {'type': 'number', 'title': '年龄',
        'required': True, 'validation': {'min': 0}}}, headers={'Idempotency-Key': 'family'})
    assert created.status_code == 201, created.text
    v = created.json();vid = v['version']['question_version_id']
    def attach(s, override, key):
        r = client.post('/api/surveys/' + s['id'] + '/question-references', json={
            'question_version_id': vid, 'required_override': override,
            'expected_schema_version': s['schema_version']}, headers={'Idempotency-Key': key})
        assert r.status_code == 201, r.text
        return r.json()
    a = attach(survey, True, 'a')
    b = attach(check('POST', '/api/surveys', 201, {'title': '草稿B'}).json(), False, 'b')
    path_a = '/api/surveys/' + a['id'];path_b = '/api/surveys/' + b['id']
    check('POST', path_a + '/publish', 200)
    public_a = '/api/public/surveys/' + a['public_token']
    check('POST', public_a + '/responses', 201, {'schema_version': a['schema_version'],
        'answers': [{'question_id': a['questions'][0]['id'], 'value': 10}]})
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name]
        old_snapshot = deepcopy(db.survey_versions.find_one({'survey_id': ObjectId(a['id'])}))
        old_responses = deepcopy(list(db.responses.find({'survey_id': ObjectId(a['id'])})))
    # A new default/version does not propagate to either existing occurrence.
    changed = client.post('/api/questions/' + v['family']['question_id'] + '/versions', json={
        'definition': {**v['version']['definition'], 'required': False, 'title': '新版'},
        'parent_version_id': vid, 'expected_revision': 1}, headers={'Idempotency-Key': 'new-default'})
    assert changed.status_code == 201
    assert check('GET', path_b, 200).json()['question_bindings'][0]['question_version_id'] == vid
    check('PUT', path_a + '/questions/' + a['questions'][0]['id'], 409, {'type': 'number', 'title': '拒绝'})
    edited = check('PUT', path_b + '/questions/' + b['questions'][0]['id'], 200,
                   {'type': 'number', 'title': 'B独立编辑', 'required': False, 'validation': {'min': 0}}).json()
    assert edited['question_bindings'][0]['question_version_id'] != vid
    assert not edited['questions'][0]['required']
    check('POST', path_b + '/publish', 200)
    check('POST', '/api/public/surveys/' + b['public_token'] + '/responses', 201,
          {'schema_version': edited['schema_version'], 'answers': [{'question_id': b['questions'][0]['id'], 'value': 30}]})
    for path, expected in [(path_a, 10), (path_b, 30)]:
        result = check('GET', path + '/stats', 200).json()
        assert result['versions'][0]['questions'][0]['statistics']['average'] == expected
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name]
        assert db.survey_versions.find_one({'_id': old_snapshot['_id']}) == old_snapshot
        assert list(db.responses.find({'survey_id': ObjectId(a['id'])})) == old_responses
        snapshot_b = db.survey_versions.find_one({'survey_id': ObjectId(b['id'])})
        assert snapshot_b['questions'][0]['required'] is False
        assert old_snapshot['questions'][0]['required'] is True
    print('SLICE2_FIXED_BINDINGS_REQUIRED_SNAPSHOT_AND_RESPONSES=PASS')
    fresh = check('POST', '/api/surveys', 201, {'title': '基础流程'}).json()
    survey.clear();survey.update(fresh)
