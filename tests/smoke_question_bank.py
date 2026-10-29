"""S1-12 extension for the existing isolated real Uvicorn smoke runner."""
def verify_question_bank(client):
    definition = {'type': 'number', 'title': '年龄', 'required': True,
                  'validation': {'min': 0}, 'options': []}
    response = client.post('/api/questions', json={'definition': definition},
                           headers={'Idempotency-Key': 'smoke-create'})
    assert response.status_code == 201, response.text
    initial = response.json()
    qid, vid = initial['family']['question_id'], initial['version']['question_version_id']
    response = client.post(f'/api/questions/{qid}/versions', json={
        'definition': {**definition, 'title': '年龄（岁）'}, 'parent_version_id': vid,
        'expected_revision': 1}, headers={'Idempotency-Key': 'smoke-v2'})
    assert response.status_code == 201, response.text
    restored = client.post(f'/api/questions/{qid}/restore', json={
        'source_version_id': vid, 'expected_revision': 2},
        headers={'Idempotency-Key': 'smoke-restore'})
    assert restored.status_code == 201, restored.text
    assert restored.json()['version']['restored_from'] == vid
    assert client.get('/api/question-versions/' + vid).json() == initial['version']
    assert [v['version_no'] for v in client.get(f'/api/questions/{qid}/versions').json()['items']] == [3, 2, 1]
    print('QUESTION_BANK_UVICORN_SMOKE=PASS')
