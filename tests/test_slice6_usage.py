"""Slice 6: authoritative usage coverage, permissions, and generation recovery."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from bson import ObjectId
from fastapi import HTTPException
import pytest
from test_slice4_sharing import account, clients, question, definition, share, revoke, bind
from test_revisions import create_revision, legacy_source


def build(db, user, scope='all'):
    from app.services import usage
    return usage.rebuild(db, {'_id':ObjectId(user['id'])}, scope)


def query(client,qid,**params):
    return client.get('/api/questions/'+qid+'/usages',params=params)


def draft(client,title):
    r=client.post('/api/surveys',json={'title':title,'allow_anonymous':True});assert r.status_code==201,r.text;return r.json()


def test_current_multiple_positions_versions_and_rebuild(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_owner1');q=question(owner);qid=q['family']['question_id'];v1=q['version']['question_version_id']
        v2=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':v1,'expected_revision':1,'definition':definition('第二版')},headers={'Idempotency-Key':'usage-v2'}).json()['version']['question_version_id']
        a=draft(owner,'a');b=draft(owner,'b');a=bind(owner,a,v1,'a1').json();a=bind(owner,a,v1,'a2').json();b=bind(owner,b,v2,'b1').json()
        assert query(owner,qid).status_code==409
        build(db,user);response=query(owner,qid);assert response.status_code==200,response.text
        rows=response.json()['items'];assert len(rows)==3
        assert {r['question_version_id'] for r in rows}=={v1,v2}
        assert len({(r['survey_id'],r['local_question_id']) for r in rows})==3
        assert len(query(owner,qid,version_id=v1).json()['items'])==2
        first=query(owner,qid,limit=1).json();assert len(first['items'])==1 and first['next_cursor']
        assert query(owner,qid,version_id=v1,cursor=first['next_cursor']).status_code==422
        second=query(owner,qid,limit=2,cursor=first['next_cursor']).json();assert len(second['items'])==2
        assert {r['local_question_id'] for r in first['items']+second['items']}=={r['local_question_id'] for r in rows}
        before=sorted((r['survey_id'],r['local_question_id'],r['question_version_id']) for r in rows)
        build(db,user);assert sorted((r['survey_id'],r['local_question_id'],r['question_version_id']) for r in query(owner,qid).json()['items'])==before
        local=a['question_bindings'][0]['local_question_id'];assert owner.delete('/api/surveys/'+a['id']+'/questions/'+local).status_code==200
        assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==2


def test_history_revision_and_bank_are_not_usage(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_owner2');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bank=owner.post('/api/question-banks',json={'name':'库'},headers={'Idempotency-Key':'usage-bank'}).json()
        item=owner.post('/api/question-banks/'+bank['bank_id']+'/items',json={'question_version_id':vid});assert item.status_code==201
        build(db,user);assert query(owner,qid).json()['items']==[]
        newer=owner.post(f'/api/questions/{qid}/versions',json={'parent_version_id':vid,'expected_revision':1,
            'definition':definition('新版本')},headers={'Idempotency-Key':'usage-bank-version'})
        assert newer.status_code==201
        changed=owner.put('/api/question-banks/'+bank['bank_id']+'/items/'+qid,json={
            'question_version_id':newer.json()['version']['question_version_id'],'expected_revision':item.json()['revision']})
        assert changed.status_code==200
        assert query(owner,qid).json()['items']==[]
        s=bind(owner,draft(owner,'published'),vid,'hist').json();published=owner.post('/api/surveys/'+s['id']+'/publish');assert published.status_code==200
        build(db,user);rows=query(owner,qid).json()['items'];assert len(rows)==1 and rows[0]['historical'] and rows[0]['source_kind']=='published_snapshot'
        snap=deepcopy(db.survey_versions.find_one({'survey_id':ObjectId(s['id'])}))
        child=create_revision(owner,published.json());assert child.status_code==201,child.text
        build(db,user);rows=query(owner,qid).json()['items'];assert {r['survey_id'] for r in rows}=={s['id'],child.json()['id']}
        assert db.survey_versions.find_one({'_id':snap['_id']})==snap
        assert owner.delete('/api/question-banks/'+bank['bank_id'],params={'expected_revision':bank['revision']}).status_code==204
        assert len(query(owner,qid).json()['items'])==2


def test_share_visibility_revocation_and_survey_privacy(db):
    owner, recipient, other=clients(db)
    with owner,recipient,other:
        a=account(owner,'usage_owner3');b=account(recipient,'usage_recipient');account(other,'usage_stranger')
        q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id'];assert share(owner,vid,b['id']).status_code==201
        s=bind(recipient,draft(recipient,'private recipient survey'),vid,'shared').json();assert recipient.post('/api/surveys/'+s['id']+'/publish').status_code==200
        build(db,a);build(db,b)
        assert query(owner,qid).json()['items']==[]
        assert len(query(recipient,qid).json()['items'])==1
        assert query(other,qid).status_code==404
        assert revoke(owner,vid,b['id']).status_code==204
        assert query(recipient,qid).status_code==404 # Q8 is not approved.
        assert query(owner,qid).json()['items']==[]
        assert bind(recipient,draft(recipient,'new'),vid,'after').status_code==404
        assert db.survey_versions.count_documents({'survey_id':ObjectId(s['id'])})==1


def test_missing_rows_manifests_and_building_fail_closed(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_integrity');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bind(owner,draft(owner,'tracked'),vid,'tracked');build(db,user)
        uid=ObjectId(user['id']);head=db.usage_heads.find_one({'owner_id':uid,'scope':'all'});gen=head['active_generation']
        rows=list(db.question_usages.find({'generation_id':gen}));assert len(rows)==1
        db.question_usages.delete_one({'_id':rows[0]['_id']});assert query(owner,qid).status_code==409
        build(db,user);head=db.usage_heads.find_one({'owner_id':uid,'scope':'all'});gen=head['active_generation']
        db.usage_manifests.delete_one({'generation_id':gen});assert query(owner,qid).status_code==409
        build(db,user);head=db.usage_heads.find_one({'owner_id':uid,'scope':'all'});gen=head['active_generation']
        db.usage_generations.update_one({'_id':gen},{'$set':{'state':'BUILDING'}});assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==1


@pytest.mark.parametrize('stage',['generation_created','row_written','source_written','before_verify'])
def test_failed_rebuild_preserves_previous_ready(db,monkeypatch,stage):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_fault_'+stage);q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        first=bind(owner,draft(owner,'one'),vid,'one').json();bind(owner,first,vid,'two');build(db,user);before=deepcopy(query(owner,qid).json())
        def stop(name,*args):
            if name==stage:raise RuntimeError('injected rebuild fault')
        monkeypatch.setattr(usage,'checkpoint',stop)
        with pytest.raises(RuntimeError,match='injected rebuild fault'):build(db,user)
        assert query(owner,qid).json()==before
        assert db.usage_generations.count_documents({'state':'FAILED'})>=1
        if stage=='row_written':
            failed=db.usage_generations.find_one({'owner_id':ObjectId(user['id']),'state':'FAILED'})
            assert db.question_usages.count_documents({'generation_id':failed['_id']})==1
        monkeypatch.setattr(usage,'checkpoint',lambda *args:None);build(db,user)
        assert len(query(owner,qid).json()['items'])==2


@pytest.mark.parametrize('stage',['before_verify','after_verify'])
def test_changed_source_during_rebuild_cannot_be_ready(db,monkeypatch,stage):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_change');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        s=draft(owner,'race');bind(owner,s,vid,'race');build(db,user)
        def change(name,*args):
            if name==stage:db.surveys.update_one({'_id':ObjectId(s['id'])},{'$inc':{'schema_version':1}})
        monkeypatch.setattr(usage,'checkpoint',change)
        with pytest.raises(HTTPException) as e:build(db,user)
        assert e.value.status_code==409
        assert query(owner,qid).status_code==409
        monkeypatch.setattr(usage,'checkpoint',lambda *args:None);build(db,user)
        assert len(query(owner,qid).json()['items'])==1


def test_legacy_requires_audited_explicit_revision_mapping(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_legacy');q=question(owner);qid=q['family']['question_id']
        old=legacy_source(owner,db)
        with pytest.raises(HTTPException) as e:build(db,user)
        assert e.value.status_code==409 and e.value.detail['code']=='legacy_mapping_required'
        revision=create_revision(owner,old);assert revision.status_code==201,revision.text
        mapped=revision.json()['question_bindings'][0]['question_id']
        build(db,user);r=query(owner,mapped);assert r.status_code==200,r.text
        assert any(x['survey_id']==old['id'] and x['source_kind']=='legacy_mapping' for x in r.json()['items'])
        assert query(owner,qid).json()['items']==[]
        db.revision_operations.update_one({'source_survey_id':ObjectId(old['id'])},{'$set':{'plans.0.key':'forged'}})
        denied=query(owner,mapped);assert denied.status_code==409
        assert denied.json()['detail']['code']=='legacy_mapping_conflict'


def test_missing_whole_source_and_extra_row_are_not_complete(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_whole_source');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        first=draft(owner,'one');bind(owner,first,vid,'one');build(db,user)
        head=db.usage_heads.find_one({'owner_id':ObjectId(user['id']),'scope':'all'});gen=head['active_generation']
        db.question_usages.insert_one({'generation_id':gen,'source_key':'invented','local_question_id':'extra'})
        assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==1
        bind(owner,draft(owner,'whole missing source'),vid,'two')
        assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==2
        db.question_usages.delete_many({});db.usage_manifests.delete_many({})
        assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==2
        db.question_usages.drop();db.usage_manifests.drop()
        assert query(owner,qid).status_code==409
        build(db,user);assert len(query(owner,qid).json()['items'])==2
        db.surveys.update_one({'_id':ObjectId(first['id'])},{'$set':{'questions.0.order':0}})
        invalid=query(owner,qid);assert invalid.status_code==409 and invalid.json()['detail']['code']=='source_inconsistent'


def test_rebuild_verification_failure_preserves_ready(db,monkeypatch):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_verify_fault');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bind(owner,draft(owner,'one'),vid,'one');build(db,user);before=query(owner,qid).json()
        def corrupt(name,gen,*args):
            if name=='before_verify':db.question_usages.delete_many({'generation_id':gen['_id']})
        monkeypatch.setattr(usage,'checkpoint',corrupt)
        with pytest.raises(HTTPException) as e:build(db,user)
        assert e.value.status_code==409 and e.value.detail['code']=='index_incomplete'
        assert query(owner,qid).json()==before
        monkeypatch.setattr(usage,'checkpoint',lambda *args:None);build(db,user)
        assert len(query(owner,qid).json()['items'])==1


def test_source_change_during_query_fails_closed(db,monkeypatch):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_query_race');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        s=draft(owner,'race');bind(owner,s,vid,'race');build(db,user)
        def change(name,*args):
            if name=='query_verified':db.surveys.update_one({'_id':ObjectId(s['id'])},{'$inc':{'schema_version':1}})
        monkeypatch.setattr(usage,'checkpoint',change)
        response=query(owner,qid);assert response.status_code==409
        assert response.json()['detail']['code']=='source_changed'


def test_generation_stops_being_ready_during_query(db,monkeypatch):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_query_generation');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bind(owner,draft(owner,'one'),vid,'one');build(db,user)
        def invalidate(name,gen,*args):
            if name=='query_verified':db.usage_generations.update_one({'_id':gen['_id']},{'$set':{'state':'BUILDING'}})
        monkeypatch.setattr(usage,'checkpoint',invalidate)
        response=query(owner,qid);assert response.status_code==409
        assert response.json()['detail']['code']=='index_incomplete'


def test_referenced_missing_historical_snapshot_fails_closed(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_missing_snapshot');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        s=bind(owner,draft(owner,'history'),vid,'binding').json();assert owner.post('/api/surveys/'+s['id']+'/publish').status_code==200
        build(db,user);assert query(owner,qid).status_code==200
        db.responses.insert_one({'survey_id':ObjectId(s['id']),'survey_schema_version':999})
        assert query(owner,qid).status_code==409


def test_separate_current_and_historical_scopes(db):
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_scopes');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bound=bind(owner,draft(owner,'published'),vid,'scope-pub').json()
        assert owner.post('/api/surveys/'+bound['id']+'/publish').status_code==200
        bind(owner,draft(owner,'current'),vid,'scope-draft')
        build(db,user,'current');build(db,user,'historical')
        current=query(owner,qid,scope='current').json();history=query(owner,qid,scope='historical').json()
        assert len(current['items'])==1 and current['items'][0]['historical'] is False
        assert len(history['items'])==1 and history['items'][0]['historical'] is True
        assert current['coverage']['scope']=='current' and history['coverage']['scope']=='historical'
        assert query(owner,qid).status_code==409


def test_concurrent_rebuild_cas_exposes_only_complete_generation(db,monkeypatch):
    from app.services import usage
    owner,_,_=clients(db)
    with owner:
        user=account(owner,'usage_concurrent');q=question(owner);qid=q['family']['question_id'];vid=q['version']['question_version_id']
        bind(owner,draft(owner,'one'),vid,'concurrent');build(db,user)
        old=db.usage_heads.find_one({'owner_id':ObjectId(user['id']),'scope':'all'})['active_generation']
        gate=Barrier(2)
        def wait(name,*args):
            if name=='before_verify':gate.wait(timeout=15)
        monkeypatch.setattr(usage,'checkpoint',wait)
        def attempt(_):
            try:return build(db,user)
            except HTTPException as e:return e
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        assert sum(isinstance(x,dict) for x in results)==1
        assert sum(isinstance(x,HTTPException) and x.status_code==409 for x in results)==1
        assert db.usage_generations.find_one({'_id':old})['state']=='READY'
        monkeypatch.setattr(usage,'checkpoint',lambda *args:None)
        assert len(query(owner,qid).json()['items'])==1
