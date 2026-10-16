from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.core.security import utcnow
from app.services import questions


def create(client):
    response = client.post('/api/surveys', json={'title':'题目测试'})
    assert response.status_code == 201
    return response.json()


def definition(kind='text', **fields):
    return {'type':kind, 'title':'题目', **fields}


def add(client, survey_id, data=None):
    return client.post(f'/api/surveys/{survey_id}/questions', json=data or definition())


@pytest.mark.parametrize('kind,rules', [
    ('single_choice',{}), ('multiple_choice',{'exact_selections':1}),
    ('text',{'min_length':1,'max_length':20}), ('number',{'min':0,'max':120,'integer_only':True}),
])
def test_create_each_type(logged, db, kind, rules):
    survey=create(logged)
    assert survey['schema_version']==1
    data=definition(kind, validation=rules)
    if 'choice' in kind:
        data['options']=[{'id':'a','label':'A'},{'id':'b','label':'B'}]
    response=add(logged,survey['id'],data)
    assert response.status_code==201, response.text
    body=response.json()
    q=body['questions'][0]
    assert q['type']==kind and q['order']==1 and q['id']
    assert body['schema_version']==2
    assert body['updated_at'].endswith('Z')
    stored=db.surveys.find_one({'_id':ObjectId(survey['id'])})
    assert stored['questions'][0]==q
    assert 'questions' not in db.list_collection_names()
    assert logged.get('/api/surveys/'+survey['id']).json()['questions']==[q]


@pytest.mark.parametrize('data',[
    definition('single_choice'),
    definition('multiple_choice', options=[{'id':'x','label':'A'},{'id':'x','label':'B'}]),
    definition('text', validation={'min_length':3,'max_length':2}),
    definition('number', validation={'min':4,'max':2}),
    definition('number', schema_version=99),
    definition('text', required=1),
    definition('text', order=True),
    definition('number', validation={'min':True}),
    definition('text', id='bad.id'),
    definition('text', validation={'integer_only':True}),
])
def test_invalid_create_is_atomic(logged, data):
    survey=create(logged)
    response=add(logged,survey['id'],data)
    assert response.status_code==422
    body=logged.get('/api/surveys/'+survey['id']).json()
    assert body['questions']==[] and body['schema_version']==1


def test_question_lifecycle_and_metadata_version(logged):
    survey=create(logged)
    path='/api/surveys/'+survey['id']
    response=add(logged,survey['id'],definition(id='stable'))
    assert response.json()['schema_version']==2
    assert response.json()['questions'][0]['id']=='stable'
    metadata=logged.put(path,json={'title':'新标题','description':'changed', 'allow_anonymous':True,
                                  'allow_multiple_submissions':True,'deadline':'2030-01-01T08:00:00+08:00'})
    assert metadata.status_code==200 and metadata.json()['schema_version']==2
    changed=logged.put(path+'/questions/stable',json=definition('number',title='年龄',validation={'min':0,'integer_only':True}))
    assert changed.status_code==200 and changed.json()['schema_version']==3
    assert changed.json()['title']=='新标题' and changed.json()['allow_anonymous'] is True
    assert changed.json()['questions'][0]['id']=='stable'
    assert changed.json()['questions'][0]['type']=='number'
    same=logged.put(path+'/questions/stable',json=definition('number',title='年龄',validation={'min':0,'integer_only':True}))
    assert same.json()['schema_version']==3
    deleted=logged.delete(path+'/questions/stable')
    assert deleted.status_code==200 and deleted.json()['schema_version']==4
    assert deleted.json()['questions']==[]


def test_order_and_stable_ids(logged):
    survey=create(logged)
    sid=survey['id']
    add(logged,sid,definition(id='a'))
    add(logged,sid,definition(id='b'))
    inserted=add(logged,sid,definition(id='c',order=1)).json()
    assert [q['id'] for q in inserted['questions']]==['c','a','b']
    moved=logged.put(f'/api/surveys/{sid}/questions/b',json=definition(order=1)).json()
    assert [q['id'] for q in moved['questions']]==['b','c','a']
    deleted=logged.delete(f'/api/surveys/{sid}/questions/c').json()
    assert [q['id'] for q in deleted['questions']]==['b','a']
    assert [q['order'] for q in deleted['questions']]==[1,2]
    assert deleted['schema_version']==6


