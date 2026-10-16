from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, OperationFailure
import pytest

from app.core.security import utcnow
from app.services import questions, responses, versions


def setup_survey(client, *, publish=True, anonymous=True, multiple=True, deadline=None):
    survey=client.post('/api/surveys',json={'title':'公开问卷','allow_anonymous':anonymous,
        'allow_multiple_submissions':multiple,'deadline':deadline}).json()
    sid=survey['id']
    for q in [{'id':'q1','type':'single_choice','title':'选择','required':True,'options':[{'id':'a','label':'跳转'},{'id':'b','label':'顺序'}]},
              {'id':'q2','type':'text','title':'跳过的必答','required':True},
              {'id':'q3','type':'number','title':'年龄','required':True,'validation':{'min':0,'max':120,'integer_only':True}},
              {'id':'q4','type':'multiple_choice','title':'选答','options':[{'id':'x','label':'X'},{'id':'y','label':'Y'}]}]:
        result=client.post(f'/api/surveys/{sid}/questions',json=q)
        assert result.status_code==201,result.text
        survey=result.json()
    r=client.post(f'/api/surveys/{sid}/jump-rules',json={'id':'r1','source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3','priority':1})
    assert r.status_code==201,r.text
    survey=r.json()
    if publish:
        p=client.post(f'/api/surveys/{sid}/publish');assert p.status_code==200,p.text;survey=p.json()
    return survey


def payload(survey, **answers):
    values={'q1':'a','q3':20,**answers}
    return {'schema_version':survey['schema_version'],'answers':[{'question_id':k,'value':v} for k,v in values.items()]}


def url(survey):
    return '/api/public/surveys/'+survey['public_token']


def test_publish_snapshot_immutable_unique_and_owner_history(logged,db):
    survey=setup_survey(logged,publish=False);sid=survey['id'];oid=ObjectId(sid)
    assert db.survey_versions.count_documents({})==0
    assert logged.post(f'/api/surveys/{sid}/publish').status_code==200
    old=versions.get_survey_version(db,sid,survey['schema_version'])
    assert old['questions']==survey['questions'] and old['jump_rules']==survey['jump_rules']
    assert old['created_reason']=='publish' and old['created_at'].tzinfo is not None
    with pytest.raises(DuplicateKeyError):
        db.survey_versions.insert_one({**old,'_id':ObjectId()})
    changed=logged.put(f'/api/surveys/{sid}/questions/q2',json={'type':'text','title':'新标题'}).json()
    assert changed['schema_version']==survey['schema_version']+1
    assert db.survey_versions.find_one({'_id':old['_id']})==old
    new=versions.get_survey_version(db,sid,changed['schema_version'])
    assert new['created_reason']=='question_change'
    result=logged.get(f"/api/surveys/{sid}/versions/{survey['schema_version']}")
    assert result.status_code==200 and result.json()['questions']==old['questions']
    assert logged.put(f"/api/surveys/{sid}/versions/{survey['schema_version']}",json={}).status_code==405
    with pytest.raises(HTTPException) as exc:
        versions.get_survey_version(db,sid,9999)
    assert exc.value.status_code==404


def test_jump_crud_snapshot_and_reference_integrity(logged,db):
    s=setup_survey(logged);path='/api/surveys/'+s['id'];v=s['schema_version']
    before=db.survey_versions.count_documents({})
    assert logged.delete(path+'/questions/q1').status_code==409
    assert logged.delete(path+'/questions/q3').status_code==409
    assert logged.put(path+'/questions/q1',json={'type':'text','title':'非法改型'}).status_code==409
    assert logged.put(path+'/questions/q1',json={'type':'single_choice','title':'改选项','options':[{'id':'z','label':'Z'},{'id':'b','label':'B'}]}).status_code==409
    assert logged.put(path+'/questions/q3',json={'type':'number','title':'倒序','order':1}).status_code==409
    assert db.survey_versions.count_documents({})==before
    assert logged.get(path).json()['schema_version']==v
    assert logged.put(path+'/jump-rules/r1',json={'source_question_id':'q1','operator':'equals','value':'b','target_question_id':'q3','priority':1}).status_code==200
    latest=logged.get(path).json();assert latest['schema_version']==v+1
    assert versions.get_survey_version(db,s['id'],v+1)['created_reason']=='jump_rule_change'
    assert logged.delete(path+'/jump-rules/r1').status_code==200
    assert logged.delete(path+'/questions/q1').status_code==200
    assert logged.delete(path+'/jump-rules/missing').status_code==404


