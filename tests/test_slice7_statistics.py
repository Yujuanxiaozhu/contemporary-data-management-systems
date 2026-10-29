"""Slice 7 cross-survey question statistics: immutable versions, snapshots and ACL."""
from copy import deepcopy
from bson import ObjectId
from test_slice4_sharing import account, clients, share, revoke, bind
from test_slice6_usage import build
from test_revisions import legacy_source


def make_question(client,kind,key='q',title=None):
    opts=[{'id':'a','label':'甲'},{'id':'b','label':'乙'}] if 'choice' in kind else []
    definition={'type':kind,'title':title or kind,'required':False,'options':opts,'validation':{}}
    r=client.post('/api/questions',json={'definition':definition},headers={'Idempotency-Key':key})
    assert r.status_code==201,r.text
    return r.json()


def new_survey(client,title):
    r=client.post('/api/surveys',json={'title':title,'allow_anonymous':True,'allow_multiple_submissions':True})
    assert r.status_code==201,r.text
    return r.json()


def publish(client,s):
    r=client.post('/api/surveys/'+s['id']+'/publish');assert r.status_code==200,r.text;return r.json()


def submit(client,s,answers):
    r=client.post('/api/public/surveys/'+s['public_token']+'/responses',json={'schema_version':s['schema_version'],'answers':[{'question_id':k,'value':v} for k,v in answers.items()]})
    assert r.status_code==201,r.text


def stats(client,qid,**params):return client.get('/api/questions/'+qid+'/stats',params=params)
def version(result,vid):return next(v for v in result['versions'] if v['question_version_id']==vid)


def test_number_versions_multiple_surveys_and_positions(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_numbers');q=make_question(owner,'number');qid=q['family']['question_id'];v1=q['version']['question_version_id']
        r=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,'definition':{'type':'number','title':'v2','required':False,'options':[],'validation':{}}},headers={'Idempotency-Key':'v2'})
        assert r.status_code==201;v2=r.json()['version']['question_version_id']
        a=bind(owner,new_survey(owner,'A'),v1,'a1').json();a=bind(owner,a,v1,'a2').json();a=publish(owner,a)
        a1,a2=[x['local_question_id'] for x in a['question_bindings']]
        submit(owner,a,{a1:20,a2:30});submit(owner,a,{})
        b=publish(owner,bind(owner,new_survey(owner,'B'),v1,'b1').json());submit(owner,b,{b['question_bindings'][0]['local_question_id']:40})
        c=publish(owner,bind(owner,new_survey(owner,'C'),v2,'c1').json());submit(owner,c,{c['question_bindings'][0]['local_question_id']:100})
        build(db,user);r=stats(owner,qid);assert r.status_code==200,r.text
        one=version(r.json(),v1);two=version(r.json(),v2)
        assert len(r.json()['versions'])==2
        assert {k:one['statistics'][k] for k in ('count','min','max','average')}=={'count':3,'min':20,'max':40,'average':30}
        assert {k:two['statistics'][k] for k in ('count','min','max','average')}=={'count':1,'min':100,'max':100,'average':100}
        assert len(one['by_occurrence'])==3
        assert len(stats(owner,qid,version_id=v1).json()['versions'])==1
        assert all(x['question_version_id']==v1 for x in stats(owner,qid,version_id=v1).json()['versions'])
        assert stats(owner,qid,scope='all').status_code==403
        submit(owner,a,{a1:50})
        refreshed=version(stats(owner,qid).json(),v1)['statistics']
        assert refreshed['count']==4 and refreshed['average']==35


