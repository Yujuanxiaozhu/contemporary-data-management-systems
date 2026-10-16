from copy import deepcopy

import pytest

from app.services.validation import MISSING, validate_answer, validate_question_definition


def question(kind='single_choice', *, rules=None, required=True):
    return {'id': 'q1', 'type': kind, 'title': '测试题', 'required': required,
            'order': 1, 'options': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'},
                                    {'id': 'c', 'label': 'C'}] if 'choice' in kind else [],
            'validation': rules or {}}


@pytest.mark.parametrize('kind,rules', [
    ('single_choice', {}),
    ('multiple_choice', {'min_selections': 1, 'max_selections': 3, 'exact_selections': 2}),
    ('text', {'min_length': 2, 'max_length': 5}),
    ('number', {'min': -2.5, 'max': 10, 'integer_only': True}),
])
def test_valid_definitions(kind, rules):
    result = validate_question_definition(question(kind, rules=rules))
    assert result.valid and result.question['type'] == kind
    assert result.as_dict() == {'valid': True, 'errors': []}


@pytest.mark.parametrize('kind,patch,code', [
    ('single_choice', {'type': 'unknown'}, 'invalid_definition'),
    ('single_choice', {'title': '   '}, 'empty_title'),
    ('single_choice', {'options': []}, 'too_few_options'),
    ('single_choice', {'options': [{'id':'a','label':'A'}]}, 'too_few_options'),
    ('single_choice', {'options': [{'id':'a','label':'A'}, {'id':'a','label':'B'}]}, 'duplicate_option_id'),
    ('single_choice', {'options': [{'id':'a','label':' '}, {'id':'b','label':'B'}]}, 'empty_option_label'),
    ('single_choice', {'validation': {'min_length':1}}, 'unsupported_rule'),
    ('multiple_choice', {'validation': {'min_selections':3, 'max_selections':2}}, 'invalid_range'),
    ('multiple_choice', {'validation': {'exact_selections':1, 'min_selections':2}}, 'conflicting_exact'),
    ('multiple_choice', {'validation': {'exact_selections':3, 'max_selections':2}}, 'conflicting_exact'),
    ('multiple_choice', {'validation': {'min_selections':4}}, 'impossible_selection_count'),
    ('multiple_choice', {'validation': {'exact_selections':0}}, 'unsatisfiable_required'),
    ('multiple_choice', {'validation': {'min_selections':True}}, 'invalid_rule_value'),
    ('multiple_choice', {'validation': {'min_selections':-1}}, 'invalid_rule_value'),
    ('multiple_choice', {'validation': {'exact_selections':1.0}}, 'invalid_rule_value'),
    ('text', {'validation': {'min_length':5,'max_length':2}}, 'invalid_range'),
    ('text', {'validation': {'max_length':0}}, 'unsatisfiable_required'),
    ('text', {'validation': {'max_length':1_000_001}}, 'invalid_rule_value'),
    ('text', {'validation': {'min_length':'1'}}, 'invalid_rule_value'),
    ('text', {'options': [{'id':'a','label':'A'}]}, 'unexpected_options'),
    ('number', {'validation': {'min':5,'max':2}}, 'invalid_range'),
    ('number', {'validation': {'min':float('nan')}}, 'invalid_rule_value'),
    ('number', {'validation': {'max':float('inf')}}, 'invalid_rule_value'),
    ('number', {'validation': {'min':False}}, 'invalid_rule_value'),
    ('number', {'validation': {'min':2**63}}, 'invalid_rule_value'),
    ('number', {'validation': {'integer_only':1}}, 'invalid_rule_value'),
    ('number', {'validation': {'min':0.2,'max':0.8,'integer_only':True}}, 'unsatisfiable_integer'),
    ('number', {'validation': {'max_length':10}}, 'unsupported_rule'),
    ('number', {'id':'bad.id'}, 'invalid_definition'),
    ('number', {'order':True}, 'invalid_definition'),
    ('number', {'order':0}, 'invalid_definition'),
    ('number', {'required':'true'}, 'invalid_definition'),
    ('number', {'schema_version':9}, 'invalid_definition'),
])
def test_invalid_definitions(kind, patch, code):
    result = validate_question_definition({**question(kind), **patch})
    assert not result.valid
    assert code in [e.code for e in result.errors]
    assert all(e.field and e.message for e in result.errors)


@pytest.mark.parametrize('kind', ['single_choice','multiple_choice','text','number'])
@pytest.mark.parametrize('answer', [MISSING, None])
def test_required_missing(kind, answer):
    assert validate_answer(question(kind), answer).errors[0].code == 'required'
    assert validate_answer(question(kind, required=False), answer).valid


@pytest.mark.parametrize('kind,rules,answer,expected', [
    ('single_choice',{},'a',None),
    ('single_choice',{},'missing','invalid_option'),
    ('single_choice',{},['a'],'invalid_option'),
    ('single_choice',{},True,'invalid_option'),
    ('multiple_choice',{'min_selections':2,'max_selections':2},['a','b'],None),
    ('multiple_choice',{'min_selections':2},['a'],'min_selections'),
    ('multiple_choice',{'max_selections':1},['a','b'],'max_selections'),
    ('multiple_choice',{'exact_selections':2},['a'],'exact_selections'),
    ('multiple_choice',{},['a','a'],'duplicate_selection'),
    ('multiple_choice',{},['missing'],'invalid_option'),
    ('multiple_choice',{},'a','invalid_answer_type'),
    ('multiple_choice',{},[True],'invalid_answer_type'),
    ('multiple_choice',{},[{}],'invalid_answer_type'),
    ('text',{'min_length':2,'max_length':4},'中文',None),
    ('text',{'min_length':2},'a','min_length'),
    ('text',{'max_length':2},'abc','max_length'),
    ('text',{},12,'invalid_answer_type'),
    ('text',{},'  ','required'),
    ('number',{'min':0,'max':10},5,None),
    ('number',{'min':0},-1,'min'),
    ('number',{'max':10},11,'max'),
    ('number',{'integer_only':True},1.5,'integer_only'),
    ('number',{'integer_only':True},2.0,None),
    ('number',{},True,'invalid_number'),
    ('number',{},False,'invalid_number'),
    ('number',{},'1.5','invalid_number'),
    ('number',{},float('nan'),'invalid_number'),
    ('number',{},float('inf'),'invalid_number'),
    ('number',{},float('-inf'),'invalid_number'),
    ('number',{},2**63,'invalid_number'),
])
def test_answers(kind, rules, answer, expected):
    result = validate_answer(question(kind, rules=rules), answer)
    assert result.valid == (expected is None)
    if expected:
        assert result.errors[0].code == expected
        assert result.as_dict()['errors'][0]['message']


@pytest.mark.parametrize('kind,empty', [('single_choice',''),('multiple_choice',[]),('text','')])
def test_empty_answers(kind, empty):
    assert validate_answer(question(kind), empty).errors[0].code == 'required'
    assert validate_answer(question(kind, required=False), empty).valid


def test_optional_nonempty_answer_still_validates():
    q = question('text', rules={'min_length':2, 'max_length':3}, required=False)
    assert validate_answer(q, '').valid
    assert not validate_answer(q, 'a').valid
    assert not validate_answer(q, '    ').valid
    assert validate_answer(question('number', required=False), 0).valid


def test_engine_does_not_mutate_input_and_refuses_invalid_definition():
    q = question('text')
    before = deepcopy(q)
    assert validate_answer(q, 'hello').valid
    assert q == before
    q['validation'] = {'min_length':5, 'max_length':2}
    assert validate_answer(q, 'hello').errors[0].code == 'invalid_range'