@pytest.mark.parametrize('method,suffix',[('POST',''),('PUT','/r1'),('DELETE','/r1')])
def test_jump_owner_auth_status_ids(logged,method,suffix):
    s=setup_survey(logged)
    path=f"/api/surveys/{s['id']}/jump-rules{suffix}"
    data={'source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3','priority':2}
    assert logged.request(method,'/api/surveys/not-an-id/jump-rules'+suffix,json=data).status_code==422
    logged.post('/api/surveys/'+s['id']+'/close')
    assert logged.request(method,path,json=data).status_code==409
    logged.post('/api/auth/register',json={'username':'bob','password':'password123'})
    logged.post('/api/auth/login',json={'username':'bob','password':'password123'})
    assert logged.request(method,path,json=data).status_code==404
    logged.post('/api/auth/logout')
    assert logged.request(method,path,json=data).status_code==401


def test_rule_id_and_priority_validation(logged):
    s=setup_survey(logged,publish=False);path=f"/api/surveys/{s['id']}/jump-rules"
    data={'source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3','priority':1}
    assert logged.post(path,json=data).status_code==422
    data['priority']=2;data['id']='r1'
    assert logged.post(path,json=data).status_code==422
    data['id']='bad.id'
    response=logged.post(path,json=data);assert response.status_code==201
    assert response.json()['jump_rules'][-1]['id']!='bad.id'


@pytest.mark.parametrize('state,code',[('published',200),('draft',409),('closed',409),('missing',404),('expired',410)])
def test_public_status_deadline_page_and_privacy(logged,state,code):
    s=setup_survey(logged,publish=state!='draft')
    if state=='closed':logged.post('/api/surveys/'+s['id']+'/close')
    if state=='expired':logged.put('/api/surveys/'+s['id'],json={'title':'过期','allow_anonymous':True,'deadline':(utcnow()-timedelta(seconds=1)).isoformat()})
    logged.post('/api/auth/logout')
    path=url(s) if state!='missing' else '/api/public/surveys/missing'
    result=logged.get(path);assert result.status_code==code,result.text
    page=logged.get('/survey/'+(s['public_token'] if state!='missing' else 'missing'))
    assert page.status_code==code
    if code==200:
        body=result.json();assert body['schema_version']==s['schema_version']
        assert set(body)=={'id','title','description','schema_version','questions','jump_rules','allow_anonymous','allow_multiple_submissions','deadline'}
        assert 'owner_id' not in result.text and '_pending_schema' not in result.text and 'password' not in result.text
        assert 'survey.js' in page.text


@pytest.mark.parametrize('anonymous,logged_in,expected',[(False,False,401),(False,True,201),(True,False,201),(True,True,201)])
def test_anonymous_policy(logged,db,anonymous,logged_in,expected):
    s=setup_survey(logged,anonymous=anonymous)
    if not logged_in:logged.post('/api/auth/logout')
    assert logged.get(url(s)).status_code==(200 if expected==201 else 401)
    result=logged.post(url(s)+'/responses',json=payload(s));assert result.status_code==expected,result.text
    if expected==201:
        stored=db.responses.find_one({'_id':ObjectId(result.json()['id'])})
        assert (stored['respondent_user_id'] is not None)==logged_in
        assert stored['survey_schema_version']==s['schema_version']
        assert stored['visited_question_ids']==['q1','q3','q4']
        assert stored['submitted_at'].tzinfo is not None


