from copy import deepcopy
import math
import pytest
from bson import ObjectId

from app.services.statistics import DataConsistencyError, compute_question_statistics
from test_public_responses import setup_survey, payload, url


def question(kind='number'):
    return {'id':'q','type':kind,'title':'题目','order':1,'required':False,'options':[{'id':'a','label':'历史 A'},{'id':'b','label':'历史 B'}] if 'choice' in kind else [],'validation':{}}


@pytest.mark.parametrize('kind,values,expected',[
 ('single_choice',['a','a','b',None,''],{'answered_count':3,'options':[{'option_id':'a','label':'历史 A','count':2},{'option_id':'b','label':'历史 B','count':1}]}),
 ('multiple_choice',[['a','b'],['a'],[],None],{'answered_count':2,'total_selections':3,'options':[{'option_id':'a','label':'历史 A','count':2},{'option_id':'b','label':'历史 B','count':1}]}),
 ('text',['你好','世界','',None],{'answered_count':2,'values':['你好','世界']}),
 ('number',[0,1,2.5,None],{'answered_count':3,'values':[0,1,2.5],'average':3.5/3,'min':0,'max':2.5}),
 ('number',[],{'answered_count':0,'values':[],'average':None,'min':None,'max':None}),
 ('number',[0.1,0.2],{'answered_count':2,'values':[0.1,0.2],'average':0.15,'min':0.1,'max':0.2}),
 ('number',[1e308,1e308],{'average':1e308}),
 ('number',[1e308,1e-100,-1e308],{'average':1e-100/3}),
])
def test_question_statistics(kind,values,expected):
    result=compute_question_statistics(question(kind),values)
    for key,value in expected.items():assert result[key]==value


@pytest.mark.parametrize('kind,bad',[('single_choice','unknown'),('multiple_choice',['a','a']),('multiple_choice',['unknown']),('text',5),('number',True),('number',float('nan')),('number',float('inf')),('number',2**63)])
def test_bad_values_fail_closed(kind,bad):
    with pytest.raises(DataConsistencyError):compute_question_statistics(question(kind),[bad])


def stats(client,s):
    result=client.get('/api/surveys/'+s['id']+'/stats')
    assert result.status_code==200,result.text
    return result.json()


def entry(version,qid):
    return next(item for item in version['questions'] if item['question']['id']==qid)


@pytest.mark.parametrize('published',[False,True])
def test_empty_statistics(logged,published):
    s=logged.post('/api/surveys',json={'title':'空问卷'}).json()
    if published:logged.post('/api/surveys/'+s['id']+'/publish')
    body=stats(logged,s)
    assert body['total_responses']==0
    assert body['versions']==([{'schema_version':1,'response_count':0,'questions':[]}] if published else [])


def test_multiple_responses_counts_and_skips(logged):
    s=setup_survey(logged)
    for values in [{'q4':['x','y']},{'q1':'b','q2':'有效文本','q3':40,'q4':['x']}]:
        response=logged.post(url(s)+'/responses',json=payload(s,**values));assert response.status_code==201
    body=stats(logged,s);assert body['total_responses']==2
    version=body['versions'][0];assert version['response_count']==2
    assert entry(version,'q1')['statistics']['options'][0]['count']==1
    assert entry(version,'q1')['statistics']['answered_count']==2
    assert entry(version,'q2')['statistics']=={'type':'text','answered_count':1,'values':['有效文本']}
    multi=entry(version,'q4')['statistics'];assert multi['answered_count']==2 and multi['total_selections']==3
    assert [o['count'] for o in multi['options']]==[2,1]
    assert entry(version,'q3')['statistics']['average']==30


def test_one_response_optional_missing_number_zero_answered(logged):
    s=setup_survey(logged)
    assert logged.post(url(s)+'/responses',json=payload(s,q3=0)).status_code==201
    body=stats(logged,s);assert body['total_responses']==1
    assert entry(body['versions'][0],'q4')['statistics']['answered_count']==0
    assert entry(body['versions'][0],'q3')['statistics']['average']==0
    assert entry(body['versions'][0],'q2')['statistics']['answered_count']==0


