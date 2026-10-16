"""Jump definition validation and owner-scoped mutations."""
import re
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.jump_rule import JumpRuleDefinition
from app.services.validation import ValidationIssue, ValidationResult, _is_number

OPERATORS = {'single_choice': {'equals'}, 'multiple_choice': {'contains'},
             'number': {'equals', 'greater_than', 'greater_than_or_equal', 'less_than', 'less_than_or_equal'}}


def validate_jump_rules(questions: list[dict], rules: list[dict]) -> ValidationResult:
    result = ValidationResult()
    by_id = {q['id']: q for q in questions}
    ids, priorities = set(), set()
    if len(rules) > 1000:
        return ValidationResult([ValidationIssue('too_many_rules', 'jump_rules', '最多 1000 条规则')])
    for index, raw in enumerate(rules):
        field = f'jump_rules.{index}'
        try:
            rule = JumpRuleDefinition.model_validate(raw).model_dump()
        except ValidationError as exc:
            result.errors.extend(ValidationIssue('invalid_rule', field + '.' + '.'.join(map(str, e['loc'])), e['msg']) for e in exc.errors())
            continue
        def error(code, message):
            result.errors.append(ValidationIssue(code, field, message))
        if rule['id'] in ids:
            error('duplicate_rule_id', '同一问卷 rule id 必须唯一')
        ids.add(rule['id'])
        key = (rule['source_question_id'], rule['priority'])
        if key in priorities:
            error('duplicate_priority', '同一 source 的 priority 不能重复')
        priorities.add(key)
        source, target = by_id.get(rule['source_question_id']), by_id.get(rule['target_question_id'])
        if source is None or target is None:
            error('missing_question', 'source 和 target 都必须存在')
            continue
        if target['order'] <= source['order']:
            error('not_forward', '只允许跳转到 order 更大的题目')
        kind = source['type']
        if rule['operator'] not in OPERATORS.get(kind, set()):
            error('invalid_operator', 'source 题型不支持该 operator')
        if kind in ('single_choice', 'multiple_choice'):
            if type(rule['value']) is not str or rule['value'] not in {o['id'] for o in source['options']}:
                error('invalid_rule_value', 'value 必须是 source 的合法 option id')
        elif kind == 'number' and not _is_number(rule['value']):
            error('invalid_rule_value', 'value 必须是有限 JSON 数字，不能是 bool 或超出 int64 的整数')
    return result


def _commit(db, survey, user, rules):
    from app.services.questions import commit_structure
    result = validate_jump_rules(survey['questions'], rules)
    if not result.valid:
        raise HTTPException(422, result.as_dict())
    rules = [JumpRuleDefinition.model_validate(rule).model_dump() for rule in rules]
    if rules == survey['jump_rules']:
        return survey
    return commit_structure(db, survey, user, {'jump_rules': rules})


def add_rule(db, survey_id: str, user: dict, data: dict) -> dict:
    from app.services.questions import _editable
    survey = _editable(db, survey_id, user)
    rule = dict(data)
    if type(rule.get('id')) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', rule['id']):
        rule['id'] = uuid4().hex
    return _commit(db, survey, user, [*survey['jump_rules'], rule])


def update_rule(db, survey_id: str, rule_id: str, user: dict, data: dict) -> dict:
    from app.services.questions import _editable
    survey = _editable(db, survey_id, user)
    if not any(r['id'] == rule_id for r in survey['jump_rules']):
        raise HTTPException(404, '跳转规则不存在')
    if 'id' in data and data['id'] != rule_id:
        raise HTTPException(422, 'rule id 不允许修改')
    rule = {'id': rule_id, **data}
    return _commit(db, survey, user, [rule if r['id'] == rule_id else r for r in survey['jump_rules']])


def delete_rule(db, survey_id: str, rule_id: str, user: dict) -> dict:
    from app.services.questions import _editable
    survey = _editable(db, survey_id, user)
    rules = [r for r in survey['jump_rules'] if r['id'] != rule_id]
    if len(rules) == len(survey['jump_rules']):
        raise HTTPException(404, '跳转规则不存在')
    return _commit(db, survey, user, rules)
