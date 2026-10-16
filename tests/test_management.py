import pytest
from test_public_responses import setup_survey, payload, url


@pytest.mark.parametrize('path',['/','/login','/register'])
def test_public_account_pages(client,path):
    response=client.get(path)
    assert response.status_code==200 and '<html' in response.text and '/static/management.js' in response.text


@pytest.mark.parametrize('path',['/dashboard','/surveys/new','/surveys/012345678901234567890123/edit','/surveys/012345678901234567890123/stats'])
def test_management_requires_login(client,path):
    response=client.get(path,follow_redirects=False)
    assert response.status_code==303 and response.headers['location']=='/login'


def test_dashboard_isolation_and_owner_pages(logged):
    s=setup_survey(logged)
    dashboard=logged.get('/dashboard')
    assert dashboard.status_code==200 and s['id'] in dashboard.text
    assert '/survey/'+s['public_token'] in dashboard.text
    assert 'schema_version' not in dashboard.text or str(s['schema_version']) in dashboard.text
    assert logged.get('/surveys/new').status_code==200
    edit=logged.get('/surveys/'+s['id']+'/edit')
    assert edit.status_code==200 and 'question-form' in edit.text and 'rule-form' in edit.text
    assert logged.get('/surveys/'+s['id']+'/stats').status_code==200
    logged.post('/api/auth/register',json={'username':'other','password':'password123'})
    logged.post('/api/auth/login',json={'username':'other','password':'password123'})
    assert s['id'] not in logged.get('/dashboard').text
    for suffix in ['/edit','/stats','/questions/q1/stats']:
        assert logged.get('/surveys/'+s['id']+suffix).status_code==404


def test_statistics_page_escapes_response_text(logged):
    s=setup_survey(logged)
    evil='<script>alert(1)</script>'
    assert logged.post(url(s)+'/responses',json=payload(s,q1='b',q2=evil)).status_code==201
    page=logged.get('/surveys/'+s['id']+'/stats')
    assert page.status_code==200,page.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page.text and evil not in page.text
    assert 'Schema 版本' in page.text and '平均值' in page.text
    assert logged.get('/surveys/'+s['id']+'/questions/q2/stats').status_code==200


def test_edit_data_and_dashboard_escape_html(logged):
    s=logged.post('/api/surveys',json={'title':'<img src=x onerror=alert(1)>'}).json()
    assert '<img src=x onerror=alert(1)>' not in logged.get('/dashboard').text
    page=logged.get('/surveys/'+s['id']+'/edit')
    assert page.status_code==200 and 'survey-data' in page.text
    assert '<img src=x onerror=alert(1)>' not in page.text


def test_closed_ui_readonly_and_same_origin(logged):
    s=setup_survey(logged);logged.post('/api/surveys/'+s['id']+'/close')
    edit=logged.get('/surveys/'+s['id']+'/edit')
    assert edit.status_code==200 and 'id="question-form"' not in edit.text and 'id="rule-form"' not in edit.text
    assert logged.post('/api/surveys',json={'title':'attack'},headers={'Origin':'https://evil.example'}).status_code==403
