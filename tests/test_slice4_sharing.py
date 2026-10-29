"""Slice 4: immutable-version sharing, revocation, and server-side authorization."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
import pytest

from bson import ObjectId
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import create_app


def account(client, name):
    data = {'username': name, 'password': 'temporary-pass-42'}
    assert client.post('/api/auth/register', json=data).status_code == 201
    assert client.post('/api/auth/login', json=data).status_code == 200
    return client.get('/api/auth/me').json()


def definition(title='共享题'):
    return {'type': 'number', 'title': title, 'required': True, 'options': [], 'validation': {}}


def clients(db):
    return [TestClient(create_app(Settings(_env_file=None), database=db)) for _ in range(3)]


def question(client, key='family'):
    r=client.post('/api/questions',json={'definition':definition()},headers={'Idempotency-Key':key})
    assert r.status_code==201,r.text
    return r.json()


def bind(client, survey, vid, key='bind'):
    return client.post('/api/surveys/'+survey['id']+'/question-references',json={
        'question_version_id':vid,'required_override':None,'expected_schema_version':survey['schema_version']},
        headers={'Idempotency-Key':key})


def share(client, vid, uid):
    return client.put(f'/api/question-versions/{vid}/shares/{uid}',json={})


def revoke(client, vid, uid):
    return client.delete(f'/api/question-versions/{vid}/shares/{uid}')


def test_private_grant_version_scope_and_server_authorization(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        a=account(owner,'slice4_owner');b=account(grantee,'slice4_grantee');account(other,'slice4_other')
        q=question(owner);qid=q['family']['question_id'];v1=q['version']['question_version_id']
        v2=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,
            'definition':definition('不分享的第二版')},headers={'Idempotency-Key':'version2'}).json()['version']['question_version_id']
        assert grantee.get('/api/question-versions/'+v1).status_code==404
        assert other.get('/api/question-versions/'+v1).status_code==404
        assert grantee.get('/api/shared-question-versions').json()['items']==[]
        r=share(owner,v1,b['id']);assert r.status_code in (200,201),r.text
        assert grantee.get('/api/question-versions/'+v1).status_code==200
        assert grantee.get('/api/question-versions/'+v2).status_code==404
        assert other.get('/api/question-versions/'+v1).status_code==404
        assert grantee.get('/api/questions/'+qid).status_code==404
        assert grantee.get('/api/questions/'+qid+'/versions').status_code==404
        assert grantee.get(f'/api/question-versions/{v1}/shares').status_code==404
        items=grantee.get('/api/shared-question-versions').json()['items']
        assert [x['question_version_id'] for x in items]==[v1]
        assert grantee.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,
            'definition':definition('窃取')},headers={'Idempotency-Key':'steal'}).status_code==404
        assert share(grantee,v1,a['id']).status_code==404
        assert revoke(other,v1,b['id']).status_code==404
        assert other.get('/api/questions').json()['items']==[]
        assert owner.get('/api/questions/'+qid).status_code==200
        assert db.questions.find_one({'_id':ObjectId(qid)})['owner_id']==ObjectId(a['id'])


def test_revoke_existing_draft_and_published_snapshot(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner2');b=account(grantee,'slice4_grantee2');account(other,'slice4_other2')
        q=question(owner);vid=q['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        published=grantee.post('/api/surveys',json={'title':'历史','allow_anonymous':True}).json()
        draft=grantee.post('/api/surveys',json={'title':'草稿'}).json()
        a=bind(grantee,published,vid,'published-binding');assert a.status_code==201,a.text
        bnd=bind(grantee,draft,vid,'draft-binding');assert bnd.status_code==201,bnd.text
        p=grantee.post('/api/surveys/'+published['id']+'/publish');assert p.status_code==200,p.text
        before=deepcopy(db.survey_versions.find_one({'survey_id':ObjectId(published['id'])}))
        assert revoke(owner,vid,b['id']).status_code==204
        assert grantee.get('/api/question-versions/'+vid).status_code==404
        assert grantee.get('/api/shared-question-versions').json()['items']==[]
        new=grantee.post('/api/surveys',json={'title':'新草稿'}).json()
        assert bind(grantee,new,vid,'after-revoke').status_code==404
        denied=grantee.post('/api/surveys/'+draft['id']+'/publish');assert denied.status_code==409,denied.text
        assert denied.json()['detail']['code']=='authorization_revoked'
        assert db.survey_versions.find_one({'_id':before['_id']})==before
        assert grantee.get('/api/surveys/'+published['id']).status_code==200
        assert owner.get('/api/question-versions/'+vid).status_code==200
        assert db.surveys.find_one({'_id':ObjectId(draft['id'])})['question_bindings']


def test_shared_version_does_not_disclose_unshared_history_ids(db):
    owner, grantee, _ = clients(db)
    with owner, grantee:
        account(owner, 'slice4_history_owner')
        recipient = account(grantee, 'slice4_history_grantee')
        first = question(owner, 'history-family')
        qid = first['family']['question_id']
        v1 = first['version']['question_version_id']
        response = owner.post(f'/api/questions/{qid}/versions', json={
            'parent_version_id': v1, 'expected_revision': 1,
            'definition': definition('共享第二版')}, headers={'Idempotency-Key': 'history-v2'})
        assert response.status_code == 201, response.text
        v2 = response.json()['version']['question_version_id']
        assert share(owner, v2, recipient['id']).status_code in (200, 201)
        assert grantee.get('/api/question-versions/' + v1).status_code == 404
        direct = grantee.get('/api/question-versions/' + v2).json()
        listed = grantee.get('/api/shared-question-versions').json()['items'][0]
        for row in (direct, listed):
            assert row['question_version_id'] == v2
            assert row['parent_version_id'] is None
            assert row['restored_from'] is None
            assert row['restored_from_version_id'] is None
        assert owner.get('/api/question-versions/' + v2).json()['parent_version_id'] == v1


def test_fork_creates_recipient_owned_family_with_provenance(db):
    owner, grantee, other = clients(db)
    with owner, grantee, other:
        account(owner, 'slice4_fork_owner')
        recipient = account(grantee, 'slice4_fork_recipient')
        account(other, 'slice4_fork_other')
        original = question(owner, 'fork-origin')
        vid = original['version']['question_version_id']
        url = f'/api/question-versions/{vid}/fork'
        headers = {'Idempotency-Key': 'fork-1'}
        assert other.post(url, json={}, headers=headers).status_code == 404
        assert share(owner, vid, recipient['id']).status_code in (200, 201)
        first = grantee.post(url, json={'definition': definition('我的派生题')}, headers=headers)
        assert first.status_code == 201, first.text
        forked = first.json()
        assert forked['family']['owner_id'] == recipient['id']
        assert forked['family']['question_id'] != original['family']['question_id']
        assert forked['version']['derived_from_version_id'] == vid
        assert grantee.post(url, json={'definition': definition('我的派生题')}, headers=headers).json()['family']['question_id'] == forked['family']['question_id']
        assert grantee.post(url, json={}, headers=headers).status_code == 409
        assert revoke(owner, vid, recipient['id']).status_code == 204
        assert grantee.get('/api/question-versions/' + forked['version']['question_version_id']).status_code == 200
        assert grantee.post(url, json={}, headers={'Idempotency-Key': 'fork-after-revoke'}).status_code == 404
        assert owner.get('/api/question-versions/' + vid).json()['definition'] == original['version']['definition']


def test_fork_admitted_before_revoke_recovers_same_intent(db, monkeypatch):
    from app.services import question_bank
    owner, grantee, _ = clients(db)
    with owner, grantee:
        account(owner, 'slice4_fork_race_owner')
        recipient = account(grantee, 'slice4_fork_race_recipient')
        vid = question(owner, 'fork-race-origin')['version']['question_version_id']
        assert share(owner, vid, recipient['id']).status_code in (200, 201)
        def fail_after_admission(name, operation):
            if name == 'fork_admitted':
                raise RuntimeError('test interruption after admission')
        monkeypatch.setattr(question_bank, 'checkpoint', fail_after_admission)
        url = f'/api/question-versions/{vid}/fork'
        with pytest.raises(RuntimeError, match='test interruption'):
            grantee.post(url, json={}, headers={'Idempotency-Key': 'fork-race'})
        assert revoke(owner, vid, recipient['id']).status_code == 204
        monkeypatch.setattr(question_bank, 'checkpoint', lambda *args: None)
        resumed = grantee.post(url, json={}, headers={'Idempotency-Key': 'fork-race'})
        assert resumed.status_code == 201, resumed.text
        assert resumed.json()['version']['derived_from_version_id'] == vid
        assert grantee.post(url, json={'definition': definition('changed')}, headers={'Idempotency-Key': 'fork-race'}).status_code == 409


def test_share_lifecycle_validation_and_uniqueness(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        a=account(owner,'slice4_owner3');b=account(grantee,'slice4_grantee3');account(other,'slice4_other3')
        vid=question(owner)['version']['question_version_id']
        assert share(owner,vid,a['id']).status_code==422
        assert share(owner,vid,str(ObjectId())).status_code==404
        assert share(owner,vid,b['id']).status_code in (200,201)
        first=db.question_shares.find_one({'question_version_id':ObjectId(vid),'grantee_user_id':ObjectId(b['id'])})
        assert share(owner,vid,b['id']).status_code==200
        assert db.question_shares.count_documents({'question_version_id':ObjectId(vid),'grantee_user_id':ObjectId(b['id'])})==1
        assert revoke(owner,vid,b['id']).status_code==204
        assert revoke(owner,vid,b['id']).status_code==204
        assert share(owner,vid,b['id']).status_code==200
        again=db.question_shares.find_one({'_id':first['_id']})
        assert again['grant_epoch']>first['grant_epoch']
        assert grantee.get('/api/question-versions/'+vid).status_code==200
        assert owner.get('/api/question-versions/'+vid+'/shares').status_code==200


def test_anonymous_and_legacy_private(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner4');account(grantee,'slice4_grantee4');account(other,'slice4_other4')
        q=question(owner);vid=q['version']['question_version_id']
        assert grantee.get('/api/question-versions/'+vid).status_code==404
        owner.post('/api/auth/logout')
        assert owner.get('/api/question-versions/'+vid).status_code==401
        assert owner.get('/api/shared-question-versions').status_code==401


def test_publish_ticket_survives_revoke_and_regrant_after_interruption(db, monkeypatch):
    from pymongo.errors import AutoReconnect
    from app.services import share_publish
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner5');b=account(grantee,'slice4_grantee5');account(other,'slice4_other5')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'票据'}).json();assert bind(grantee,survey,vid).status_code==201
        calls=[]
        def fail_once(stage,op):
            if stage=='share_admitted' and not calls:
                calls.append(stage);raise AutoReconnect('injected after admission')
        monkeypatch.setattr(share_publish,'checkpoint',fail_once)
        path='/api/surveys/'+survey['id']+'/publish';first=grantee.post(path)
        assert first.status_code==503,first.text
        assert revoke(owner,vid,b['id']).status_code==204
        assert share(owner,vid,b['id']).status_code==200
        resumed=grantee.post(path);assert resumed.status_code==200,resumed.text
        assert resumed.json()['status']=='published'
        ops=list(db.share_publish_operations.find({'survey_id':ObjectId(survey['id'])}))
        assert len(ops)==1 and ops[0]['requirements'][0]['grant_epoch']==1
        grant=db.question_shares.find_one({'question_version_id':ObjectId(vid),'grantee_user_id':ObjectId(b['id'])})
        assert grant['grant_epoch']==2 and grant['admission_count']==0
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==1


def test_revoke_before_publish_admission_and_regrant_requires_new_operation(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner6');b=account(grantee,'slice4_grantee6');account(other,'slice4_other6')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'撤销后发布'}).json();assert bind(grantee,survey,vid).status_code==201
        assert revoke(owner,vid,b['id']).status_code==204
        path='/api/surveys/'+survey['id']+'/publish';denied=grantee.post(path)
        assert denied.status_code==409 and denied.json()['detail']['code']=='authorization_revoked'
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==0
        assert share(owner,vid,b['id']).status_code==200
        accepted=grantee.post(path);assert accepted.status_code==200,accepted.text
        ops=list(db.share_publish_operations.find({'survey_id':ObjectId(survey['id'])}))
        assert len(ops)==2 and {x['requirements'][0]['grant_epoch'] for x in ops}=={1,2}


def test_selected_binding_admission_survives_revoke_after_interruption(db,monkeypatch):
    from pymongo.errors import AutoReconnect
    from app.services import draft_bindings
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner7');b=account(grantee,'slice4_grantee7');account(other,'slice4_other7')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'中断绑定'}).json();fired=[]
        def fail_once(stage,op):
            if stage=='share_admitted' and not fired:
                fired.append(stage);raise AutoReconnect('injected')
        monkeypatch.setattr(draft_bindings,'checkpoint',fail_once)
        first=bind(grantee,survey,vid);assert first.status_code==503,first.text
        assert revoke(owner,vid,b['id']).status_code==204
        resumed=grantee.get('/api/surveys/'+survey['id']);assert resumed.status_code==200,resumed.text
        assert resumed.json()['question_bindings'][0]['question_version_id']==vid
        assert grantee.post('/api/surveys/'+survey['id']+'/publish').status_code==409


def test_shared_draft_page_after_revoke_reports_loss_without_deleting_data(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner8');b=account(grantee,'slice4_grantee8');account(other,'slice4_other8')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'保留草稿'}).json();assert bind(grantee,survey,vid).status_code==201
        assert revoke(owner,vid,b['id']).status_code==204
        page=grantee.get('/surveys/'+survey['id']+'/edit');assert page.status_code==200
        assert '授权已失效' in page.text
        assert len(db.surveys.find_one({'_id':ObjectId(survey['id'])})['question_bindings'])==1


def test_shared_published_survey_remains_answerable_after_revoke(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner9');b=account(grantee,'slice4_grantee9');account(other,'slice4_other9')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'公开历史','allow_anonymous':True,'allow_multiple_submissions':True}).json()
        result=bind(grantee,survey,vid);assert result.status_code==201,result.text
        data=result.json();assert grantee.post('/api/surveys/'+survey['id']+'/publish').status_code==200
        assert revoke(owner,vid,b['id']).status_code==204
        public='/api/public/surveys/'+survey['public_token']
        assert other.get(public).status_code==200
        response=other.post(public+'/responses',json={'schema_version':data['schema_version'],
            'answers':[{'question_id':data['questions'][0]['id'],'value':35}]})
        assert response.status_code==201,response.text
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==1


def test_concurrent_share_creates_one_record(db):
    from app.services import question_shares
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        a=account(owner,'slice4_owner10');b=account(grantee,'slice4_grantee10');account(other,'slice4_other10')
        vid=question(owner)['version']['question_version_id'];gate=Barrier(2)
        def work():
            gate.wait();return question_shares.grant(db,vid,b['id'],{'_id':ObjectId(a['id'])})
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:work(),range(2)))
        assert {str(x[0]['_id']) for x in results}.__len__()==1
        assert db.question_shares.count_documents({'question_version_id':ObjectId(vid),'grantee_user_id':ObjectId(b['id']),'state':'ACTIVE'})==1


def test_usernames_share_and_shared_views_do_not_expose_owner_history(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner11');b=account(grantee,'slice4_grantee11');account(other,'slice4_other11')
        q=question(owner);vid=q['version']['question_version_id'];qid=q['family']['question_id']
        path='/api/question-versions/'+vid+'/shares'
        assert owner.post(path,json={'username':'slice4_grantee11'}).status_code==201
        assert owner.post(path,json={'username':'slice4_grantee11'}).status_code==200
        assert owner.post(path,json={'username':'no-such-user'}).status_code==404
        assert grantee.post(path,json={'username':'slice4_owner11'}).status_code==404
        row=owner.get(path).json()['items'][0];assert row['username']=='slice4_grantee11'
        assert grantee.get('/question-bank').status_code==200
        shared=grantee.get('/api/shared-question-versions').json()['items'];assert len(shared)==1
        assert shared[0]['owner_username']=='slice4_owner11' and shared[0]['question_version_id']==vid
        assert grantee.get('/question-bank/'+qid).status_code==404


def test_concurrent_revoke_after_publish_admission_allows_exact_operation(db,monkeypatch):
    from threading import Event
    from app.services import share_publish
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner12');b=account(grantee,'slice4_grantee12');account(other,'slice4_other12')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'并发授权'}).json();assert bind(grantee,survey,vid).status_code==201
        admitted,continue_work=Event(),Event()
        def checkpoint(stage,op):
            if stage=='share_admitted':admitted.set();assert continue_work.wait(10)
        monkeypatch.setattr(share_publish,'checkpoint',checkpoint)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(grantee.post,'/api/surveys/'+survey['id']+'/publish')
            assert admitted.wait(10)
            try:assert revoke(owner,vid,b['id']).status_code==204
            finally:continue_work.set()
            result=future.result(timeout=15)
        assert result.status_code==200,result.text
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==1
        assert grantee.get('/api/question-versions/'+vid).status_code==404


def test_two_shares_revoke_unadmitted_version_blocks_entire_publish(db,monkeypatch):
    from threading import Event
    from app.services import share_publish
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner13');b=account(grantee,'slice4_grantee13');account(other,'slice4_other13')
        a=question(owner,'first-share');c=question(owner,'second-share');v1=a['version']['question_version_id'];v2=c['version']['question_version_id']
        assert share(owner,v1,b['id']).status_code in (200,201);assert share(owner,v2,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'双授权'}).json();first=bind(grantee,survey,v1,'one');assert first.status_code==201
        second=bind(grantee,first.json(),v2,'two');assert second.status_code==201
        admitted,continue_work=Event(),Event();stages=[]
        def checkpoint(stage,op):
            if stage=='share_admitted' and not stages:
                stages.append(stage);admitted.set();assert continue_work.wait(10)
        monkeypatch.setattr(share_publish,'checkpoint',checkpoint)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(grantee.post,'/api/surveys/'+survey['id']+'/publish');assert admitted.wait(10)
            try:assert revoke(owner,v2,b['id']).status_code==204
            finally:continue_work.set()
            result=future.result(timeout=15)
        assert result.status_code==409 and result.json()['detail']['code']=='authorization_revoked'
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==0
        assert db.surveys.find_one({'_id':ObjectId(survey['id'])})['status']=='draft'


def test_share_revision_preconditions(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner14');b=account(grantee,'slice4_grantee14');account(other,'slice4_other14')
        vid=question(owner)['version']['question_version_id'];path=f"/api/question-versions/{vid}/shares/{b['id']}"
        assert owner.put(path,json={'expected_revision':1}).status_code==409
        first=owner.put(path,json={});assert first.status_code==201
        assert owner.delete(path,params={'expected_revision':99}).status_code==409
        assert owner.delete(path,params={'expected_revision':first.json()['revision']}).status_code==204
        assert grantee.get('/api/question-versions/'+vid).status_code==404


def test_publish_ticket_cannot_follow_changed_metadata(db,monkeypatch):
    from threading import Event
    from app.services import share_publish
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner15');b=account(grantee,'slice4_grantee15');account(other,'slice4_other15')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'原始标题'}).json();assert bind(grantee,survey,vid).status_code==201
        ready,continue_work=Event(),Event()
        def checkpoint(stage,op):
            if stage=='ready':ready.set();assert continue_work.wait(10)
        monkeypatch.setattr(share_publish,'checkpoint',checkpoint)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(grantee.post,'/api/surveys/'+survey['id']+'/publish');assert ready.wait(10)
            try:
                edit=grantee.put('/api/surveys/'+survey['id'],json={'title':'并发修改标题'});assert edit.status_code==200,edit.text
            finally:continue_work.set()
            result=future.result(timeout=15)
        assert result.status_code==409,result.text
        op=db.share_publish_operations.find_one({'survey_id':ObjectId(survey['id'])});assert op['state']=='ABORTED'
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==0


def test_grantee_legacy_put_requires_own_family(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner16');b=account(grantee,'slice4_grantee16');account(other,'slice4_other16')
        q=question(owner);vid=q['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'共享题草稿'}).json();bound=bind(grantee,survey,vid);assert bound.status_code==201
        local=bound.json()['questions'][0]['id'];original=deepcopy(db.question_versions.find_one({'_id':ObjectId(vid)}))
        result=grantee.put('/api/surveys/'+survey['id']+'/questions/'+local,json={'type':'number','title':'修改','required':True})
        assert result.status_code==409 and result.json()['detail']['code']=='requires_fork'
        assert db.question_versions.find_one({'_id':ObjectId(vid)})==original


def test_shared_version_dom_contract():
    import shutil,subprocess
    node=shutil.which('node');assert node
    result=subprocess.run([node,'tests/slice4_dom_contract.js'],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'SLICE4_SHARED_DOM=PASS' in result.stdout


def test_multiple_revoked_bindings_can_be_removed_without_silent_mutation(db):
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner17');b=account(grantee,'slice4_grantee17');account(other,'slice4_other17')
        first=question(owner,'first');second=question(owner,'second');v1=first['version']['question_version_id'];v2=second['version']['question_version_id']
        assert share(owner,v1,b['id']).status_code in (200,201);assert share(owner,v2,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'两项撤销'}).json()
        one=bind(grantee,survey,v1,'one');assert one.status_code==201
        two=bind(grantee,one.json(),v2,'two');assert two.status_code==201
        assert revoke(owner,v1,b['id']).status_code==204;assert revoke(owner,v2,b['id']).status_code==204
        local1=two.json()['questions'][0]['id'];local2=two.json()['questions'][1]['id']
        removed=grantee.delete('/api/surveys/'+survey['id']+'/questions/'+local1);assert removed.status_code==200,removed.text
        assert [x['id'] for x in removed.json()['questions']]==[local2]
        removed2=grantee.delete('/api/surveys/'+survey['id']+'/questions/'+local2);assert removed2.status_code==200,removed2.text
        assert removed2.json()['questions']==[]


def test_sealed_publish_recovers_after_revoke(db,monkeypatch):
    from pymongo.errors import AutoReconnect
    from app.services import versions
    owner,grantee,other=clients(db)
    with owner,grantee,other:
        account(owner,'slice4_owner18');b=account(grantee,'slice4_grantee18');account(other,'slice4_other18')
        vid=question(owner)['version']['question_version_id'];assert share(owner,vid,b['id']).status_code in (200,201)
        survey=grantee.post('/api/surveys',json={'title':'封存后恢复'}).json();assert bind(grantee,survey,vid).status_code==201
        original=versions.finish_pending;fired=[]
        def fail_after_seal(db_arg,survey_arg):
            if survey_arg.get('_pending_schema') and not fired:
                fired.append(True);raise AutoReconnect('after sealed')
            return original(db_arg,survey_arg)
        monkeypatch.setattr(versions,'finish_pending',fail_after_seal)
        path='/api/surveys/'+survey['id'];assert grantee.post(path+'/publish').status_code==503
        op=db.share_publish_operations.find_one({'survey_id':ObjectId(survey['id'])});assert op['state']=='SEALED'
        assert revoke(owner,vid,b['id']).status_code==204
        recovered=grantee.get(path);assert recovered.status_code==200 and recovered.json()['status']=='published'
        assert db.share_publish_operations.find_one({'_id':op['_id']})['state']=='COMMITTED'
        assert db.survey_versions.count_documents({'survey_id':ObjectId(survey['id'])})==1