def test_choice_multi_text_and_empty_numbers(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_types');pairs=[make_question(owner,k,k) for k in ('single_choice','multiple_choice','text','number')]
        s=new_survey(owner,'类型');
        for i,q in enumerate(pairs):s=bind(owner,s,q['version']['question_version_id'],'type'+str(i)).json()
        s=publish(owner,s);ids=[b['local_question_id'] for b in s['question_bindings']]
        submit(owner,s,{ids[0]:'a',ids[1]:['a','b'],ids[2]:'文本一'})
        submit(owner,s,{ids[0]:'a',ids[1]:['a'],ids[2]:''})
        submit(owner,s,{ids[0]:'b',ids[1]:[],ids[2]:'文本二'})
        submit(owner,s,{ids[0]:'',ids[1]:[],ids[2]:'',ids[3]:None})
        build(db,user)
        values=[]
        for q in pairs:
            r=stats(owner,q['family']['question_id']);assert r.status_code==200,r.text
            values.append(version(r.json(),q['version']['question_version_id'])['statistics'])
        single,multi,text,num=values
        assert single['answered_count']==3 and [x['count'] for x in single['options']]==[2,1]
        assert [round(x['percentage'],3) for x in single['options']]==[66.667,33.333]
        assert multi['answered_count']==2 and multi['total_selections']==3 and [x['count'] for x in multi['options']]==[2,1]
        assert text['answered_count']==2 and text['values']==['文本一','文本二']
        assert {k:num[k] for k in ('count','min','max','average')}=={'count':0,'min':None,'max':None,'average':None}


def test_shared_permissions_and_revoke(db):
    owner,recipient,other=clients(db)
    with owner,recipient,other:
        a=account(owner,'slice7_author');b=account(recipient,'slice7_recipient');account(other,'slice7_unrelated')
        q=make_question(owner,'text');qid=q['family']['question_id'];vid=q['version']['question_version_id']
        other_version=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':vid,'expected_revision':1,
            'definition':{'type':'text','title':'未分享新版','required':False,'options':[],'validation':{}}},headers={'Idempotency-Key':'private-v2'}).json()['version']['question_version_id']
        a_s=publish(owner,bind(owner,new_survey(owner,'作者'),vid,'author').json());submit(owner,a_s,{a_s['question_bindings'][0]['local_question_id']:'作者私文'})
        assert share(owner,vid,b['id']).status_code==201
        b_s=publish(recipient,bind(recipient,new_survey(recipient,'接收者'),vid,'recipient').json());submit(recipient,b_s,{b_s['question_bindings'][0]['local_question_id']:'接收者私文'})
        build(db,a);build(db,b)
        assert version(stats(owner,qid).json(),vid)['statistics']['values']==['作者私文']
        assert version(stats(recipient,qid).json(),vid)['statistics']['values']==['接收者私文']
        assert stats(recipient,qid,version_id=other_version).status_code==404
        assert stats(other,qid).status_code==404
        assert revoke(owner,vid,b['id']).status_code==204
        assert stats(recipient,qid).status_code==404
        assert version(stats(owner,qid).json(),vid)['statistics']['values']==['作者私文']


def test_integrity_fail_closed_and_legacy(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_integrity');q=make_question(owner,'number');qid=q['family']['question_id'];vid=q['version']['question_version_id']
        s=publish(owner,bind(owner,new_survey(owner,'historical'),vid,'bind').json());local=s['question_bindings'][0]['local_question_id'];submit(owner,s,{local:12})
        build(db,user);assert stats(owner,qid).status_code==200
        newer=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':vid,'expected_revision':1,
            'definition':{'type':'number','title':'未使用版','required':False,'options':[],'validation':{}}},headers={'Idempotency-Key':'unused-version'}).json()['version']['question_version_id']
        db.question_versions.update_one({'_id':ObjectId(newer)},{'$set':{'definition.title':'损坏'}})
        assert stats(owner,qid).status_code==409
        db.question_versions.update_one({'_id':ObjectId(newer)},{'$set':{'definition.title':'未使用版'}})
        head=db.usage_heads.find_one({'owner_id':ObjectId(user['id']),'scope':'all'})
        db.usage_manifests.delete_many({'generation_id':head['active_generation']})
        assert stats(owner,qid).status_code==409
        build(db,user);assert stats(owner,qid).status_code==200
        db.responses.update_one({'survey_id':ObjectId(s['id'])},{'$set':{'answers.0.value':'not a number'}})
        assert stats(owner,qid).status_code==409
        db.responses.update_one({'survey_id':ObjectId(s['id'])},{'$set':{'answers.0.value':12}})
        snapshot=deepcopy(db.survey_versions.find_one({'survey_id':ObjectId(s['id'])}));db.survey_versions.delete_one({'_id':snapshot['_id']})
        assert stats(owner,qid).status_code==409
        db.survey_versions.insert_one(snapshot)
        old=legacy_source(owner,db);assert stats(owner,qid).status_code==409


