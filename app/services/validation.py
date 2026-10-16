"""One reusable definition/answer engine, independent of HTTP and MongoDB."""
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import ValidationError

from app.schemas.question import QuestionDefinition

MISSING = object()
ALLOWED_RULES = {
    'single_choice': set(),
    'multiple_choice': {'min_selections', 'max_selections', 'exact_selections'},
    'text': {'min_length', 'max_length'},
    'number': {'min', 'max', 'integer_only'},
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    field: str
    message: str


@dataclass
class ValidationResult:
    errors: list[ValidationIssue] = field(default_factory=list)
    question: dict[str, Any] | None = None

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {'valid': self.valid, 'errors': [asdict(error) for error in self.errors]}


def _is_number(value: Any) -> bool:
    # JSON numbers only: no bool, string coercion, NaN or Infinity.
    return ((type(value) is int and -(2**63) <= value < 2**63)
            or (type(value) is float and math.isfinite(value)))


def validate_question_definition(definition: Any) -> ValidationResult:
    result = ValidationResult()
    try:
        question = QuestionDefinition.model_validate(definition).model_dump()
    except ValidationError as exc:
        # Never include raw input/ctx: non-finite values are unsafe JSON error payloads.
        result.errors = [ValidationIssue('invalid_definition', '.'.join(map(str, e['loc'])), e['msg'])
                         for e in exc.errors()]
        return result

    def error(code: str, field: str, message: str):
        result.errors.append(ValidationIssue(code, field, message))

    kind, options, rules = question['type'], question['options'], question['validation']
    question['title'] = question['title'].strip()
    if not question['title']:
        error('empty_title', 'title', '题目标题不能为空')
    if kind in ('single_choice', 'multiple_choice'):
        if len(options) < 2:
            error('too_few_options', 'options', '选择题至少需要两个选项')
        if len({option['id'] for option in options}) != len(options):
            error('duplicate_option_id', 'options', '同一题目内 option id 必须唯一')
        for option in options:
            option['label'] = option['label'].strip()
            if not option['label']:
                error('empty_option_label', 'options', '选项文字不能为空')
    elif options:
        error('unexpected_options', 'options', '非选择题不允许 options')

    for key in rules.keys() - ALLOWED_RULES[kind]:
        error('unsupported_rule', f'validation.{key}', f'{kind} 不支持规则 {key}')

    valid_rules = True
    for key, value in rules.items():
        if key not in ALLOWED_RULES[kind]:
            continue
        if kind in ('text', 'multiple_choice'):
            if type(value) is not int or value < 0:
                error('invalid_rule_value', f'validation.{key}', '必须是非负整数，不能是 bool')
                valid_rules = False
            elif kind == 'multiple_choice' and value > len(options):
                error('impossible_selection_count', f'validation.{key}', '选择数量不能超过选项数')
                valid_rules = False
            elif value > 1_000_000:
                error('invalid_rule_value', f'validation.{key}', '长度上限不能超过 1000000')
                valid_rules = False
        elif key == 'integer_only':
            if type(value) is not bool:
                error('invalid_rule_value', f'validation.{key}', 'integer_only 必须是 bool')
                valid_rules = False
        elif not _is_number(value) or (type(value) is int and not -(2**63) <= value < 2**63):
            error('invalid_rule_value', f'validation.{key}', '边界必须是有限数字，整数须在 BSON int64 范围内')
            valid_rules = False

    if valid_rules:
        pairs = {'text': ('min_length', 'max_length'),
                 'multiple_choice': ('min_selections', 'max_selections'),
                 'number': ('min', 'max')}
        if kind in pairs:
            low, high = pairs[kind]
            if low in rules and high in rules and rules[low] > rules[high]:
                error('invalid_range', 'validation', f'{low} 不得大于 {high}')
        if kind == 'multiple_choice':
            exact = rules.get('exact_selections')
            if exact is not None and (exact < rules.get('min_selections', 0) or exact > rules.get('max_selections', len(options))):
                error('conflicting_exact', 'validation', 'exact_selections 与 min/max 冲突')
            if question['required'] and (rules.get('max_selections') == 0 or exact == 0):
                error('unsatisfiable_required', 'validation', '必答多选题必须允许至少选择一项')
        if kind == 'text' and question['required'] and rules.get('max_length') == 0:
            error('unsatisfiable_required', 'validation', '必答文本题不能将最大长度设为零')
        if kind == 'number' and rules.get('integer_only'):
            low, high = rules.get('min'), rules.get('max')
            if low is not None and high is not None and math.ceil(low) > math.floor(high):
                error('unsatisfiable_integer', 'validation', '指定范围内没有合法整数')
    if result.valid:
        result.question = question
    return result


def validate_answer(definition: Any, answer: Any = MISSING) -> ValidationResult:
    result = validate_question_definition(definition)
    if not result.valid:
        return result
    question = result.question
    assert question is not None
    kind, rules = question['type'], question['validation']

    def invalid(code: str, message: str) -> ValidationResult:
        return ValidationResult([ValidationIssue(code, 'answer', message)])

    # Missing/null skip validation for optional questions. Empty typed containers
    # are also unanswered; whitespace text is blank only for required semantics.
    empty = answer is MISSING or answer is None
    empty = empty or (kind == 'text' and type(answer) is str and answer == '')
    if kind == 'text' and question['required'] and type(answer) is str and not answer.strip():
        empty = True
    empty = empty or (kind == 'multiple_choice' and type(answer) is list and not answer)
    empty = empty or (kind == 'single_choice' and type(answer) is str and answer == '')
    if empty:
        if question['required']:
            return invalid('required', '必答题不能缺失或为空')
        return ValidationResult()

    option_ids = {option['id'] for option in question['options']}
    if kind == 'single_choice':
        if type(answer) is not str or answer not in option_ids:
            return invalid('invalid_option', '答案必须是合法 option id')
    elif kind == 'multiple_choice':
        if type(answer) is not list or any(type(v) is not str for v in answer):
            return invalid('invalid_answer_type', '多选答案必须是 option id 字符串数组')
        if len(set(answer)) != len(answer):
            return invalid('duplicate_selection', '不能重复选择同一 option')
        if not set(answer) <= option_ids:
            return invalid('invalid_option', '答案包含不存在的 option id')
        if 'exact_selections' in rules and len(answer) != rules['exact_selections']:
            return invalid('exact_selections', '选择数量必须等于 exact_selections')
        if len(answer) < rules.get('min_selections', 0):
            return invalid('min_selections', '选择数量低于 min_selections')
        if len(answer) > rules.get('max_selections', len(option_ids)):
            return invalid('max_selections', '选择数量超过 max_selections')
    elif kind == 'text':
        if type(answer) is not str:
            return invalid('invalid_answer_type', '文本答案必须是字符串')
        if len(answer) < rules.get('min_length', 0):
            return invalid('min_length', '文本长度低于 min_length')
        if 'max_length' in rules and len(answer) > rules['max_length']:
            return invalid('max_length', '文本长度超过 max_length')
    elif kind == 'number':
        if not _is_number(answer):
            return invalid('invalid_number', '答案必须是有限 JSON 数字，不能是 bool 或数字字符串')
        if rules.get('integer_only') and type(answer) is float and not answer.is_integer():
            return invalid('integer_only', '答案必须具有整数值')
        if 'min' in rules and answer < rules['min']:
            return invalid('min', '数值低于 min')
        if 'max' in rules and answer > rules['max']:
            return invalid('max', '数值超过 max')
    return ValidationResult()
