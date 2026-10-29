from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow
from app.models.survey import new_survey

def owned_filter(survey_id: str, user: dict) -> dict:
    if not ObjectId.is_valid(survey_id):
        raise HTTPException(422, 'survey_id 必须是 24 位十六进制 ObjectId')
    return {'_id': ObjectId(survey_id), 'owner_id': user['_id'], '_revision_deleted': {'$ne': True}}

def get_owned(db, survey_id: str, user: dict) -> dict:
    doc = db.surveys.find_one(owned_filter(survey_id, user))
    if doc is None:
        raise HTTPException(404, '问卷不存在')
    from app.services.versions import finish_pending
    from app.services.draft_bindings import finish_pending as finish_bindings
    return finish_pending(db, finish_bindings(db, doc))

def create_survey(db, user: dict, fields: dict) -> dict:
    for _ in range(3):
        doc = new_survey(user['_id'], fields)
        try:
            doc['_id'] = db.surveys.insert_one(doc).inserted_id
            return doc
        except DuplicateKeyError:
            continue
    raise HTTPException(503, '公开标识生成失败，请重试')

def update_survey(db, survey_id: str, user: dict, fields: dict) -> dict:
    if set(fields) - {'title', 'description', 'allow_anonymous', 'allow_multiple_submissions', 'deadline'}:
        from app.services.draft_bindings import structural_guard
        structural_guard(get_owned(db, survey_id, user))
        raise HTTPException(422, '结构字段必须通过草稿结构接口修改')
    doc = db.surveys.find_one_and_update(owned_filter(survey_id, user),
        {'$set': {**fields, 'updated_at': utcnow()}}, return_document=ReturnDocument.AFTER)
    if doc is None:
        raise HTTPException(404, '问卷不存在')
    return doc

def transition(db, survey_id: str, user: dict, target: str) -> dict:
    if target not in {'published', 'closed'}:
        raise HTTPException(422, '非法状态转换目标')
    from app.services.versions import ensure_current_snapshot, snapshot_commit
    existing = get_owned(db, survey_id, user)
    if existing['status'] == target:
        return ensure_current_snapshot(db, existing)
    source = 'draft' if target == 'published' else 'published'
    if existing['status'] != source:
        raise HTTPException(409, f'当前状态不能转换为 {target}')
    if target == 'published':
        return snapshot_commit(db, existing, {'status': 'published'}, 'publish')
    doc = db.surveys.find_one_and_update(
        {**owned_filter(survey_id, user), 'status': source, '_pending_schema': {'$exists': False}},
        {'$set': {'status': target, 'updated_at': utcnow()}}, return_document=ReturnDocument.AFTER)
    if doc is None:
        raise HTTPException(409, '问卷已被并发修改，请重试')
    return doc


def delete_survey(db, survey_id: str, user: dict):
    survey = get_owned(db, survey_id, user)
    if survey.get('_revision_operation_id'):
        op = db.revision_operations.find_one({'_id': survey['_revision_operation_id']})
        if op is None or op['state'] != 'COMMITTED':
            raise HTTPException(409, 'revision_recovery_required')
    if survey['status'] != 'draft':
        raise HTTPException(409, 'published 请先关闭问卷，closed 保留历史数据，均不能物理删除')
    if db.responses.find_one({'survey_id': survey['_id']}, {'_id': 1}) is not None:
        raise HTTPException(409, '已有答卷，不能删除历史数据，请关闭问卷')
    predicate = {**owned_filter(survey_id, user), 'status': 'draft',
                 '_pending_schema': {'$exists': False}, '_pending_binding': {'$exists': False}}
    if survey.get('_revision_operation_id'):
        # Atomic replacement keeps the _id unique while admitted stale inserters
        # can still run. No gap between removing the body and installing barrier.
        tombstone = {'_id': survey['_id'], 'owner_id': user['_id'], 'public_token': survey['public_token'],
                     '_revision_operation_id': survey['_revision_operation_id'], '_revision_deleted': True}
        if db.surveys.replace_one(predicate, tombstone).modified_count == 0:
            raise HTTPException(409, '问卷状态已改变，不能删除')
        from app.services.revisions import cleanup_deleted
        from pymongo.errors import PyMongoError
        try:
            db.revision_operations.update_one({'_id': survey['_revision_operation_id']},
                                             {'$set': {'result_deleted': True}})
            cleanup_deleted(db, survey['_revision_operation_id'])
        except PyMongoError:
            raise HTTPException(503, {'code': 'operation_recovery_required',
                                    'operation_id': str(survey['_revision_operation_id'])}) from None
    elif db.surveys.delete_one(predicate).deleted_count == 0:
        raise HTTPException(409, '问卷状态已改变，不能删除')
