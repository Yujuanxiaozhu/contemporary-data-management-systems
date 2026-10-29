"""Real HTTP extension for the two slice-2 review corrections."""
from copy import deepcopy

from bson import ObjectId
from pymongo import MongoClient

from smoke_draft_bindings import verify_bindings


def verify_review_fix(client, check, survey, uri, name):
    assert name.startswith('survey_test_smoke_')
    verify_bindings(client, check, survey, uri, name)
    path = '/api/surveys/' + survey['id']
    body = {'id': 'boundary', 'type': 'number', 'title': 'Boundary',
            'required': True, 'validation': {'min': 1}}
    a = client.post(path + '/questions', json=body, headers={'Idempotency-Key': 'review-A'})
    assert a.status_code == 201, a.text
    b = client.put(path + '/questions/boundary', json={**body, 'validation': {'min': 1.0}},
                   headers={'Idempotency-Key': 'review-B'})
    assert b.status_code == 200, b.text
    assert a.json()['question_bindings'][0]['question_version_id'] != b.json()['question_bindings'][0]['question_version_id']
    check('POST', path + '/publish', 200)
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name]
        op = db.draft_operations.find_one({'survey_id': ObjectId(survey['id']), 'key': 'explicit:review-A'})
        before = {n: deepcopy(list(db[n].find({}))) for n in (
            'surveys', 'survey_versions', 'responses', 'question_versions', 'draft_operations', 'stage2_operations')}
    resumed = check('POST', path + '/binding-operations/' + str(op['_id']) + '/resume', 409)
    assert resumed.json()['detail']['code'] == 'operation_superseded'
    for value in ['NaN', 'Infinity', '-Infinity']:
        payload = ('{"schema_version":' + str(b.json()['schema_version'])
                   + ',"answers":[{"question_id":"boundary","value":' + value + '}]}')
        r = client.post('/api/public/surveys/' + survey['public_token'] + '/responses',
                        content=payload, headers={'Content-Type': 'application/json'})
        assert r.status_code == 422, r.text
        assert r.json()['detail']['valid'] is False
    with MongoClient(uri, tz_aware=True) as mongo:
        for n, rows in before.items():
            assert list(mongo[name][n].find({})) == rows
    print('SLICE2_REVIEW_SUPERSEDED_EXACT_NUMERIC_NONFINITE=PASS')
    fresh = check('POST', '/api/surveys', 201, {'title': 'Base workflow'}).json()
    survey.clear();survey.update(fresh)