def test_historical_response_uses_exact_snapshot_schema(db):
    from app.services import question_bank
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_old_schema')
        first={'type':'number','title':'旧版','required':False,'options':[],'validation':{'max':10}}
        q=owner.post('/api/questions',json={'definition':first},headers={'Idempotency-Key':'old'}).json()
        qid=q['family']['question_id'];v1=q['version']['question_version_id']
        s=publish(owner,bind(owner,new_survey(owner,'历史版本'),v1,'old-binding').json())
        local=s['question_bindings'][0]['local_question_id'];submit(owner,s,{local:5})
        second={'type':'number','title':'新版','required':False,'options':[],'validation':{'min':50}}
        created=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,'definition':second},headers={'Idempotency-Key':'new-version'})
        assert created.status_code==201,created.text
        v2=created.json()['version'];new_schema=s['schema_version']+1
        question={**v2['definition'],'id':local,'order':1}
        binding={'local_question_id':local,'question_id':ObjectId(qid),'question_version_id':ObjectId(v2['question_version_id']),
                 'content_hash':v2['content_hash'],'effective_hash':question_bank.digest(v2['definition']),'required_override':None}
        old_snapshot=db.survey_versions.find_one({'survey_id':ObjectId(s['id'])})
        db.survey_versions.insert_one({**deepcopy(old_snapshot),'_id':ObjectId(),'schema_version':new_schema,
                                       'questions':[question],'question_bindings':[binding]})
        db.surveys.update_one({'_id':ObjectId(s['id'])},{'$set':{'schema_version':new_schema,'questions':[question],'question_bindings':[binding]}})
        submit(owner,{**s,'schema_version':new_schema},{local:100})
        build(db,user);result=stats(owner,qid);assert result.status_code==200,result.text
        assert version(result.json(),v1)['statistics']['values']==[5]
        assert version(result.json(),v2['question_version_id'])['statistics']['values']==[100]


def test_minimal_statistics_page_dom():
    import subprocess
    result=subprocess.run(['node','tests/slice7_stats_dom.js'],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'SLICE7_STATS_DOM=PASS' in result.stdout


def test_same_local_id_in_different_surveys_is_not_global_identity(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_local_collision');one=make_question(owner,'number','one');two=make_question(owner,'number','two')
        a=publish(owner,bind(owner,new_survey(owner,'first'),one['version']['question_version_id'],'one').json())
        b=publish(owner,bind(owner,new_survey(owner,'second'),two['version']['question_version_id'],'two').json())
        for survey in (a,b):
            oid=ObjectId(survey['id']);change={'questions.0.id':'same-id','question_bindings.0.local_question_id':'same-id'}
            db.surveys.update_one({'_id':oid},{'$set':change});db.survey_versions.update_one({'survey_id':oid},{'$set':change})
        submit(owner,a,{'same-id':12});submit(owner,b,{'same-id':99});build(db,user)
        left=stats(owner,one['family']['question_id']);right=stats(owner,two['family']['question_id'])
        assert left.status_code==200 and right.status_code==200
        assert version(left.json(),one['version']['question_version_id'])['statistics']['values']==[12]
        assert version(right.json(),two['version']['question_version_id'])['statistics']['values']==[99]


def test_jumped_question_does_not_count_as_answer(db):
    from test_public_responses import setup_survey,payload,url
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'slice7_skip');survey=setup_survey(owner)
        target=next(b for b in survey['question_bindings'] if b['local_question_id']=='q2')
        assert owner.post(url(survey)+'/responses',json=payload(survey)).status_code==201
        assert owner.post(url(survey)+'/responses',json=payload(survey,q1='b',q2='见到')).status_code==201
        build(db,user);r=stats(owner,target['question_id']);assert r.status_code==200,r.text
        result=version(r.json(),target['question_version_id'])['statistics']
        assert result['answered_count']==1 and result['values']==['见到']
