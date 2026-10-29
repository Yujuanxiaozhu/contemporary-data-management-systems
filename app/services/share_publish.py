"""Payload-scoped, recoverable share admissions for publication."""
from bson import ObjectId, json_util
from pymongo.errors import DuplicateKeyError
from fastapi import HTTPException
from app.services import question_bank as bank, question_shares as shares
from app.core.security import utcnow
import hashlib


def checkpoint(name, operation):
    """Failure-injection point."""


def payload_hash(survey):
    data={k:survey.get(k) for k in ('_id','owner_id','schema_version','questions','question_bindings','jump_rules','title','description','allow_anonymous','allow_multiple_submissions','deadline')}
    return hashlib.sha256(json_util.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def acquire(db,survey,user):
    """Admit each exact grant/epoch and keep durable receipts on the operation."""
    fingerprint=payload_hash(survey)
    # A pending operation remains the same intent even if a grant is later reissued.
    op=db.share_publish_operations.find_one({'owner_id':user['_id'],'survey_id':survey['_id'],
        'base_schema':survey['schema_version'],'payload_hash':fingerprint,
        'state':{'$in':['PREPARED','PARTIALLY_ADMITTED','READY']}})
    if op is not None:
        requirements=op['requirements'];opid=op['_id']
    else:
        requirements=[]
        for binding in survey.get('question_bindings',[]):
            vid=binding['question_version_id']
            version=db.question_versions.find_one({'_id':vid})
            family=db.questions.find_one({'_id':binding['question_id']})
            if version is None or family is None or version['question_id']!=family['_id']:
                bank.fail(409,'binding_mismatch')
            if family['owner_id']==user['_id']:continue
            grant=db.question_shares.find_one({'question_version_id':vid,'grantee_user_id':user['_id']})
            if grant is None:bank.fail(409,'authorization_revoked',message='共享题授权已失效，请移除、替换或重新获授权。')
            if not any(x['share_id']==grant['_id'] for x in requirements):
                requirements.append({'share_id':grant['_id'],'version_id':vid,'grant_epoch':grant['grant_epoch']})
        if not requirements:return set(), None
        identity=hashlib.sha256(json_util.dumps({'survey':survey['_id'],'base':survey['schema_version'],
            'hash':fingerprint,'requirements':requirements},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        opid=ObjectId(identity[:24]);db.share_publish_operations.create_index([('survey_id',1),('owner_id',1),('base_schema',1)])
        op={'_id':opid,'owner_id':user['_id'],'survey_id':survey['_id'],'base_schema':survey['schema_version'],
            'payload_hash':fingerprint,'requirements':requirements,'receipts':{},'state':'PREPARED','created_at':utcnow()}
        try:db.share_publish_operations.insert_one(op)
        except DuplicateKeyError:
            op=db.share_publish_operations.find_one({'_id':opid})
            if op is None or op['payload_hash']!=fingerprint or op['requirements']!=requirements:
                bank.fail(409,'idempotency_conflict',opid)
    for req in requirements:
        field=str(req['share_id']);op=db.share_publish_operations.find_one({'_id':opid})
        receipt=op.get('receipts',{}).get(field)
        if receipt is None:
            grant=db.question_shares.find_one({'_id':req['share_id']})
            if grant is None:bank.fail(409,'authorization_revoked',opid)
            # An operation is tied to its original epoch even across a later regrant.
            grant={**grant,'grant_epoch':req['grant_epoch']}
            try:
                receipt=shares.admit(db,grant,opid,fingerprint)
            except HTTPException as exc:
                latest=db.share_publish_operations.find_one({'_id':opid})
                receipt=(latest or {}).get('receipts',{}).get(field)
                if receipt is None:
                    if exc.status_code==409 and exc.detail.get('code')=='authorization_revoked':
                        db.share_publish_operations.update_one({'_id':opid,'receipts.'+field:{'$exists':False}}, {'$set':{'state':'BLOCKED'}})
                    raise
            checkpoint('share_admitted',op)
            db.share_publish_operations.update_one({'_id':opid,'payload_hash':fingerprint, 'state':{'$in':['PREPARED','PARTIALLY_ADMITTED']}},
                {'$set':{'receipts.'+field:receipt,'state':'PARTIALLY_ADMITTED'}})
        shares.forget_admission(db,req['share_id'],opid)
        if receipt['payload_hash']!=fingerprint or receipt['grant_epoch']!=req['grant_epoch']:
            bank.fail(409,'operation_inconsistent',opid)
    db.share_publish_operations.update_one({'_id':opid,'state':{'$in':['PREPARED','PARTIALLY_ADMITTED']}},{'$set':{'state':'READY'}})
    checkpoint('ready',op)
    return {x['version_id'] for x in requirements}, opid
