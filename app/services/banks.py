"""Private bank organization. Immutable versions and grants remain authoritative."""
from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow
from app.services import question_bank as qb


def indexes(db):
    db.question_banks.create_index([('owner_id',1),('create_key',1)], unique=True)
    db.question_banks.create_index([('owner_id',1),('archived_at',1),('_id',1)])
    db.bank_items.create_index([('bank_id',1),('question_id',1)],unique=True)
    db.bank_items.create_index([('bank_id',1),('_id',1)])


def owned(db,bid,user):
    bank=db.question_banks.find_one({'_id':qb.oid(bid),'owner_id':user['_id'],'archived_at':None})
    if bank is None:qb.fail(404,'resource_not_found')
    return bank


def bank_out(b):
    return {'bank_id':str(b['_id']),'name':b['name'],'description':b['description'],'revision':b['revision'],'archived':b['archived_at'] is not None,
            'created_at':b['created_at'].isoformat(),'updated_at':b['updated_at'].isoformat()}


def create(db,user,key,body):
    if not key or len(key)>128 or any(ord(c)<33 or ord(c)>126 for c in key):qb.fail(422,'invalid_idempotency_key')
    indexes(db);fingerprint=qb.digest(body);now=utcnow()
    row={'_id':ObjectId(),'owner_id':user['_id'],'name':body['name'],'description':body['description'],
         'revision':1,'created_at':now,'updated_at':now,'archived_at':None,'create_key':key,'create_hash':fingerprint}
    try:db.question_banks.insert_one(row)
    except DuplicateKeyError:
        row=db.question_banks.find_one({'owner_id':user['_id'],'create_key':key})
        if not row or row['create_hash']!=fingerprint:qb.fail(409,'idempotency_conflict')
        if row['archived_at'] is not None:qb.fail(410,'bank_archived')
    return bank_out(row)


def list_banks(db,user,cursor,limit):
    query={'owner_id':user['_id'],'archived_at':None}
    if cursor:query['_id']={'$gt':qb.oid(cursor)}
    rows=list(db.question_banks.find(query).sort('_id',1).limit(limit+1))
    return {'items':[bank_out(x) for x in rows[:limit]],'next_cursor':str(rows[limit-1]['_id']) if len(rows)>limit else None}


def update(db,bid,user,body):
    bank=owned(db,bid,user)
    row=db.question_banks.find_one_and_update({'_id':bank['_id'],'owner_id':user['_id'],'archived_at':None,'revision':body['expected_revision']},
        {'$set':{'name':body['name'],'description':body['description'],'updated_at':utcnow()},'$inc':{'revision':1}},return_document=ReturnDocument.AFTER)
    if row is None:qb.fail(409,'concurrent_modification')
    return bank_out(row)


def remove_bank(db,bid,user,revision):
    bank=owned(db,bid,user)
    if revision is None:qb.fail(422,'expected_revision_required')
    r=db.question_banks.update_one({'_id':bank['_id'],'archived_at':None,'revision':revision},
        {'$set':{'archived_at':utcnow(),'updated_at':utcnow()},'$inc':{'revision':1}})
    if not r.matched_count:qb.fail(409,'concurrent_modification')


def item_out(db,item,user):
    result={'item_id':str(item['_id']),'bank_id':str(item['bank_id']),'question_id':str(item['question_id']),
            'selected_version_id':str(item['selected_version_id']),'default_version_id':str(item['selected_version_id']),
            'revision':item['revision'],'added_at':item['added_at'].isoformat(),'updated_at':item['updated_at'].isoformat()}
    try:v=qb.get_version(db,str(item['selected_version_id']),user)
    except HTTPException as exc:
        if exc.status_code!=404:raise
        return {**result,'available':False,'reason':'authorization_lost','version':None}
    family=db.questions.find_one({'_id':v['question_id']})
    version=qb.version_out(v) if family['owner_id']==user['_id'] else qb.shared_version_out(v)
    return {**result,'available':True,'reason':None,'version':version}


def list_items(db,bid,user,cursor,limit):
    bank=owned(db,bid,user);query={'bank_id':bank['_id']}
    if cursor:query['_id']={'$gt':qb.oid(cursor)}
    rows=list(db.bank_items.find(query).sort('_id',1).limit(limit+1))
    return {'items':[item_out(db,x,user) for x in rows[:limit]],'next_cursor':str(rows[limit-1]['_id']) if len(rows)>limit else None}


def add(db,bid,user,vid):
    bank=owned(db,bid,user);version=qb.get_version(db,vid,user);indexes(db);now=utcnow()
    item={'_id':ObjectId(),'bank_id':bank['_id'],'question_id':version['question_id'],'selected_version_id':version['_id'],
          'added_by':user['_id'],'added_at':now,'updated_at':now,'revision':1}
    try:db.bank_items.insert_one(item);created=True
    except DuplicateKeyError:
        item=db.bank_items.find_one({'bank_id':bank['_id'],'question_id':version['question_id']})
        if not item or item['selected_version_id']!=version['_id']:qb.fail(409,'bank_item_exists')
        created=False
    return item_out(db,item,user),created


def update_item(db,bid,qid,user,vid,revision):
    bank=owned(db,bid,user);qid=qb.oid(qid)
    item=db.bank_items.find_one({'bank_id':bank['_id'],'question_id':qid})
    if item is None:qb.fail(404,'resource_not_found')
    version=qb.get_version(db,vid,user)
    if version['question_id']!=qid:qb.fail(409,'version_family_conflict')
    result=db.bank_items.find_one_and_update({'_id':item['_id'],'revision':revision},
        {'$set':{'selected_version_id':version['_id'],'updated_at':utcnow()},'$inc':{'revision':1}},return_document=ReturnDocument.AFTER)
    if result is None:qb.fail(409,'concurrent_modification')
    return item_out(db,result,user)


def remove_item(db,bid,qid,user,revision):
    bank=owned(db,bid,user);qid=qb.oid(qid)
    item=db.bank_items.find_one({'bank_id':bank['_id'],'question_id':qid})
    if item is None:qb.fail(404,'resource_not_found')
    if revision is None:qb.fail(422,'expected_revision_required')
    if not db.bank_items.delete_one({'_id':item['_id'],'revision':revision}).deleted_count:qb.fail(409,'concurrent_modification')
