"""Embedded question mutations, ordered IDs and optimistic schema versioning."""
from copy import deepcopy
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReturnDocument

from app.core.security import utcnow
from app.services.surveys import get_owned, owned_filter
from app.services.validation import validate_question_definition

MAX_QUESTIONS = 200


def commit_structure(db, survey: dict, user: dict, changes: dict) -> dict:
    """Shared version boundary for questions and future validated jump_rules edits."""
    if not changes or not changes.keys() <= {'questions', 'jump_rules'}:
        raise ValueError('Only validated structural fields may use this version boundary')
    if survey['status'] == 'published':
        from app.services.versions import ensure_current_snapshot, snapshot_commit
        ready = ensure_current_snapshot(db, survey)
        if (ready['schema_version'], ready['status']) != (survey['schema_version'], survey['status']):
            raise HTTPException(409, '恢复操作已推进版本，请重新读取后重试')
        reason = 'question_change' if 'questions' in changes else 'jump_rule_change'
        return snapshot_commit(db, survey, {**changes, 'schema_version': survey['schema_version'] + 1}, reason)
    updated = db.surveys.find_one_and_update(
        {**owned_filter(str(survey['_id']), user), 'schema_version': survey['schema_version'],
         'status': survey['status'], '_pending_schema': {'$exists': False}},
        {'$set': {**changes, 'updated_at': utcnow()}, '$inc': {'schema_version': 1}},
        return_document=ReturnDocument.AFTER)
    if updated is None:
        raise HTTPException(409, '问卷已被并发修改或删除，请重新读取后重试')
    return updated


def _editable(db, survey_id: str, user: dict) -> dict:
    survey = get_owned(db, survey_id, user)
    if survey['status'] == 'closed':
        raise HTTPException(409, '已关闭问卷的题目只读')
    return survey


def _validated(data: dict[str, Any], question_id: str, order: int) -> dict:
    result = validate_question_definition({'id': question_id, 'order': order, **data})
    if not result.valid:
        raise HTTPException(422, result.as_dict())
    assert result.question is not None
    return result.question


def _reorder(questions: list[dict]) -> None:
    for order, question in enumerate(questions, start=1):
        question['order'] = order


def add_question(db, survey_id: str, user: dict, data: dict[str, Any]) -> dict:
    survey = _editable(db, survey_id, user)
    questions = deepcopy(survey['questions'])
    if len(questions) >= MAX_QUESTIONS:
        raise HTTPException(422, '每份问卷最多 200 题')
    question = _validated(data, uuid4().hex, len(questions) + 1)
    if any(q['id'] == question['id'] for q in questions):
        raise HTTPException(409, 'question id 已存在')
    if question['order'] > len(questions) + 1:
        raise HTTPException(422, '新增题目的 order 必须位于 1 到题目数+1')
    questions.insert(question['order'] - 1, question)
    _reorder(questions)
    _check_references(survey, questions)
    return commit_structure(db, survey, user, {'questions': questions})


def update_question(db, survey_id: str, question_id: str, user: dict, data: dict[str, Any]) -> dict:
    survey = _editable(db, survey_id, user)
    questions = deepcopy(survey['questions'])
    index = next((i for i, q in enumerate(questions) if q['id'] == question_id), None)
    if index is None:
        raise HTTPException(404, '题目不存在')
    if 'id' in data and data['id'] != question_id:
        raise HTTPException(422, 'question id 不允许修改')
    question = _validated(data, question_id, index + 1)
    if question['order'] > len(questions):
        raise HTTPException(422, '修改题目的 order 必须位于 1 到题目数')
    questions.pop(index)
    questions.insert(question['order'] - 1, question)
    _reorder(questions)
    _check_references(survey, questions)
    if questions == survey['questions']:
        return survey
    return commit_structure(db, survey, user, {'questions': questions})


def delete_question(db, survey_id: str, question_id: str, user: dict) -> dict:
    survey = _editable(db, survey_id, user)
    questions = [deepcopy(q) for q in survey['questions'] if q['id'] != question_id]
    if len(questions) == len(survey['questions']):
        raise HTTPException(404, '题目不存在')
    _reorder(questions)
    _check_references(survey, questions)
    return commit_structure(db, survey, user, {'questions': questions})


def _check_references(survey: dict, questions: list[dict]):
    from app.services.jump_rules import validate_jump_rules
    result = validate_jump_rules(questions, survey['jump_rules'])
    if not result.valid:
        raise HTTPException(409, {'message': '修改将破坏跳转规则，请先删除或修改相关规则', **result.as_dict()})