@pytest.mark.parametrize('extra,expected',[
 ({},201),({'q2':'skipped'},422),({'q3':None},422),({'q3':121},422),({'q3':True},422),
 ({'q1':'missing'},422),({'q4':['x','x']},422),({'q4':['x']},201),({'unknown':1},422),
 ({'q1':'b','q2':'顺序必答'},201),({'q1':'b'},422),({'q1':'b','q2':5},422)])
def test_response_path_validation(logged,db,extra,expected):
    s=setup_survey(logged)
    result=logged.post(url(s)+'/responses',json=payload(s,**extra))
    assert result.status_code==expected,result.text
    assert db.responses.count_documents({})==(1 if expected==201 else 0)


def test_next_api_and_historical_submission(logged,db):
    s=setup_survey(logged);path=url(s)
    result=logged.post(path+'/next',json={'schema_version':s['schema_version'],'current_question_id':'q1','answer':'a'})
    assert result.json()=={'next_question_id':'q3','completed':False}
    assert logged.post(path+'/next',json={'schema_version':s['schema_version'],'current_question_id':'q3','answer':-1}).status_code==422
    old=deepcopy(versions.get_survey_version(db,s['id'],s['schema_version']))
    update=logged.put(f"/api/surveys/{s['id']}/questions/q3",json={'type':'number','title':'新范围','required':True,'validation':{'min':50}})
    assert update.status_code==200
    assert logged.post(path+'/responses',json=payload(s)).status_code==201
    current={**s,'schema_version':update.json()['schema_version']}
    assert logged.post(path+'/responses',json=payload(current)).status_code==422
    assert logged.post(path+'/responses',json={**payload(s),'schema_version':9999}).status_code==404
    assert versions.get_survey_version(db,s['id'],s['schema_version'])==old


@pytest.mark.parametrize('multiple,anonymous,expected',[(False,False,409),(True,False,201),(False,True,201)])
def test_duplicate_submission(logged,db,multiple,anonymous,expected):
    s=setup_survey(logged,multiple=multiple)
    if anonymous:logged.post('/api/auth/logout')
    assert logged.post(url(s)+'/responses',json=payload(s)).status_code==201
    assert logged.post(url(s)+'/responses',json=payload(s)).status_code==expected
    first=db.responses.find_one()
    assert ('dedupe_key' in first)==(not multiple and not anonymous)


def test_concurrent_dedupe_unique_index(logged,db,monkeypatch):
    s=setup_survey(logged,multiple=False);user=db.users.find_one({'username':'alice'})
    original=type(db.responses).insert_one;barrier=Barrier(2)
    def insert(collection,*args,**kwargs):
        if collection.name=='responses':barrier.wait(timeout=10)
        return original(collection,*args,**kwargs)
    monkeypatch.setattr(type(db.responses),'insert_one',insert)
    def worker(_):
        try:responses.submit_response(db,s['public_token'],user,payload(s));return 201
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,range(2)))
    assert sorted(results)==[201,409]
    assert db.responses.count_documents({})==1


@pytest.mark.parametrize('deadline', ['none','future','past'])
def test_submit_deadline(logged,deadline):
    value=None if deadline=='none' else (utcnow()+timedelta(hours=1 if deadline=='future' else -1)).isoformat()
    s=setup_survey(logged,deadline=value)
    assert logged.post(url(s)+'/responses',json=payload(s)).status_code==(410 if deadline=='past' else 201)


@pytest.mark.parametrize('change',['closed','expired'])
def test_final_gate_rechecks_after_validation(logged,db,monkeypatch,change):
    s=setup_survey(logged);original=responses.validate_response_path
    def changed(*args,**kwargs):
        values={'status':'closed'} if change=='closed' else {'deadline':utcnow()-timedelta(seconds=1)}
        db.surveys.update_one({'_id':ObjectId(s['id'])},{'$set':values})
        return original(*args,**kwargs)
    monkeypatch.setattr(responses,'validate_response_path',changed)
    assert logged.post(url(s)+'/responses',json=payload(s)).status_code==(409 if change=='closed' else 410)
    assert db.responses.count_documents({})==0


