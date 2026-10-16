"""Real Uvicorn/MongoDB verification for the second iteration; no submit API."""
from bson import ObjectId
from pymongo import MongoClient

from smoke_startup import main


def verify_questions(client, check, survey, uri, database_name):
    path='/api/surveys/'+survey['id']
    data={'id':'stable','type':'multiple_choice','title':'选水果','required':True,
          'options':[{'id':'a','label':'苹果'},{'id':'b','label':'香蕉'}],
          'validation':{'min_selections':1,'max_selections':2}}
    created=check('POST',path+'/questions',201,data).json()
    assert created['schema_version']==2 and created['questions'][0]['id']=='stable'
    check('PUT',path,200,{'title':'改元信息'})
    assert check('GET',path,200).json()['schema_version']==2
    check('POST',path+'/publish',200)
    data['title']='已发布题目仍可修改'
    changed=check('PUT',path+'/questions/stable',200,data).json()
    assert changed['schema_version']==3 and changed['status']=='published'
    deleted=check('DELETE',path+'/questions/stable',200).json()
    assert deleted['schema_version']==4 and deleted['questions']==[]
    check('POST',path+'/questions',201,{'type':'number','title':'年龄','validation':{'min':0,'max':120}})
    check('POST',path+'/close',200)
    check('POST',path+'/questions',409,{'type':'text','title':'不能编辑'})
    assert check('GET',path,200).json()['questions'][0]['type']=='number'
    protected=check('POST','/api/surveys',201,{'title':'保护历史'}).json()
    check('POST','/api/surveys/'+protected['id']+'/publish',200)
    # Seed only the disposable test database to verify a future response guard.
    with MongoClient(uri) as mongo:
        result=mongo[database_name].responses.insert_one({'survey_id':ObjectId(protected['id']),
            'respondent_user_id':None,'answers':[],'survey_schema_version':1})
        check('DELETE','/api/surveys/'+protected['id'],409)
        assert mongo[database_name].responses.find_one({'_id':result.inserted_id}) is not None
    empty=check('POST','/api/surveys',201,{'title':'可删除'}).json()
    check('DELETE','/api/surveys/'+empty['id'],204)
    print('REAL_QUESTION_API_SMOKE=PASS')
    # The unchanged first-round flow publishes then closes a separate draft.
    fresh=check('POST','/api/surveys',201,{'title':'基础流程回归'}).json()
    survey.clear()
    survey.update(fresh)


if __name__=='__main__':
    main(extension=verify_questions, log_name='iteration-2/startup-server.txt')