def test_id_conflicts_and_invalid_order(logged):
    survey=create(logged)
    sid=survey['id']
    add(logged,sid,definition(id='a'))
    assert add(logged,sid,definition(id='a')).status_code==409
    assert add(logged,sid,definition(order=3)).status_code==422
    assert logged.put(f'/api/surveys/{sid}/questions/a',json=definition(id='other')).status_code==422
    assert logged.put(f'/api/surveys/{sid}/questions/a',json=definition(order=2)).status_code==422
    assert logged.get('/api/surveys/'+sid).json()['schema_version']==2


@pytest.mark.parametrize('method,suffix', [('POST',''),('PUT','/missing'),('DELETE','/missing')])
def test_auth_required(client,method,suffix):
    response=client.request(method,'/api/surveys/'+str(ObjectId())+'/questions'+suffix,json=definition() if method!='DELETE' else None)
    assert response.status_code==401


@pytest.mark.parametrize('method,suffix', [('POST',''),('PUT','/q1'),('DELETE','/q1')])
def test_other_owner_and_invalid_ids(logged,method,suffix):
    survey=create(logged)
    add(logged,survey['id'],definition(id='q1'))
    logged.post('/api/auth/register',json={'username':'bob','password':'password123'})
    logged.post('/api/auth/login',json={'username':'bob','password':'password123'})
    data=definition() if method!='DELETE' else None
    response=logged.request(method,f"/api/surveys/{survey['id']}/questions{suffix}",json=data)
    assert response.status_code==404
    assert logged.request(method,'/api/surveys/bad-id/questions'+suffix,json=data).status_code==422
    assert logged.request(method,f'/api/surveys/{ObjectId()}/questions'+suffix,json=data).status_code==404


def test_missing_question(logged):
    survey=create(logged)
    path=f"/api/surveys/{survey['id']}/questions/missing"
    assert logged.put(path,json=definition()).status_code==404
    assert logged.delete(path).status_code==404
    assert logged.get('/api/surveys/'+survey['id']).json()['schema_version']==1


def test_published_edit_closed_readonly(logged):
    sid=create(logged)['id']
    path='/api/surveys/'+sid
    assert logged.post(path+'/publish').status_code==200
    added=add(logged,sid,definition(id='q1'))
    assert added.status_code==201 and added.json()['status']=='published'
    assert added.json()['schema_version']==2
    updated=logged.put(path+'/questions/q1',json=definition(title='已发布可改'))
    assert updated.json()['schema_version']==3
    logged.post(path+'/close')
    assert add(logged,sid).status_code==409
    assert logged.put(path+'/questions/q1',json=definition()).status_code==409
    assert logged.delete(path+'/questions/q1').status_code==409
    existing=logged.get(path).json()
    assert existing['questions'][0]['title']=='已发布可改' and existing['schema_version']==3
    assert logged.post(path+'/publish').status_code==409


def test_delete_survey_protects_responses(logged,db):
    sid=create(logged)['id']
    document={'survey_id':ObjectId(sid),'respondent_user_id':None,'answers':[],
              'submitted_at':utcnow(),'survey_schema_version':1}
    response_id=db.responses.insert_one(document).inserted_id
    response=logged.delete('/api/surveys/'+sid)
    assert response.status_code==409 and '关闭' in response.json()['detail']
    assert logged.get('/api/surveys/'+sid).status_code==200
    assert db.responses.find_one({'_id':response_id}) is not None
    empty=create(logged)['id']
    assert logged.delete('/api/surveys/'+empty).status_code==204
    assert db.responses.find_one({'_id':response_id}) is not None


def test_response_does_not_leak_survey_existence(logged,db):
    sid=create(logged)['id']
    db.responses.insert_one({'survey_id':ObjectId(sid)})
    logged.post('/api/auth/register',json={'username':'bob','password':'password123'})
    logged.post('/api/auth/login',json={'username':'bob','password':'password123'})
    assert logged.delete('/api/surveys/'+sid).status_code==404


