from copy import deepcopy
import pytest
from app.services.jump_rules import validate_jump_rules
from app.services.jump_engine import resolve_next_question, validate_response_path


def definition(kind='single_choice'):
    questions=[]
    for i in range(1,5):
        q={'id':f'q{i}','type':kind if i==1 else 'text','title':f'Q{i}','required':False,'order':i,'options':[],'validation':{}}
        if i==1 and 'choice' in kind:
            q['options']=[{'id':'a','label':'A'},{'id':'b','label':'B'}]
        questions.append(q)
    return {'questions':questions,'jump_rules':[]}


def rule(**fields):
    return {'id':'r1','source_question_id':'q1','operator':'equals','value':'a','target_question_id':'q3','priority':1,**fields}


@pytest.mark.parametrize('kind,op,value', [('single_choice','equals','a'),('multiple_choice','contains','a'),
 ('number','equals',2),('number','greater_than',2),('number','greater_than_or_equal',2),('number','less_than',2),('number','less_than_or_equal',2)])
def test_valid_rules(kind,op,value):
    d=definition(kind)
    assert validate_jump_rules(d['questions'],[rule(operator=op,value=value)]).valid


@pytest.mark.parametrize('kind,patch,code',[
 ('single_choice',{'operator':'contains'},'invalid_operator'),
 ('single_choice',{'operator':'unknown'},'invalid_operator'),
 ('single_choice',{'value':'missing'},'invalid_rule_value'),
 ('multiple_choice',{'operator':'contains','value':['a']},'invalid_rule_value'),
 ('number',{'operator':'greater_than','value':True},'invalid_rule_value'),
 ('number',{'value':float('nan')},'invalid_rule_value'),
 ('number',{'value':float('inf')},'invalid_rule_value'),
 ('number',{'value':float('-inf')},'invalid_rule_value'),
 ('number',{'value':2**63},'invalid_rule_value'),
 ('number',{'value':'2'},'invalid_rule_value'),
 ('text',{},'invalid_operator'),
 ('single_choice',{'source_question_id':'missing'},'missing_question'),
 ('single_choice',{'target_question_id':'missing'},'missing_question'),
 ('single_choice',{'target_question_id':'q1'},'not_forward'),
 ('single_choice',{'source_question_id':'q3','target_question_id':'q2'},'not_forward'),
 ('single_choice',{'priority':True},'invalid_rule'),
 ('single_choice',{'priority':0},'invalid_rule'),
])
def test_invalid_rules(kind,patch,code):
    result=validate_jump_rules(definition(kind)['questions'],[rule(**patch)])
    assert not result.valid and code in [e.code for e in result.errors]


@pytest.mark.parametrize('second,code',[(rule(priority=2),'duplicate_rule_id'),(rule(id='r2'),'duplicate_priority')])
def test_duplicate_rules_and_priority(second,code):
    result=validate_jump_rules(definition()['questions'],[rule(),second])
    assert code in [e.code for e in result.errors]


@pytest.mark.parametrize('kind,op,value,answer,expected',[
 ('single_choice','equals','a','a','q3'),('single_choice','equals','a','b','q2'),
 ('multiple_choice','contains','a',['a','b'],'q3'),('multiple_choice','contains','a',['b'],'q2'),
 ('number','greater_than',2,3,'q3'),('number','greater_than',2,2,'q2'),
 ('number','greater_than_or_equal',2,2,'q3'),('number','less_than',2,1,'q3'),
 ('number','less_than_or_equal',2,2,'q3'),('number','equals',2,2,'q3')])
def test_resolve(kind,op,value,answer,expected):
    d=definition(kind); d['jump_rules']=[rule(operator=op,value=value)]
    assert resolve_next_question(d,'q1',answer)==expected


def test_sequential_last_and_priority():
    d=definition()
    assert resolve_next_question(d,'q1','a')=='q2'
    assert resolve_next_question(d,'q4') is None
    d['jump_rules']=[rule(id='late',priority=2,target_question_id='q4'),rule(id='early',priority=1)]
    assert resolve_next_question(d,'q1','a')=='q3'
    d['jump_rules'].reverse()
    assert resolve_next_question(d,'q1','a')=='q3'


def test_path_required_skipped_extra_and_optional():
    d=definition();d['questions'][1]['required']=True;d['jump_rules']=[rule()]
    good=validate_response_path(d,{'q1':'a'})
    assert good.valid and good.visited_question_ids==['q1','q3','q4']
    assert not validate_response_path(d,{'q1':'a','q2':'污染'}).valid
    assert not validate_response_path(d,{'q1':'b'}).valid
    assert not validate_response_path(d,{'q1':'a','unknown':1}).valid


def test_runtime_cycle_and_max_steps():
    d=definition();d['questions'][2]['type']='single_choice';d['questions'][2]['options']=deepcopy(d['questions'][0]['options'])
    d['jump_rules']=[rule(),rule(id='bad',source_question_id='q3',target_question_id='q1')]
    assert validate_response_path(d,{'q1':'a','q3':'a'}).errors[0].code=='unsafe_path'
    assert validate_response_path(definition(),{'q1':'a'},max_steps=1).errors[0].code=='unsafe_path'
