from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow
from app.models.survey import new_survey

def owned_filter(survey_id: str, user: dict) -> dict:
    if not ObjectId.is_valid(survey_id):
        raise HTTPException(422, 'survey_id 必须是 24 位十六进制 ObjectId')
    return {'_id': ObjectId(survey_id), 'owner_id': user['_id']}

def get_owned(db, survey_id: str, user: dict) -> dict:
    doc = db.surveys.find_one(owned_filter(survey_id, user))
    if doc is None:
        raise HTTPException(404, '问卷不存在')
    from app.services.versions import finish_pending
    return finish_pending(db, doc)

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
    doc = db.surveys.find_one_and_update(owned_filter(survey_id, user),
        {'$set': {**fields, 'updated_at': utcnow()}}, return_document=ReturnDocument.AFTER)
    if doc is None:
        raise HTTPException(404, '问卷不存在')
    return doc

def transition(db, survey_id: str, user: dict, target: str) -> dict:
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
    if survey['status'] != 'draft':
        raise HTTPException(409, 'published 请先关闭问卷，closed 保留历史数据，均不能物理删除')
    if db.responses.find_one({'survey_id': survey['_id']}, {'_id': 1}) is not None:
        raise HTTPException(409, '已有答卷，不能删除历史数据，请关闭问卷')
    if db.surveys.delete_one({**owned_filter(survey_id, user), 'status': 'draft', '_pending_schema': {'$exists': False}}).deleted_count == 0:
        raise HTTPException(409, '问卷状态已改变，不能删除')
