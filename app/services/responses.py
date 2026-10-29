"""Public access, historical validation and race-safe authenticated dedupe."""
from datetime import timedelta
from typing import TypeVar

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.security import utcnow
from app.schemas.response import NextInput, ResponseInput
from app.services.jump_engine import JumpEngineError, resolve_next_question, validate_response_path
from app.services.versions import ensure_current_snapshot, get_survey_version

T = TypeVar('T', bound=BaseModel)


def parse_input(model: type[T], data: dict) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(422, {'valid': False, 'errors': [
            {'code': 'invalid_input', 'field': '.'.join(map(str, error['loc'])), 'message': error['msg']}
            for error in exc.errors()]}) from None


def get_open_survey(db, token: str, user: dict | None) -> dict:
    survey = db.surveys.find_one({'public_token': token, '_revision_deleted': {'$ne': True}})
    if survey is None:
        raise HTTPException(404, '问卷不存在')
    survey = ensure_current_snapshot(db, survey)
    if survey['status'] != 'published':
        raise HTTPException(409, '问卷尚未发布或已关闭')
    if survey['deadline'] is not None and utcnow() > survey['deadline']:
        raise HTTPException(410, '问卷已超过截止时间')
    if not survey['allow_anonymous'] and user is None:
        raise HTTPException(401, '该问卷需要先登录')
    return survey


def public_survey(db, token: str, user: dict | None) -> dict:
    survey = get_open_survey(db, token, user)
    snapshot = get_survey_version(db, survey['_id'], survey['schema_version'])
    # Explicit allowlist: no owner, sessions, pending commit or internal gate fields.
    return {'id': str(survey['_id']), **{k: survey[k] for k in (
        'title', 'description', 'allow_anonymous', 'allow_multiple_submissions', 'deadline')},
        **{k: snapshot[k] for k in ('schema_version', 'questions', 'jump_rules')}}


def next_question(db, token: str, user: dict | None, data: dict) -> dict:
    survey = get_open_survey(db, token, user)
    request = parse_input(NextInput, data)
    snapshot = get_survey_version(db, survey['_id'], request.schema_version)
    try:
        next_id = resolve_next_question(snapshot, request.current_question_id, request.answer)
    except JumpEngineError as exc:
        raise HTTPException(422, {'message': str(exc)}) from None
    return {'next_question_id': next_id, 'completed': next_id is None}


def submit_response(db, token: str, user: dict | None, data: dict) -> dict:
    survey = get_open_survey(db, token, user)
    request = parse_input(ResponseInput, data)
    snapshot = get_survey_version(db, survey['_id'], request.schema_version)
    answers = {}
    for item in request.answers:
        if item.question_id in answers:
            raise HTTPException(422, '同一 question_id 不能重复提交答案')
        answers[item.question_id] = item.value
    path = validate_response_path(snapshot, answers)
    if not path.valid:
        raise HTTPException(422, path.as_dict())
    if user is not None and not survey['allow_multiple_submissions']:
        if db.responses.find_one({'survey_id': survey['_id'], 'respondent_user_id': user['_id']}) is not None:
            raise HTTPException(409, '该账号已经提交过此问卷')

    # Linearization point for current status/deadline/policies, after validation.
    # A close after this gate does not revoke a response admitted before it.
    now = utcnow()
    # BSON dates have millisecond precision: round the lower bound up so a
    # sub-millisecond deadline crossing cannot pass a truncated query value.
    deadline_bound = now + timedelta(microseconds=(-now.microsecond) % 1000)
    admitted = db.surveys.find_one_and_update(
        {'_id': survey['_id'], 'status': 'published',
         'allow_anonymous': survey['allow_anonymous'],
         'allow_multiple_submissions': survey['allow_multiple_submissions'],
         '$or': [{'deadline': None}, {'deadline': {'$gte': deadline_bound}}]},
        {'$set': {'_last_response_admitted_at': now}}, return_document=ReturnDocument.AFTER)
    if admitted is None:
        get_open_survey(db, token, user)
        raise HTTPException(409, '提交策略已改变，请重新读取问卷后重试')
    document = {'survey_id': survey['_id'], 'respondent_user_id': user['_id'] if user else None,
                'survey_schema_version': request.schema_version,
                'answers': [{'question_id': qid, 'value': answers[qid]}
                            for qid in path.visited_question_ids if qid in answers],
                'visited_question_ids': path.visited_question_ids, 'submitted_at': now}
    if user is not None and not admitted['allow_multiple_submissions']:
        document['dedupe_key'] = f"survey:{survey['_id']}:user:{user['_id']}"
    try:
        document['_id'] = db.responses.insert_one(document).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, '该账号已经提交过此问卷') from None
    return {'id': str(document['_id']), 'survey_id': str(document['survey_id']),
            **{k: document[k] for k in ('survey_schema_version', 'visited_question_ids', 'submitted_at')}}