def test_concurrent_question_edits_use_cas(logged,db,monkeypatch):
    sid=create(logged)['id']
    user=db.users.find_one({'username':'alice'})
    barrier=Barrier(4)
    original=questions.get_owned
    def snapshot(*args):
        survey=original(*args)
        barrier.wait(timeout=10)
        return survey
    monkeypatch.setattr(questions,'get_owned',snapshot)
    def worker(index):
        try:
            return questions.add_question(db,sid,user,definition(id=f'q{index}'))['schema_version']
        except HTTPException as exc:
            assert exc.status_code==409
            return 'conflict'
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(worker,range(4)))
    assert results.count(2)==1 and results.count('conflict')==3
    stored=db.surveys.find_one({'_id':ObjectId(sid)})
    assert stored['schema_version']==2 and len(stored['questions'])==1


def test_commit_preserves_unrelated_fields_and_checks_status(logged,db):
    sid=create(logged)['id']
    user=db.users.find_one({'username':'alice'})
    snapshot=questions.get_owned(db,sid,user)
    db.surveys.update_one({'_id':snapshot['_id']},{'$set':{'description':'concurrent metadata','jump_rules':[{'future':True}]}})
    updated=questions.commit_structure(db,snapshot,user,{'questions':[]})
    assert updated['description']=='concurrent metadata' and updated['jump_rules']==[{'future':True}]
    assert updated['schema_version']==2
    stale=dict(updated)
    db.surveys.update_one({'_id':snapshot['_id']},{'$set':{'status':'closed'}})
    with pytest.raises(HTTPException) as exc:
        questions.commit_structure(db,stale,user,{'questions':[]})
    assert exc.value.status_code==409
    assert db.surveys.find_one({'_id':snapshot['_id']})['schema_version']==2


@pytest.mark.parametrize('nonfinite', ['NaN','Infinity','-Infinity'])
def test_nonfinite_json_definition_returns_safe_error(logged, nonfinite):
    sid=create(logged)['id']
    raw='{"type":"number","title":"范围","validation":{"min":'+nonfinite+'}}'
    response=logged.post(f'/api/surveys/{sid}/questions',content=raw.encode('utf-8'),headers={'Content-Type':'application/json'})
    assert response.status_code==422
    assert response.json()['detail']['errors'][0]['code']=='invalid_rule_value'
    assert logged.get('/api/surveys/'+sid).json()['schema_version']==1


def test_edit_options_validation_required_each_bumps_once(logged):
    sid=create(logged)['id']
    data=definition('single_choice',id='stable',options=[{'id':'a','label':'A'},{'id':'b','label':'B'}])
    assert add(logged,sid,data).json()['schema_version']==2
    path=f'/api/surveys/{sid}/questions/stable'
    data['options'][1]['label']='更新 B'
    assert logged.put(path,json=data).json()['schema_version']==3
    data['type']='multiple_choice'
    data['validation']={'min_selections':1,'max_selections':2}
    assert logged.put(path,json=data).json()['schema_version']==4
    data['validation']={'exact_selections':1}
    data['required']=True
    changed=logged.put(path,json=data)
    assert changed.json()['schema_version']==5
    assert changed.json()['questions'][0]['id']=='stable'
    data['validation']={'min_selections':2,'max_selections':1}
    assert logged.put(path,json=data).status_code==422
    assert logged.get('/api/surveys/'+sid).json()['schema_version']==5


def test_published_delete_question_bumps_version(logged):
    sid=create(logged)['id']
    add(logged,sid,definition(id='q1'))
    logged.post(f'/api/surveys/{sid}/publish')
    result=logged.delete(f'/api/surveys/{sid}/questions/q1')
    assert result.status_code==200
    assert result.json()['schema_version']==3 and result.json()['status']=='published'


def test_structure_change_ignores_simultaneous_metadata_edit(logged,db,monkeypatch):
    sid=create(logged)['id']
    original=questions.commit_structure
    def concurrent_metadata(db_,survey,user,changes):
        db_.surveys.update_one({'_id':survey['_id']},{'$set':{'title':'concurrent title','description':'kept'}})
        return original(db_,survey,user,changes)
    monkeypatch.setattr(questions,'commit_structure',concurrent_metadata)
    result=add(logged,sid)
    assert result.status_code==201
    assert result.json()['title']=='concurrent title' and result.json()['description']=='kept'
    assert result.json()['schema_version']==2