def test_historical_options_types_and_absent_question(logged,db):
    s=logged.post('/api/surveys',json={'title':'历史','allow_anonymous':True,'allow_multiple_submissions':True}).json();path='/api/surveys/'+s['id']
    base={'id':'stable','type':'single_choice','title':'历史题','options':[{'id':'a','label':'旧苹果'},{'id':'b','label':'旧香蕉'}]}
    old=logged.post(path+'/questions',json=base).json();logged.post(path+'/publish')
    def submit(version,value,extra=None):
        data={'schema_version':version,'answers':[{'question_id':'stable','value':value}]+(extra or [])}
        result=logged.post(url(s)+'/responses',json=data);assert result.status_code==201,result.text
    submit(old['schema_version'],'a')
    base['options']=[{'id':'a','label':'新苹果'},{'id':'b','label':'新香蕉'},{'id':'c','label':'新橙子'}]
    newer=logged.put(path+'/questions/stable',json=base).json();submit(newer['schema_version'],'c')
    numeric=logged.put(path+'/questions/stable',json={'type':'number','title':'现在是数字'}).json();submit(numeric['schema_version'],1.5)
    add=logged.post(path+'/questions',json={'id':'later','type':'text','title':'后加入'}).json();submit(add['schema_version'],2.5,[{'question_id':'later','value':'后来的答案'}])
    # Change only the current label/type again; existing snapshots must stay meaningful.
    logged.put(path+'/questions/stable',json={'type':'text','title':'当前文本'})
    body=stats(logged,s);assert body['total_responses']==4 and len(body['versions'])==5
    assert body['versions'][0]['questions'][0]['statistics']['options'][0]['label']=='旧苹果'
    assert body['versions'][1]['questions'][0]['statistics']['options'][2]['count']==1
    assert body['versions'][2]['questions'][0]['statistics']['average']==1.5
    result=logged.get(path+'/questions/stable/stats').json()
    assert [v['question']['type'] for v in result['versions']]==['single_choice','single_choice','number','number','text']
    later=logged.get(path+'/questions/later/stats').json()
    assert len(later['versions'])==2
    assert all(v['schema_version']>=add['schema_version'] for v in later['versions'])
    assert logged.get(path+'/questions/missing/stats').status_code==404
    assert db.responses.count_documents({'survey_id':ObjectId(s['id'])})==4


@pytest.mark.parametrize('suffix',['/stats','/questions/q1/stats'])
def test_statistics_permissions_and_bad_ids(logged,suffix):
    s=setup_survey(logged)
    assert logged.get('/api/surveys/'+s['id']+suffix).status_code==200
    assert logged.get('/api/surveys/invalid'+suffix).status_code==422
    assert logged.get(url(s)+suffix).status_code in (404,405)
    logged.post('/api/auth/register',json={'username':'other','password':'password123'})
    logged.post('/api/auth/login',json={'username':'other','password':'password123'})
    assert logged.get('/api/surveys/'+s['id']+suffix).status_code==404
    logged.post('/api/auth/logout')
    assert logged.get('/api/surveys/'+s['id']+suffix).status_code==401


@pytest.mark.parametrize('corruption',['unknown_option','bool','nan','missing_snapshot','duplicate_answer','bad_path','missing_version','bad_type'])
def test_corrupt_history_api_returns_conflict(logged,db,corruption):
    s=setup_survey(logged)
    result=logged.post(url(s)+'/responses',json=payload(s));assert result.status_code==201
    oid=ObjectId(result.json()['id'])
    if corruption=='missing_snapshot':db.survey_versions.delete_many({'survey_id':ObjectId(s['id'])})
    elif corruption=='missing_version':db.responses.update_one({'_id':oid},{'$unset':{'survey_schema_version':''}})
    else:
        doc=db.responses.find_one({'_id':oid})
        if corruption=='bad_path':doc['visited_question_ids']=['q1']
        elif corruption=='duplicate_answer':doc['answers'].append(doc['answers'][0])
        elif corruption=='bad_type':doc['answers']='wrong'
        else:
            target='q1' if corruption=='unknown_option' else 'q3'
            for answer in doc['answers']:
                if answer['question_id']==target:answer['value']={'unknown_option':'missing','bool':True,'nan':float('nan')}[corruption]
        db.responses.replace_one({'_id':oid},doc)
    response=logged.get('/api/surveys/'+s['id']+'/stats')
    assert response.status_code==409,response.text
    assert response.json()['detail']['code']=='statistics_data_inconsistency'
    assert 'total_responses' not in response.json()


@pytest.mark.parametrize('kind',['single_choice','multiple_choice','text','number'])
@pytest.mark.parametrize('skipped',[False,True])
def test_every_type_optional_missing_or_skipped_not_counted(logged,kind,skipped):
    s=logged.post('/api/surveys',json={'title':'未答语义','allow_anonymous':True,'allow_multiple_submissions':True}).json()
    path='/api/surveys/'+s['id']
    definitions=[{'id':'start','type':'single_choice','title':'开始','options':[{'id':'a','label':'A'},{'id':'b','label':'B'}]},
                 {'id':'middle','type':kind,'title':'中间题','required':skipped},
                 {'id':'end','type':'number','title':'结束'}]
    if 'choice' in kind:definitions[1]['options']=[{'id':'a','label':'A'},{'id':'b','label':'B'}]
    current=None
    for q in definitions:
        result=logged.post(path+'/questions',json=q);assert result.status_code==201;current=result.json()
    if skipped:
        current=logged.post(path+'/jump-rules',json={'source_question_id':'start','target_question_id':'end','operator':'equals','value':'a','priority':1}).json()
    assert logged.post(path+'/publish').status_code==200
    result=logged.post(url(s)+'/responses',json={'schema_version':current['schema_version'],'answers':[{'question_id':'start','value':'a'}]})
    assert result.status_code==201,result.text
    body=stats(logged,s);middle=entry(body['versions'][0],'middle')['statistics']
    assert middle['answered_count']==0
    if 'choice' in kind:assert all(option['count']==0 for option in middle['options'])
    if kind=='multiple_choice':assert middle['total_selections']==0
    if kind=='number':assert middle['average'] is None
