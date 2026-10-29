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
    if not changes or not changes.keys() <= {'questions', 'jump_rules', '_binding_requests', '_operation'}:
        raise ValueError('Only validated structural fields may use this version boundary')
    from app.services import draft_bindings
    draft_bindings.structural_guard(survey)
    operation = changes.get('_operation', {})
    return draft_bindings.commit(db, survey, user, changes, **operation)


def _editable(db, survey_id: str, user: dict) -> dict:
    survey = get_owned(db, survey_id, user)
    from app.services.draft_bindings import structural_guard
    structural_guard(survey)
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


def add_question(db, survey_id: str, user: dict, data: dict[str, Any], key=None) -> dict:
    survey = _editable(db, survey_id, user)
    from app.services import draft_bindings as binding
    replay = binding.replay(db, survey, user, key, 'add', data)
    if replay is not None:
        return replay
    replay = binding.recent_replay(db, survey, 'add', data) if key is None and 'id' not in data else None
    if replay is not None:
        return replay
    original = deepcopy(data)
    data, hint = binding.option_fields(data)
    questions = deepcopy(survey['questions'])
    if len(questions) >= MAX_QUESTIONS:
        raise HTTPException(422, '每份问卷最多 200 题')
    question = _validated(data, uuid4().hex, len(questions) + 1)
    _required_hint(db, survey, user, question, hint)
    if any(q['id'] == question['id'] for q in questions):
        raise HTTPException(409, 'question id 已存在')
    if question['order'] > len(questions) + 1:
        raise HTTPException(422, '新增题目的 order 必须位于 1 到题目数+1')
    questions.insert(question['order'] - 1, question)
    _reorder(questions)
    _check_references(survey, questions)
    return commit_structure(db, survey, user, {'questions': questions,
        '_binding_requests': {question['id']: hint},
        '_operation': {'key': key, 'action': 'add', 'payload': original}})


def update_question(db, survey_id: str, question_id: str, user: dict, data: dict[str, Any], key=None) -> dict:
    survey = _editable(db, survey_id, user)
    from app.services import draft_bindings as binding
    payload = {'local_id': question_id, 'body': data}
    replay = binding.replay(db, survey, user, key, 'update', payload)
    if replay is None and key is None and data.get('new_family') is True:
        replay = binding.recent_replay(db, survey, 'update', payload)
    if replay is not None:
        return replay
    data, hint = binding.option_fields(data)
    questions = deepcopy(survey['questions'])
    index = next((i for i, q in enumerate(questions) if q['id'] == question_id), None)
    if index is None:
        raise HTTPException(404, '题目不存在')
    if 'id' in data and data['id'] != question_id:
        raise HTTPException(422, 'question id 不允许修改')
    question = _validated(data, question_id, index + 1)
    _required_hint(db, survey, user, question, hint)
    if question['order'] > len(questions):
        raise HTTPException(422, '修改题目的 order 必须位于 1 到题目数')
    questions.pop(index)
    questions.insert(question['order'] - 1, question)
    _reorder(questions)
    _check_references(survey, questions)
    if key is None and binding.exact_match(questions, survey['questions']) and not hint.get('new_family') and binding.hints_unchanged(survey, question_id, hint):
        return survey
    return commit_structure(db, survey, user, {'questions': questions,
        '_binding_requests': {question_id: hint},
        '_operation': {'key': key, 'action': 'update', 'payload': payload}})


def delete_question(db, survey_id: str, question_id: str, user: dict, key=None) -> dict:
    survey = _editable(db, survey_id, user)
    from app.services import draft_bindings as binding
    replay = binding.replay(db, survey, user, key, 'delete', {'local_id': question_id})
    if replay is not None:
        return replay
    questions = [deepcopy(q) for q in survey['questions'] if q['id'] != question_id]
    if len(questions) == len(survey['questions']):
        raise HTTPException(404, '题目不存在')
    _reorder(questions)
    _check_references(survey, questions)
    return commit_structure(db, survey, user, {'questions': questions,
        '_operation': {'key': key, 'action': 'delete', 'payload': {'local_id': question_id}}})


def _required_hint(db, survey, user, question, hint):
    from app.services import draft_bindings as binding, question_bank
    hint['default_required'] = question['required']
    if 'required_override' not in hint:
        return
    default = question['required']
    bound = next((b for b in survey.get('question_bindings', []) if b['local_question_id'] == question['id']), None)
    if bound and not hint.get('new_family'):
        default = question_bank.get_version(db, str(bound['question_version_id']), user)['definition']['required']
    question['required'] = default if hint['required_override'] is None else hint['required_override']
    _validated(question, question['id'], question['order'])


def _check_references(survey: dict, questions: list[dict]):
    from app.services.jump_rules import validate_jump_rules
    result = validate_jump_rules(questions, survey['jump_rules'])
    if not result.valid:
        raise HTTPException(409, {'message': '修改将破坏跳转规则，请先删除或修改相关规则', **result.as_dict()})
