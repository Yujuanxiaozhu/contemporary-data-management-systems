"""S1-03 pure checks independent of MongoDB."""
import pytest
from fastapi import HTTPException

from app.services.question_bank import canonical, digest, normalize


def test_canonical_hash_ignores_dictionary_order():
    assert digest({'b': 1, 'a': {'y': 2, 'x': 3}}) == digest({'a': {'x': 3, 'y': 2}, 'b': 1})
    assert canonical({'标题': '年龄', 'a': 1}) == '{"a":1,"标题":"年龄"}'
    assert digest({'a': [1, 2]}) != digest({'a': [2, 1]})
    assert digest({'a': 1}) != digest({'a': 1.0})


def test_normalized_default_and_whitespace():
    assert normalize({'type': 'text', 'title': ' 测试 '}) == {
        'type': 'text', 'title': '测试', 'required': False, 'options': [], 'validation': {}}


@pytest.mark.parametrize('patch', [
    {'id': 'local'}, {'order': 1}, {'owner_id': 'attacker'}, {'required': 1},
    {'type': 'number', 'validation': {'min': float('nan')}},
    {'type': 'number', 'validation': {'max': float('inf')}},
    {'validation': {'unknown': 1}}, {'title': '  '},
])
def test_invalid_standalone_definition(patch):
    with pytest.raises(HTTPException) as exc:
        normalize({'type': 'text', 'title': '测试', **patch})
    assert exc.value.status_code == 422


def test_non_finite_hash_rejected():
    with pytest.raises(ValueError):
        digest({'a': float('nan')})
