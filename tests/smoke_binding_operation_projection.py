"""Real HTTP projection check; fault setup writes only the isolated smoke DB."""
from copy import deepcopy

from bson import ObjectId
from pymongo import MongoClient

from smoke_slice2_review_fix import verify_review_fix


def verify_projection(client, check, survey, uri, name):
    assert name.startswith('survey_test_smoke_')
    verify_review_fix(client, check, survey, uri, name)
    path = '/api/surveys/' + survey['id']
    a = client.post(path + '/questions', json={'id': 'q', 'type': 'text', 'title': 'A'},
                    headers={'Idempotency-Key': 'projection-A'})
    assert a.status_code == 201, a.text
    b = client.put(path + '/questions/q', json={'type': 'text', 'title': 'B'},
                   headers={'Idempotency-Key': 'projection-B'})
    assert b.status_code == 200, b.text
    check('POST', path + '/publish', 200)
    check('POST', '/api/public/surveys/' + survey['public_token'] + '/responses', 201, {
        'schema_version': b.json()['schema_version'], 'answers': [{'question_id': 'q', 'value': 'answer'}]})
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name]
        op = db.draft_operations.find_one({'survey_id': ObjectId(survey['id']), 'key': 'explicit:projection-A'})
        assert op['_id'] in db.surveys.find_one({'_id': ObjectId(survey['id'])})['_binding_commits']
        assert op['state'] == 'COMMITTED'
        operation_path = path + '/binding-operations/' + str(op['_id'])
        for lagging in [False, True]:
            if lagging:
                db.draft_operations.update_one({'_id': op['_id']}, {'$set': {'state': 'PREPARED'}})
            before = {n: deepcopy(list(db[n].find({}))) for n in (
                'surveys', 'survey_versions', 'responses', 'questions', 'question_versions',
                'draft_operations', 'stage2_operations')}
            status = check('GET', operation_path, 200).json()
            assert status == {'operation_id': str(op['_id']), 'state': 'COMMITTED',
                'result_schema_version': a.json()['schema_version'],
                'current_schema_version': b.json()['schema_version'], 'superseded': True}
            for n, rows in before.items():
                assert list(db[n].find({})) == rows
            assert check('POST', operation_path + '/resume', 409).json()['detail']['code'] == 'operation_superseded'
            for n, rows in before.items():
                assert list(db[n].find({})) == rows
    print('SLICE2_LOGICAL_COMMITTED_PROJECTION_READ_ONLY=PASS')
    fresh = check('POST', '/api/surveys', 201, {'title': 'Base workflow'}).json()
    survey.clear();survey.update(fresh)
