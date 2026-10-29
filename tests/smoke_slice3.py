from copy import deepcopy
from pathlib import Path
import os

from bson import ObjectId
from pymongo import MongoClient

from smoke_binding_operation_projection import verify_projection


def verify_slice3(client, check, survey, uri, name):
    assert name.startswith('survey_test_smoke_')
    verify_projection(client, check, survey, uri, name)
    path = '/api/surveys/' + survey['id']
    a = client.post(path + '/questions', json={'id': 'q', 'type': 'number', 'title': 'Age', 'required': True},
                    headers={'Idempotency-Key': 'slice3-source'})
    assert a.status_code == 201
    current = a.json();check('POST', path + '/publish', 200)
    check('POST', '/api/public/surveys/' + survey['public_token'] + '/responses', 201,
          {'schema_version': current['schema_version'], 'answers': [{'question_id': 'q', 'value': 20}]})
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name];sid = ObjectId(survey['id'])
        before = {'survey': deepcopy(db.surveys.find_one({'_id': sid})),
                  'snapshots': deepcopy(list(db.survey_versions.find({'survey_id': sid}))),
                  'responses': deepcopy(list(db.responses.find({'survey_id': sid})))}
    body = {'source_schema_version': current['schema_version'], 'expected_schema_version': current['schema_version']}
    r = client.post(path + '/revisions', json=body, headers={'Idempotency-Key': 'slice3-revision'})
    assert r.status_code == 201, r.text
    child = r.json();assert child['id'] != survey['id'] and child['public_token'] != survey['public_token']
    assert client.post(path + '/revisions', json=body, headers={'Idempotency-Key': 'slice3-revision'}).json() == child
    assert child['revision_of'] == survey['id'] and child['status'] == 'draft'
    check('PUT', '/api/surveys/' + child['id'] + '/questions/q', 200, {'type': 'number', 'title': 'New age', 'required': False})
    check('POST', '/api/surveys/' + child['id'] + '/publish', 200)
    check('PUT', '/api/surveys/' + child['id'] + '/questions/q', 409, {'type': 'number', 'title': 'blocked'})
    evidence = Path(__file__).resolve().parents[1] / ('docs/stage2/slice3/pages-' + os.environ.get('SLICE3_EVIDENCE_MODE', 'smoke'))
    evidence.mkdir(exist_ok=False)
    for label, route in [('bank', '/question-bank'), ('family', '/question-bank/' + current['question_bindings'][0]['question_id']),
                         ('source', '/surveys/' + survey['id'] + '/edit'), ('revision', '/surveys/' + child['id'] + '/edit'),
                         ('dashboard', '/dashboard')]:
        page = check('GET', route, 200)
        # Generated test public tokens are omitted from persisted page evidence.
        import re
        content = re.sub(r'(/survey/)[A-Za-z0-9_-]+', r'\1[PUBLIC_TOKEN_REDACTED]', page.text)
        for token in [survey['public_token'], child['public_token']]:content = content.replace(token, '[PUBLIC_TOKEN_REDACTED]')
        with (evidence / (label + '.html')).open('x', encoding='utf8') as output:output.write(content)
    with MongoClient(uri, tz_aware=True) as mongo:
        db = mongo[name]
        assert db.surveys.find_one({'_id': sid}) == before['survey']
        assert list(db.survey_versions.find({'survey_id': sid})) == before['snapshots']
        assert list(db.responses.find({'survey_id': sid})) == before['responses']
    print('SLICE3_BANK_PAGES_REVISION_EDIT_PUBLISH_SOURCE_PROTECTED=PASS')
    fresh = check('POST', '/api/surveys', 201, {'title': 'Base workflow'}).json()
    survey.clear();survey.update(fresh)