@pytest.mark.parametrize('state,expected',[('draft',204),('published',409),('closed',409)])
def test_delete_state_policy(logged,state,expected):
    s=setup_survey(logged,publish=state!='draft')
    if state=='closed':logged.post('/api/surveys/'+s['id']+'/close')
    assert logged.delete('/api/surveys/'+s['id']).status_code==expected


@pytest.mark.parametrize('failure_stage',['snapshot','pointer'])
def test_snapshot_failure_keeps_current_and_recovers(logged,db,monkeypatch,failure_stage):
    s=setup_survey(logged);sid=ObjectId(s['id']);before=db.surveys.find_one({'_id':sid})
    collection_type=type(db.surveys)
    method='insert_one' if failure_stage=='snapshot' else 'find_one_and_update'
    original=getattr(collection_type,method)
    failed=False
    def injected(collection,*args,**kwargs):
        nonlocal failed
        target=collection.name=='survey_versions' if failure_stage=='snapshot' else collection.name=='surveys' and '_pending_schema.id' in args[0]
        if target and not failed:
            failed=True
            raise OperationFailure('INJECTED_'+failure_stage.upper()+'_WRITE_FAILURE')
        return original(collection,*args,**kwargs)
    monkeypatch.setattr(collection_type,method,injected)
    response=logged.put(f"/api/surveys/{s['id']}/questions/q2",json={'type':'text','title':'待恢复'})
    assert response.status_code==503
    current=db.surveys.find_one({'_id':sid})
    assert current['schema_version']==before['schema_version'] and current['questions']==before['questions']
    assert '_pending_schema' in current
    assert versions.get_survey_version(db,sid,s['schema_version'])['questions']==before['questions']
    recovered=db.surveys.find_one({'_id':sid})
    assert recovered['schema_version']==s['schema_version']+1 and '_pending_schema' not in recovered
    assert versions.get_survey_version(db,sid,recovered['schema_version'])['questions']==recovered['questions']


def test_publish_snapshot_failure_does_not_publish(logged,db,monkeypatch):
    s=setup_survey(logged,publish=False);original=type(db.survey_versions).insert_one
    def fail(collection,*args,**kwargs):
        if collection.name=='survey_versions':raise OperationFailure('INJECTED_PUBLISH_SNAPSHOT_FAILURE')
        return original(collection,*args,**kwargs)
    monkeypatch.setattr(type(db.survey_versions),'insert_one',fail)
    assert logged.post('/api/surveys/'+s['id']+'/publish').status_code==503
    current=db.surveys.find_one({'_id':ObjectId(s['id'])})
    assert current['status']=='draft' and current['schema_version']==s['schema_version']
    assert db.survey_versions.count_documents({})==0


def test_concurrent_published_edit_snapshots(logged,db,monkeypatch):
    s=setup_survey(logged);user=db.users.find_one({'username':'alice'});barrier=Barrier(4);original=questions.get_owned
    def synced(*args):
        found=original(*args);barrier.wait(timeout=10);return found
    monkeypatch.setattr(questions,'get_owned',synced)
    def worker(i):
        try:questions.add_question(db,s['id'],user,{'type':'text','title':f'线程{i}'});return 200
        except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:out=list(pool.map(worker,range(4)))
    assert sorted(out)==[200,409,409,409]
    current=db.surveys.find_one({'_id':ObjectId(s['id'])})
    assert current['schema_version']==s['schema_version']+1
    assert versions.get_survey_version(db,current['_id'],current['schema_version'])['questions']==current['questions']
    assert db.survey_versions.count_documents({})==2


def test_rule_default_priority_is_saved(logged):
    s=setup_survey(logged,publish=False)
    path=f"/api/surveys/{s['id']}/jump-rules"
    logged.delete(path+'/r1')
    result=logged.post(path,json={'source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3'})
    assert result.status_code==201
    assert result.json()['jump_rules'][0]['priority']==1
    assert logged.post('/api/surveys/'+s['id']+'/publish').status_code==200
    assert logged.post(url(s)+'/next',json={'schema_version':result.json()['schema_version'],'current_question_id':'q1','answer':'a'}).json()['next_question_id']=='q3'


