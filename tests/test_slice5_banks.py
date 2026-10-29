"""Slice 5 private banks: version defaults organize, never rewrite survey history."""
from copy import deepcopy
from bson import ObjectId
from test_slice4_sharing import account, clients, question, definition, share, revoke, bind


def create_bank(client, key='bank', name='教学题库'):
    return client.post('/api/question-banks', json={'name':name,'description':'课程'}, headers={'Idempotency-Key':key})


def add(client, bid, vid):
    return client.post(f'/api/question-banks/{bid}/items', json={'question_version_id':vid})


def test_bank_private_crud_and_idempotency(db):
    owner, other, anonymous=clients(db)
    with owner, other, anonymous:
        account(owner,'slice5_owner');account(other,'slice5_other')
        assert other.get('/api/question-banks').json()['items']==[]
        first=create_bank(owner);assert first.status_code==201,first.text
        bank=first.json();bid=bank['bank_id'];assert bank['archived'] is False
        assert create_bank(owner).json()['bank_id']==bid
        assert create_bank(owner,name='different').status_code==409
        assert owner.get('/api/question-banks').json()['items'][0]['bank_id']==bid
        assert owner.get('/api/question-banks/'+bid).status_code==200
        for method in ('get','delete'):
            assert getattr(other,method)('/api/question-banks/'+bid).status_code==404
        assert other.get(f'/api/question-banks/{bid}/items').status_code==404
        assert anonymous.get('/api/question-banks').status_code==401
        u=owner.put('/api/question-banks/'+bid,json={'name':'新名称','description':'','expected_revision':bank['revision']})
        assert u.status_code==200,u.text
        assert owner.put('/api/question-banks/'+bid,json={'name':'并发','description':'','expected_revision':bank['revision']}).status_code==409
        assert owner.delete('/api/question-banks/'+bid,params={'expected_revision':u.json()['revision']}).status_code==204
        assert owner.get('/api/question-banks/'+bid).status_code==404


def test_default_version_and_frozen_survey_history(db):
    owner, other, _=clients(db)
    with owner,other:
        account(owner,'slice5_versions');account(other,'slice5_other2')
        bank=create_bank(owner).json();bid=bank['bank_id']
        origin=question(owner);qid=origin['family']['question_id'];v1=origin['version']['question_version_id']
        v2resp=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,'definition':definition('版本二')},headers={'Idempotency-Key':'s5-v2'})
        assert v2resp.status_code==201,v2resp.text
        v2=v2resp.json()['version']['question_version_id']
        foreign=question(owner,'second-family')['version']['question_version_id']
        item=add(owner,bid,v1);assert item.status_code==201,item.text
        item=item.json();assert item['bank_id']==bid and item['selected_version_id']==v1 and item['default_version_id']==v1
        assert add(owner,bid,v1).status_code==200
        assert add(owner,bid,v2).status_code==409
        assert other.post(f'/api/question-banks/{bid}/items',json={'question_version_id':v1}).status_code==404
        assert owner.put(f'/api/question-banks/{bid}/items/{qid}',json={'question_version_id':foreign,'expected_revision':item['revision']}).status_code==409
        draft=owner.post('/api/surveys',json={'title':'旧草稿'}).json()
        pub=owner.post('/api/surveys',json={'title':'已发布'}).json()
        assert bind(owner,draft,v1,'s5-draft').status_code==201
        assert bind(owner,pub,v1,'s5-pub').status_code==201
        assert owner.post('/api/surveys/'+pub['id']+'/publish').status_code==200
        olddraft=deepcopy(db.surveys.find_one({'_id':ObjectId(draft['id'])})['question_bindings'])
        oldsnapshot=deepcopy(db.survey_versions.find_one({'survey_id':ObjectId(pub['id'])}))
        changed=owner.put(f'/api/question-banks/{bid}/items/{qid}',json={'question_version_id':v2,'expected_revision':item['revision']})
        assert changed.status_code==200,changed.text
        assert changed.json()['default_version_id']==v2 and changed.json()['selected_version_id']==v2
        assert db.surveys.find_one({'_id':ObjectId(draft['id'])})['question_bindings']==olddraft
        assert db.survey_versions.find_one({'_id':oldsnapshot['_id']})==oldsnapshot
        fresh=owner.post('/api/surveys',json={'title':'新草稿'}).json()
        listing=owner.get(f'/api/question-banks/{bid}/items').json()['items']
        assert listing[0]['default_version_id']==v2
        assert bind(owner,fresh,listing[0]['default_version_id'],'s5-new').status_code==201
        assert owner.delete(f'/api/question-banks/{bid}/items/{qid}',params={'expected_revision':changed.json()['revision']}).status_code==204
        assert owner.get('/api/question-versions/'+v1).status_code==200
        assert owner.get('/api/question-versions/'+v2).status_code==200
        assert add(owner,bid,v1).status_code==201
        assert owner.delete('/api/question-banks/'+bid,params={'expected_revision':bank['revision']}).status_code==204
        assert owner.get('/api/question-versions/'+v1).status_code==200
        assert db.survey_versions.find_one({'_id':oldsnapshot['_id']})==oldsnapshot


def test_shared_member_revoke_is_visible_but_unusable(db):
    owner, recipient, stranger=clients(db)
    with owner,recipient,stranger:
        account(owner,'slice5_share_owner');r=account(recipient,'slice5_share_recipient');account(stranger,'slice5_share_stranger')
        origin=question(owner);vid=origin['version']['question_version_id'];qid=origin['family']['question_id']
        bank=create_bank(recipient).json();bid=bank['bank_id']
        assert add(recipient,bid,vid).status_code==404
        assert share(owner,vid,r['id']).status_code==201
        item=add(recipient,bid,vid);assert item.status_code==201,item.text
        published=recipient.post('/api/surveys',json={'title':'共享历史','allow_anonymous':True}).json()
        assert bind(recipient,published,vid,'s5-shared-pub').status_code==201
        assert recipient.post('/api/surveys/'+published['id']+'/publish').status_code==200
        snapshot=deepcopy(db.survey_versions.find_one({'survey_id':ObjectId(published['id'])}))
        assert revoke(owner,vid,r['id']).status_code==204
        entry=recipient.get(f'/api/question-banks/{bid}/items').json()['items'][0]
        assert entry['available'] is False and entry['reason']=='authorization_lost'
        assert entry.get('version') is None
        draft=recipient.post('/api/surveys',json={'title':'新草稿'}).json()
        assert bind(recipient,draft,vid,'s5-after-revoke').status_code==404
        assert recipient.put(f'/api/question-banks/{bid}/items/{qid}',json={'question_version_id':vid,'expected_revision':entry['revision']}).status_code==404
        assert db.survey_versions.find_one({'_id':snapshot['_id']})==snapshot
        assert stranger.get(f'/api/question-banks/{bid}/items').status_code==404
        assert recipient.delete(f'/api/question-banks/{bid}/items/{qid}',params={'expected_revision':entry['revision']}).status_code==204


def test_bank_picker_dom_contract():
    import subprocess
    result=subprocess.run(['node','tests/slice5_dom_contract.js'],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'SLICE5_BANK_PICKER_FIXED_VERSION=PASS' in result.stdout


def test_unavailable_member_switch_dom_contract():
    import subprocess
    result=subprocess.run(['node','tests/slice5_organizer_contract.js'],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'SLICE5_UNAVAILABLE_SWITCH=PASS' in result.stdout
