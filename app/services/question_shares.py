"""Explicit grants for one immutable question version; no implicit family access."""
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow
from app.services import question_bank as bank


def ensure_indexes(db):
    db.question_shares.create_index([('question_version_id',1),('grantee_user_id',1)],unique=True)
    db.question_shares.create_index([('grantee_user_id',1),('state',1),('_id',1)])


def owner_version(db, vid, owner):
    v = db.question_versions.find_one({'_id': bank.oid(vid)})
    if v is None or not bank.committed(db, v):
        bank.fail(404, 'resource_not_found')
    bank.owned(db, str(v['question_id']), owner)
    return v


def grant(db, vid, uid, owner, expected_revision=None):
    v = owner_version(db, vid, owner)
    grantee = bank.oid(uid)
    if grantee == owner['_id']:
        bank.fail(422, 'self_share')
    if db.users.find_one({'_id': grantee}, {'_id':1}) is None:
        bank.fail(404, 'resource_not_found')
    ensure_indexes(db)
    scope = {'question_version_id':v['_id'], 'grantee_user_id':grantee}
    now = utcnow()
    try:
        row = {**scope,'_id':ObjectId(),'owner_user_id':owner['_id'], 'question_id':v['question_id'],
               'state':'ACTIVE','grant_epoch':1,'revision':1,'created_at':now,'revoked_at':None,
               'admissions':{},'admission_count':0}
        if expected_revision is not None and db.question_shares.find_one(scope) is None:
            bank.fail(409,'concurrent_modification')
        db.question_shares.insert_one(row)
        return row, True
    except DuplicateKeyError:
        pass
    while True:
        row = db.question_shares.find_one(scope)
        if row is None:
            bank.fail(409,'concurrent_modification')
        if expected_revision is not None and row['revision']!=expected_revision:
            bank.fail(409,'concurrent_modification')
        if row['state']=='ACTIVE':
            return row, False
        updated=db.question_shares.find_one_and_update(
            {'_id':row['_id'],'state':'REVOKED','revision':row['revision']},
            {'$set':{'state':'ACTIVE','revoked_at':None},'$inc':{'grant_epoch':1,'revision':1}},
            return_document=ReturnDocument.AFTER)
        if updated is not None:
            return updated, False


def revoke(db, vid, uid, owner, expected_revision=None):
    v=owner_version(db,vid,owner)
    grantee=bank.oid(uid)
    row=db.question_shares.find_one({'question_version_id':v['_id'],'grantee_user_id':grantee})
    if row is None:
        bank.fail(404,'resource_not_found')
    if expected_revision is not None and row['revision']!=expected_revision:
        bank.fail(409,'concurrent_modification')
    # Update the same share document as admission, preserving in-flight receipts.
    if row['state']=='ACTIVE':
        result=db.question_shares.update_one({'_id':row['_id'],'state':'ACTIVE','revision':row['revision']},
            {'$set':{'state':'REVOKED','revoked_at':utcnow()},'$inc':{'revision':1}})
        if not result.matched_count:
            current=db.question_shares.find_one({'_id':row['_id']})
            if expected_revision is not None or current is None or current['state']!='REVOKED':bank.fail(409,'concurrent_modification')


def output(row):
    return {'share_id':str(row['_id']),'question_version_id':str(row['question_version_id']),
            'grantee_user_id':str(row['grantee_user_id']),'state':row['state'],
            'grant_epoch':row['grant_epoch'],'revision':row['revision'],
            'created_at':row['created_at'].isoformat(),
            'revoked_at':row['revoked_at'].isoformat() if row.get('revoked_at') else None}


def active(db, vid, user):
    return db.question_shares.find_one({'question_version_id':vid,'grantee_user_id':user['_id'],'state':'ACTIVE'})


def shared_versions(db,user,cursor=None,limit=20):
    query={'grantee_user_id':user['_id'],'state':'ACTIVE'}
    if cursor:query['_id']={'$gt':bank.oid(cursor)}
    rows=[]
    for grant in db.question_shares.find(query).sort('_id',1):
        version=db.question_versions.find_one({'_id':grant['question_version_id']})
        family=db.questions.find_one({'_id':grant['question_id'],'owner_id':grant['owner_user_id']})
        if version is None or family is None or not bank.committed(db,version):continue
        owner=db.users.find_one({'_id':grant['owner_user_id']},{'username':1})
        if owner is None:continue
        rows.append((grant,version,owner))
        if len(rows)>limit:break
    return {'items':[{**bank.shared_version_out(v),'owner_username':u['username']} for _,v,u in rows[:limit]],
            'next_cursor':str(rows[limit-1][0]['_id']) if len(rows)>limit else None}


MAX_ADMISSIONS = 128

def admit(db, grant, operation_id, fingerprint):
    """Linearize one payload-scoped admission against revoke on the share document."""
    field='admissions.'+str(operation_id)
    receipt={'operation_id':str(operation_id),'grant_epoch':grant['grant_epoch'],
             'question_version_id':str(grant['question_version_id']),'payload_hash':fingerprint}
    updated=db.question_shares.find_one_and_update(
        {'_id':grant['_id'],'state':'ACTIVE','grant_epoch':grant['grant_epoch'],
         'admission_count':{'$lt':MAX_ADMISSIONS},field:{'$exists':False}},
        {'$set':{field:receipt},'$inc':{'admission_count':1}},
        return_document=ReturnDocument.AFTER)
    if updated is not None:return receipt
    current=db.question_shares.find_one({'_id':grant['_id']})
    recorded=(current or {}).get('admissions',{}).get(str(operation_id))
    if recorded is not None:
        if recorded != receipt:bank.fail(409,'idempotency_conflict',operation_id)
        return recorded
    if current is None or current['state']!='ACTIVE' or current['grant_epoch']!=grant['grant_epoch']:
        bank.fail(409,'authorization_revoked',operation_id)
    bank.fail(409,'authorization_capacity',operation_id)

def forget_admission(db, share_id, operation_id):
    field='admissions.'+str(operation_id)
    db.question_shares.update_one({'_id':share_id,field:{'$exists':True}},
        {'$unset':{field:''},'$inc':{'admission_count':-1}})