@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity'])
def test_nonfinite_rule_json_and_response_json(logged,value):
    s=setup_survey(logged)
    raw='{"source_question_id":"q3","operator":"equals","value":'+value+',"target_question_id":"q4","priority":1}'
    result=logged.post(f"/api/surveys/{s['id']}/jump-rules",content=raw,headers={'Content-Type':'application/json'})
    assert result.status_code==422
    raw='{"schema_version":'+str(s['schema_version'])+',"answers":[{"question_id":"q1","value":"a"},{"question_id":"q3","value":'+value+'}]}'
    assert logged.post(url(s)+'/responses',content=raw,headers={'Content-Type':'application/json'}).status_code==422


def test_duplicate_answer_and_cross_survey_version(logged):
    s=setup_survey(logged)
    data=payload(s);data['answers'].append(data['answers'][0])
    assert logged.post(url(s)+'/responses',json=data).status_code==422
    other=setup_survey(logged)
    add=logged.post('/api/surveys/'+other['id']+'/questions',json={'type':'text','title':'另一问卷'})
    unknown={**payload(s),'schema_version':add.json()['schema_version']}
    assert logged.post(url(s)+'/responses',json=unknown).status_code==404


@pytest.mark.parametrize('delta_us,expected',[(-1,201),(0,201),(1,410)])
def test_deadline_millisecond_boundary(logged,db,monkeypatch,delta_us,expected):
    fixed=utcnow().replace(microsecond=0)+timedelta(hours=1)
    s=setup_survey(logged,deadline=fixed.isoformat())
    monkeypatch.setattr(responses,'utcnow',lambda:fixed+timedelta(microseconds=delta_us))
    assert logged.post(url(s)+'/responses',json=payload(s)).status_code==expected


def test_metadata_change_does_not_snapshot(logged,db):
    s=setup_survey(logged)
    before=list(db.survey_versions.find())
    result=logged.put('/api/surveys/'+s['id'],json={'title':'改元信息','allow_anonymous':True,'allow_multiple_submissions':True})
    assert result.json()['schema_version']==s['schema_version']
    assert list(db.survey_versions.find())==before


def test_get_version_returns_detached_document(logged,db):
    s=setup_survey(logged)
    snap=versions.get_survey_version(db,s['id'],s['schema_version']);saved=deepcopy(snap)
    snap['questions'][0]['title']='客户端对象修改'
    assert versions.get_survey_version(db,s['id'],s['schema_version'])==saved


def test_recovery_cannot_rebase_stale_question_array(logged,db,monkeypatch):
    s=setup_survey(logged);user=db.users.find_one({'username':'alice'})
    stale=questions.get_owned(db,s['id'],user)
    real=versions.ensure_current_snapshot
    def helped(db_,survey):
        # Simulate another request finishing a previously reserved newer edit.
        db_.surveys.update_one({'_id':survey['_id']},{'$inc':{'schema_version':1},'$set':{'questions':[*survey['questions'],{'id':'new','type':'text','title':'保留并发题目','required':False,'order':5,'options':[],'validation':{}}]}})
        return db_.surveys.find_one({'_id':survey['_id']})
    monkeypatch.setattr(versions,'ensure_current_snapshot',helped)
    with pytest.raises(HTTPException) as exc:
        questions.commit_structure(db,stale,user,{'questions':[]})
    assert exc.value.status_code==409
    current=db.surveys.find_one({'_id':stale['_id']})
    assert current['questions'][-1]['id']=='new'


def test_external_shared_link_read_but_cross_site_write_blocked(logged):
    s=setup_survey(logged)
    logged.post('/api/auth/logout')
    headers={'Sec-Fetch-Site':'cross-site','Origin':'https://external.example'}
    assert logged.get('/survey/'+s['public_token'],headers=headers).status_code==200
    assert logged.get(url(s),headers=headers).status_code==200
    assert logged.post(url(s)+'/responses',json=payload(s),headers=headers).status_code==403
