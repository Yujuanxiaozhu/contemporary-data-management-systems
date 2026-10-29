"""Snapshot-first, recoverable commits on MongoDB standalone; no transactions."""
from copy import deepcopy
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.security import utcnow


def finish_pending(db, survey: dict) -> dict:
    pending = survey.get('_pending_schema')
    if pending is None:
        return survey
    # Never auto-complete a legacy operation that mutates a published structure.
    if pending['base_status'] != 'draft' and pending['updates']:
        raise HTTPException(409, 'legacy_published_pending_requires_review')
    snapshot = pending['snapshot']
    try:
        db.survey_versions.insert_one(deepcopy(snapshot))
    except DuplicateKeyError:
        existing = db.survey_versions.find_one({'survey_id': snapshot['survey_id'],
                                                 'schema_version': snapshot['schema_version']})
        if existing != snapshot:
            raise HTTPException(409, '历史快照冲突，停止结构写入，请检查数据完整性') from None
    # The immutable snapshot exists before the current pointer changes.
    updated = db.surveys.find_one_and_update(
        {'_id': survey['_id'], '_pending_schema.id': pending['id'],
         'schema_version': pending['base_version'], 'status': pending['base_status']},
        {'$set': {**pending['updates'], 'updated_at': utcnow()}, '$unset': {'_pending_schema': ''}},
        return_document=ReturnDocument.AFTER)
    if updated is not None:
        if pending.get('share_publish_operation_id'):
            db.share_publish_operations.update_one({'_id':pending['share_publish_operation_id']},{'$set':{'state':'COMMITTED'}})
        return updated
    current = db.surveys.find_one({'_id': survey['_id']})
    # Another worker may have helped complete this exact reserved commit.
    if current is not None and current['schema_version'] >= snapshot['schema_version'] and current['status'] != 'draft':
        if pending.get('share_publish_operation_id'):
            db.share_publish_operations.update_one({'_id':pending['share_publish_operation_id']},{'$set':{'state':'COMMITTED'}})
        return current
    raise HTTPException(409, '快照提交未完成，请重试；当前版本未推进')


def snapshot_commit(db, survey: dict, updates: dict, reason: str) -> dict:
    if survey['status'] != 'draft' and updates:
        raise HTTPException(409, 'published_frozen' if survey['status'] == 'published' else 'closed_readonly')
    if survey['status'] == 'draft' and updates.get('status') != 'published':
        raise HTTPException(409, '草稿结构必须通过绑定提交，快照只用于发布')
    share_opid = None
    if survey['status'] == 'draft' and updates.get('status') == 'published':
        from app.services.draft_bindings import validate_publish
        from app.services.share_publish import acquire
        granted, share_opid = acquire(db, survey, {'_id': survey['owner_id']})
        validate_publish(db, {**survey, **updates}, {'_id': survey['owner_id']}, granted)
    version = updates.get('schema_version', survey['schema_version'])
    snapshot_id = ObjectId(__import__('hashlib').sha256(('share-snapshot:'+str(share_opid)).encode()).hexdigest()[:24]) if share_opid else ObjectId()
    snapshot = {'_id': snapshot_id, 'survey_id': survey['_id'], 'schema_version': version,
                'questions': deepcopy(updates.get('questions', survey['questions'])),
                'jump_rules': deepcopy(updates.get('jump_rules', survey['jump_rules'])),
                'created_at': utcnow(), 'created_reason': reason}
    if 'question_bindings' in survey or 'question_bindings' in updates:
        snapshot['question_bindings'] = deepcopy(updates.get('question_bindings', survey.get('question_bindings', [])))
    pending = {'id': str(share_opid) if share_opid else uuid4().hex, 'base_version': survey['schema_version'],
               'base_status': survey['status'], 'updates': deepcopy(updates), 'snapshot': snapshot}
    if share_opid:
        pending['share_publish_operation_id']=share_opid
        op=db.share_publish_operations.find_one({'_id':share_opid})
        snapshot['created_at']=op['created_at']
    metadata_guard = {k:survey.get(k) for k in ('title','description','allow_anonymous','allow_multiple_submissions','deadline')} if share_opid else {}
    reserved = db.surveys.find_one_and_update(
        {'_id': survey['_id'], 'owner_id': survey['owner_id'], 'schema_version': survey['schema_version'],
         'status': survey['status'], '_pending_schema': {'$exists': False}, '_pending_binding': {'$exists': False}, **metadata_guard},
        {'$set': {'_pending_schema': pending}}, return_document=ReturnDocument.AFTER)
    if reserved is None:
        if share_opid:
            from app.services.share_publish import payload_hash
            current=db.surveys.find_one({'_id':survey['_id'],'owner_id':survey['owner_id']})
            if current is not None and current.get('status')=='draft' and not current.get('_pending_schema') and payload_hash(current)!=payload_hash(survey):
                db.share_publish_operations.update_one({'_id':share_opid,'state':{'$in':['PREPARED','PARTIALLY_ADMITTED','READY']}}, {'$set':{'state':'ABORTED'}})
        raise HTTPException(409, '问卷已被并发修改，请重新读取后重试')
    if share_opid:
        db.share_publish_operations.update_one({'_id':share_opid, 'state':{'$ne':'COMMITTED'}},{'$set':{'state':'SEALED','snapshot_id':snapshot_id}})
    # Failures propagate. The durable marker allows a later request to resume,
    # including an uncertain network outcome, without modifying a saved snapshot.
    return finish_pending(db, reserved)


def ensure_current_snapshot(db, survey: dict) -> dict:
    survey = finish_pending(db, survey)
    if survey['status'] != 'draft' and db.survey_versions.find_one(
            {'survey_id': survey['_id'], 'schema_version': survey['schema_version']}) is None:
        # Compatibility for pre-iteration-3 published/closed documents: only the
        # current definition is knowable; never fabricate older versions.
        return snapshot_commit(db, survey, {}, 'publish')
    return survey


def get_survey_version(db, survey_id, schema_version: int) -> dict:
    if not ObjectId.is_valid(survey_id):
        raise HTTPException(422, '非法 survey_id')
    survey = db.surveys.find_one({'_id': ObjectId(survey_id)})
    if survey is None:
        raise HTTPException(404, '问卷不存在')
    survey = ensure_current_snapshot(db, survey)
    if type(schema_version) is not int or schema_version < 1:
        raise HTTPException(422, 'schema_version 必须是正整数')
    snapshot = db.survey_versions.find_one({'survey_id': survey['_id'], 'schema_version': schema_version})
    if snapshot is None or schema_version > survey['schema_version'] or survey['status'] == 'draft':
        raise HTTPException(404, '历史问卷版本不存在')
    return snapshot
