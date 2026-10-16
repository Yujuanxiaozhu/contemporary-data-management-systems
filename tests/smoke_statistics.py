"""HTTP/browser-route demo with independent hand-calculated statistic checks."""
import json
from pathlib import Path
from bson import ObjectId
from pymongo import MongoClient
from smoke_startup import main

ROOT=Path(__file__).resolve().parents[1]


def verify_statistics(client, check, survey, uri, database_name):
    path='/api/surveys/'+survey['id']
    for page in ['/register','/login','/dashboard','/surveys/new']:
        check('GET',page,200)
    check('PUT',path,200,{'title':'统计完整演示','description':'手算核对','allow_anonymous':True,'allow_multiple_submissions':True})
    qs=[{'id':'route','type':'single_choice','title':'路线','required':True,'options':[{'id':'a','label':'旧常规'},{'id':'b','label':'跳转'}]},
        {'id':'fruit','type':'multiple_choice','title':'水果','options':[{'id':'x','label':'苹果'},{'id':'y','label':'香蕉'}],'validation':{'min_selections':1,'max_selections':2}},
        {'id':'text','type':'text','title':'感想','validation':{'min_length':1,'max_length':100}},
        {'id':'score','type':'number','title':'数字','required':True,'validation':{'min':0,'max':100}}]
    for q in qs:check('POST',path+'/questions',201,q)
    check('POST',path+'/jump-rules',201,{'source_question_id':'route','operator':'equals','value':'b','target_question_id':'score','priority':1})
    published=check('POST',path+'/publish',200).json()
    check('GET',path.replace('/api','')+'/edit',200)
    dashboard=check('GET','/dashboard',200)
    assert '/survey/'+published['public_token'] in dashboard.text
    public='/api/public/surveys/'+published['public_token']
    check('GET','/survey/'+published['public_token'],200)
    check('GET',public,200)
    def submit(version,values):
        for qid,value in values.items():
            step=check('POST',public+'/next',200,{'schema_version':version,'current_question_id':qid,'answer':value}).json()
            if qid=='route' and value=='b':assert step['next_question_id']=='score'
        return check('POST',public+'/responses',201,{'schema_version':version,'answers':[{'question_id':k,'value':v} for k,v in values.items()]})
    old=published['schema_version']
    submit(old,{'route':'a','fruit':['x','y'],'text':'第一条','score':10})
    submit(old,{'route':'b','score':20})
    submit(old,{'route':'a','fruit':['x'],'text':'第二条','score':30})
    before=check('GET',path+'/stats',200).json()
    def stat(version,qid):return next(e['statistics'] for e in version['questions'] if e['question']['id']==qid)
    v=before['versions'][0]
    assert before['total_responses']==3 and v['response_count']==3
    assert [o['count'] for o in stat(v,'route')['options']]==[2,1]
    assert stat(v,'fruit')['answered_count']==2 and stat(v,'fruit')['total_selections']==3
    assert [o['count'] for o in stat(v,'fruit')['options']]==[2,1]
    assert stat(v,'text')['values']==['第一条','第二条']
    assert stat(v,'score')['average']==20 and stat(v,'score')['min']==10 and stat(v,'score')['max']==30
    check('GET',path.replace('/api','')+'/stats',200)
    check('GET',path+'/questions/score/stats',200)
    edited={**qs[0],'options':[{'id':'a','label':'新常规'},{'id':'b','label':'跳转'},{'id':'c','label':'新增路线'}]}
    new=check('PUT',path+'/questions/route',200,edited).json()['schema_version']
    submit(new,{'route':'c','fruit':['y'],'text':'新版本','score':40})
    final=check('GET',path+'/stats',200).json()
    assert final['total_responses']==4 and len(final['versions'])==2
    assert [v['response_count'] for v in final['versions']]==[3,1]
    assert [stat(v,'score')['average'] for v in final['versions']]==[20,40]
    assert stat(final['versions'][0],'route')['options'][0]['label']=='旧常规'
    assert stat(final['versions'][1],'route')['options'][0]['label']=='新常规'
    single=check('GET',path+'/questions/route/stats',200).json()
    assert len(single['versions'])==2
    with MongoClient(uri,tz_aware=True) as mongo:
        db=mongo[database_name]
        assert db.responses.count_documents({'survey_id':ObjectId(survey['id'])})==4
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==2
        assert 'survey_id_1_survey_schema_version_1' in db.responses.index_information()
        print('MONGODB_RESPONSE_SNAPSHOT_AND_INDEX=PASS')
    expected={'old_version_responses':3,'old_single_counts':[2,1],'old_multiple_answered':2,'old_multiple_total_selections':3,
              'old_multiple_counts':[2,1],'old_text_count':2,'old_number_values':[10,20,30],'old_number_average':20,
              'new_version_responses':1,'new_number_average':40,'total_responses':4}
    artifact={'expected_hand_calculation':expected,'actual_statistics':final,'comparison':'PASS',
              'arithmetic':'old: (10+20+30)/3=20; new: 40/1=40. multi: [x,y]+[x] => x=2,y=1,selections=3'}
    (ROOT/'docs/iteration-4/statistics-check.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    print('HAND_CALCULATED_EXPECTATIONS_MATCH=PASS',json.dumps(expected,ensure_ascii=False))
    check('POST',path+'/close',200)
    check('POST',public+'/responses',409,{'schema_version':new,'answers':[]})
    print('REAL_STATISTICS_AND_MANAGEMENT_SMOKE=PASS')
    fresh=check('POST','/api/surveys',201,{'title':'基础流程回归'}).json()
    survey.clear();survey.update(fresh)


if __name__=='__main__':
    main(extension=verify_statistics,log_name='iteration-4/startup-server.txt')
