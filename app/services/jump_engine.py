"""Deterministic pure jump execution and complete response-path validation."""
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.validation import MISSING, ValidationIssue, validate_answer


class JumpEngineError(ValueError):
    pass


def _next(definition: dict, current_question_id: str, answer: Any) -> str | None:
    questions = sorted(definition['questions'], key=lambda q: q['order'])
    by_id = {q['id']: q for q in questions}
    if current_question_id not in by_id:
        raise JumpEngineError('当前题目不存在')
    source = by_id[current_question_id]
    rules = sorted((r for r in definition['jump_rules'] if r['source_question_id'] == current_question_id),
                   key=lambda r: (r['priority'], r['id']))
    for rule in rules:
        matched = False
        if answer is not MISSING and answer is not None:
            op, value = rule['operator'], rule['value']
            if op == 'contains':
                matched = type(answer) is list and value in answer
            elif op == 'equals':
                matched = answer == value
            elif op == 'greater_than':
                matched = answer > value
            elif op == 'greater_than_or_equal':
                matched = answer >= value
            elif op == 'less_than':
                matched = answer < value
            elif op == 'less_than_or_equal':
                matched = answer <= value
            else:
                raise JumpEngineError('未知跳转 operator')
        if matched:
            if rule['target_question_id'] not in by_id:
                raise JumpEngineError('跳转目标题目不存在')
            return rule['target_question_id']
    position = next(i for i, q in enumerate(questions) if q['id'] == source['id'])
    return questions[position + 1]['id'] if position + 1 < len(questions) else None


def resolve_next_question(definition: dict, current_question_id: str, answer: Any = MISSING) -> str | None:
    question = next((q for q in definition['questions'] if q['id'] == current_question_id), None)
    if question is None:
        raise JumpEngineError('当前题目不存在')
    result = validate_answer(question, answer)
    if not result.valid:
        raise JumpEngineError('; '.join(error.message for error in result.errors))
    return _next(definition, current_question_id, answer)


@dataclass
class ResponsePathResult:
    visited_question_ids: list[str] = field(default_factory=list)
    errors: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self):
        return not self.errors

    def as_dict(self):
        return {'valid': self.valid, 'visited_question_ids': self.visited_question_ids,
                'errors': [asdict(error) for error in self.errors]}


def validate_response_path(definition: dict, answers: dict[str, Any], max_steps: int | None = None) -> ResponsePathResult:
    result = ResponsePathResult()
    ordered = sorted(definition['questions'], key=lambda q: q['order'])
    by_id = {q['id']: q for q in ordered}
    current = ordered[0]['id'] if ordered else None
    visited = set()
    limit = max_steps if max_steps is not None else len(ordered) + 1
    while current is not None:
        if current in visited or len(visited) >= limit or current not in by_id:
            result.errors.append(ValidationIssue('unsafe_path', 'path', '检测到循环、无效目标或最大步数超限'))
            return result
        visited.add(current)
        result.visited_question_ids.append(current)
        answer = answers.get(current, MISSING)
        validation = validate_answer(by_id[current], answer)
        if not validation.valid:
            result.errors.extend(ValidationIssue(e.code, f'answers.{current}', e.message) for e in validation.errors)
            return result
        try:
            current = _next(definition, current, answer)
        except JumpEngineError as exc:
            result.errors.append(ValidationIssue('unsafe_path', 'path', str(exc)))
            return result
    extra = answers.keys() - visited
    if extra:
        result.errors.append(ValidationIssue('extraneous_answer', 'answers', '包含被跳过或不存在题目的答案: ' + ', '.join(sorted(extra))))
    return result
