"""Dynamic statistics using response versions and immutable definitions."""
from collections import defaultdict
from decimal import Decimal, localcontext
import logging
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.response import ResponseInput
from app.services.jump_engine import validate_response_path
from app.services.jump_rules import validate_jump_rules
from app.services.surveys import get_owned
from app.services.validation import validate_answer, validate_question_definition


class DataConsistencyError(ValueError):
    pass


def compute_question_statistics(question: dict, values: list[Any]) -> dict:
    definition = validate_question_definition(question)
    if not definition.valid:
        raise DataConsistencyError('历史题目定义非法')
    answered = []
    for value in values:
        result = validate_answer(question, value)
        if not result.valid:
            raise DataConsistencyError(f"题目 {question['id']} 的历史答案不符合快照")
        if value is None or (type(value) is str and value == '') or (type(value) is list and not value):
            continue
        answered.append(value)
    kind = question['type']
    result = {'type': kind, 'answered_count': len(answered)}
    if kind in ('single_choice', 'multiple_choice'):
        counts = {option['id']: 0 for option in question['options']}
        for value in answered:
            selected = [value] if kind == 'single_choice' else value
            for option_id in selected:
                counts[option_id] += 1
        result['options'] = [{'option_id': option['id'], 'label': option['label'],
                              'count': counts[option['id']]} for option in question['options']]
        if kind == 'multiple_choice':
            result['total_selections'] = sum(counts.values())
    else:
        result['values'] = answered
        if kind == 'number':
            # Decimal avoids binary-sum artifacts and float overflow for large values.
            with localcontext() as context:
                context.prec = 800
                result['average'] = float(sum((Decimal(str(v)) for v in answered), Decimal(0)) / len(answered)) if answered else None
            result['min'] = min(answered) if answered else None
            result['max'] = max(answered) if answered else None
    return result


def compute_version_statistics(snapshot: dict, documents: list[dict]) -> dict:
    if type(snapshot.get('schema_version')) is not int or snapshot['schema_version'] < 1 or type(snapshot.get('questions')) is not list or type(snapshot.get('jump_rules')) is not list:
        raise DataConsistencyError('历史快照字段非法')
    if any(not validate_question_definition(q).valid for q in snapshot['questions']):
        raise DataConsistencyError('历史题目定义非法')
    questions = sorted(snapshot['questions'], key=lambda q: q['order'])
    ids = [q['id'] for q in questions]
    if len(ids) != len(set(ids)) or [q['order'] for q in questions] != list(range(1, len(questions) + 1)):
        raise DataConsistencyError('历史题目 ID 或顺序非法')
    if not validate_jump_rules(questions, snapshot['jump_rules']).valid:
        raise DataConsistencyError('历史跳转定义非法')
    values = defaultdict(list)
    for document in documents:
        if document.get('survey_id') != snapshot['survey_id'] or document.get('survey_schema_version') != snapshot['schema_version']:
            raise DataConsistencyError('答卷与快照版本不匹配')
        try:
            parsed = ResponseInput.model_validate({'schema_version': document.get('survey_schema_version'), 'answers': document.get('answers')})
        except ValidationError:
            raise DataConsistencyError('历史答卷字段结构非法') from None
        answers = {item.question_id: item.value for item in parsed.answers}
        if len(answers) != len(parsed.answers):
            raise DataConsistencyError('历史答卷包含重复题目答案')
        path = validate_response_path(snapshot, answers)
        if not path.valid or document.get('visited_question_ids') != path.visited_question_ids:
            raise DataConsistencyError('历史答卷答案或访问路径不符合快照')
        for question_id, value in answers.items():
            values[question_id].append(value)
    return {'schema_version': snapshot['schema_version'], 'response_count': len(documents),
            'questions': [{'question': question, 'statistics': compute_question_statistics(question, values[question['id']])}
                          for question in questions]}


def compute_survey_statistics(db, survey_id: str, user: dict) -> dict:
    survey = get_owned(db, survey_id, user)
    documents = list(db.responses.find({'survey_id': survey['_id']}).sort([('submitted_at', 1), ('_id', 1)]))
    try:
        grouped = defaultdict(list)
        for document in documents:
            version = document.get('survey_schema_version')
            if type(version) is not int or not 1 <= version <= survey['schema_version']:
                # A concurrent edit can advance the head after the owner read.
                latest = db.surveys.find_one({'_id': survey['_id']})
                if type(version) is not int or version < 1 or latest is None or version > latest['schema_version']:
                    raise DataConsistencyError('历史答卷版本非法')
            grouped[version].append(document)
        snapshots = {item['schema_version']: item for item in db.survey_versions.find(
            {'survey_id': survey['_id'], 'schema_version': {'$in': list(grouped)}})}
        if survey['status'] in ('published', 'closed'):
            current = db.survey_versions.find_one({'survey_id': survey['_id'], 'schema_version': survey['schema_version']})
            if current is not None:
                snapshots.setdefault(current['schema_version'], current)
        if grouped.keys() - snapshots.keys():
            raise DataConsistencyError('答卷对应历史快照缺失，不能使用当前题目代替')
        versions = [compute_version_statistics(snapshot, grouped.get(version, []))
                    for version, snapshot in sorted(snapshots.items())]
    except DataConsistencyError as exc:
        logging.getLogger(__name__).warning('Statistics data inconsistency for survey %s: %s', survey_id, exc)
        raise HTTPException(409, {'code': 'statistics_data_inconsistency', 'message': str(exc)}) from None
    return {'survey_id': str(survey['_id']), 'total_responses': len(documents), 'versions': versions}


def compute_single_question_statistics(db, survey_id: str, question_id: str, user: dict) -> dict:
    survey = compute_survey_statistics(db, survey_id, user)
    versions = []
    for version in survey['versions']:
        entry = next((entry for entry in version['questions'] if entry['question']['id'] == question_id), None)
        if entry is not None:
            versions.append({'schema_version': version['schema_version'], 'response_count': version['response_count'], **entry})
    if not versions:
        raise HTTPException(404, '所统计历史版本中不存在该题目')
    return {'survey_id': survey['survey_id'], 'question_id': question_id,
            'total_responses': survey['total_responses'], 'versions': versions}
