"""Iteration-3 real process smoke, with disposable database and real MongoDB checks."""
from bson import ObjectId
from pymongo import MongoClient
from smoke_startup import main


def verify_responses(client, check, survey, uri, database_name):
    path='/api/surveys/'+survey['id']
    # Metadata remains on the original API, not a separate implementation.
    check('PUT',path,200,{'title':'跳转填写验收','description':'真实 Uvicorn/MongoDB',
                         'allow_anonymous':True,'allow_multiple_submissions':True})
    definitions=[
        {'id':'q1','type':'single_choice','title':'路线','required':True,'options':[{'id':'a','label':'跳过 Q2'},{'id':'b','label':'顺序'}]},
        {'id':'q2','type':'text','title':'被跳过的必答题','required':True},
        {'id':'q3','type':'number','title':'年龄','required':True,'validation':{'min':0,'max':120,'integer_only':True}},
        {'id':'q4','type':'multiple_choice','title':'选答','options':[{'id':'x','label':'X'},{'id':'y','label':'Y'}]}]
    for q in definitions:check('POST',path+'/questions',201,q)
    check('POST',path+'/jump-rules',201,{'id':'r1','source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3','priority':1})
    published=check('POST',path+'/publish',200).json()
    public='/api/public/surveys/'+published['public_token']
    check('GET','/survey/'+published['public_token'],200)
    loaded=check('GET',public,200).json()
    assert 'owner_id' not in loaded and loaded['schema_version']==published['schema_version']
    answers=[{'question_id':'q1','value':'a'},{'question_id':'q3','value':20},{'question_id':'q4','value':['x']}]
    for item, expected in zip(answers,['q3','q4',None]):
        result=check('POST',public+'/next',200,{'schema_version':loaded['schema_version'],'current_question_id':item['question_id'],'answer':item['value']}).json()
        assert result['next_question_id']==expected
    data={'schema_version':loaded['schema_version'],'answers':answers}
    first=check('POST',public+'/responses',201,data).json()
    with MongoClient(uri,tz_aware=True) as mongo:
        db=mongo[database_name]
        stored=db.responses.find_one({'_id':ObjectId(first['id'])})
        assert stored['visited_question_ids']==['q1','q3','q4']
        old=db.survey_versions.find_one({'survey_id':stored['survey_id'],'schema_version':stored['survey_schema_version']})
        assert old is not None and old['questions'][2]['validation']['max']==120
        print('MONGODB_RESPONSE_AND_ORIGINAL_SNAPSHOT=PASS')
        changed=check('PUT',path+'/questions/q3',200,{'type':'number','title':'新范围','required':True,'validation':{'min':50}}).json()
        assert changed['schema_version']==loaded['schema_version']+1
        assert db.survey_versions.find_one({'survey_id':ObjectId(survey['id']),'schema_version':changed['schema_version']}) is not None
        check('POST',public+'/responses',201,data)
        assert db.survey_versions.find_one({'_id':old['_id']})==old
        print('STALE_VERSION_SUBMISSION_WITH_IMMUTABLE_SCHEMA=PASS')
        print('INDEXES', db.survey_versions.index_information(), db.responses.index_information())
    check('POST',path+'/close',200)
    check('POST',public+'/responses',409,data)
    check('DELETE',path,409)
    print('REAL_RESPONSE_API_SMOKE=PASS')
    fresh=check('POST','/api/surveys',201,{'title':'原基础流程回归'}).json()
    survey.clear();survey.update(fresh)


if __name__=='__main__':
    main(extension=verify_responses,log_name='iteration-3/startup-server.txt')
