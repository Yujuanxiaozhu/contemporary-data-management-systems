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
        return updated
    current = db.surveys.find_one({'_id': survey['_id']})
    # Another worker may have helped complete this exact reserved commit.
    if current is not None and current['schema_version'] >= snapshot['schema_version'] and current['status'] != 'draft':
        return current
    raise HTTPException(409, '快照提交未完成，请重试；当前版本未推进')


def snapshot_commit(db, survey: dict, updates: dict, reason: str) -> dict:
    version = updates.get('schema_version', survey['schema_version'])
    snapshot = {'_id': ObjectId(), 'survey_id': survey['_id'], 'schema_version': version,
                'questions': deepcopy(updates.get('questions', survey['questions'])),
                'jump_rules': deepcopy(updates.get('jump_rules', survey['jump_rules'])),
                'created_at': utcnow(), 'created_reason': reason}
    pending = {'id': uuid4().hex, 'base_version': survey['schema_version'],
               'base_status': survey['status'], 'updates': deepcopy(updates), 'snapshot': snapshot}
    reserved = db.surveys.find_one_and_update(
        {'_id': survey['_id'], 'owner_id': survey['owner_id'], 'schema_version': survey['schema_version'],
         'status': survey['status'], '_pending_schema': {'$exists': False}},
        {'$set': {'_pending_schema': pending}}, return_document=ReturnDocument.AFTER)
    if reserved is None:
        raise HTTPException(409, '问卷已被并发修改，请重新读取后重试')
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
