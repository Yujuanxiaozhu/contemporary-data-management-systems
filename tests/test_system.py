from datetime import timedelta
import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.security import utcnow, verify_password

def make(client, **fields):
    response=client.post('/api/surveys',json={'title':'测试问卷', **fields})
    assert response.status_code == 201
    return response.json()

def test_register(client, db):
    response=client.post('/api/auth/register',json={'username':'alice','password':'password123'})
    assert response.status_code == 201
    assert ObjectId.is_valid(response.json()['id'])
    user=db.users.find_one({'username':'alice'})
    assert user['password_hash'].startswith('$argon2id$')
    assert verify_password('password123',user['password_hash'])
    assert 'password_hash' not in response.json()

def test_duplicate(client):
    data={'username':'alice','password':'password123'}
    assert client.post('/api/auth/register',json=data).status_code == 201
    assert client.post('/api/auth/register',json=data).status_code == 409

@pytest.mark.parametrize('data',[{'username':'   ','password':'password123'},{'username':'a','password':'short'}])
def test_bad_registration(client,data):
    assert client.post('/api/auth/register',json=data).status_code == 422

def test_login_and_me(logged):
    assert logged.get('/api/auth/me').json()['username'] == 'alice'
    cookie=logged.cookies.get('survey_session')
    assert cookie and len(cookie)>=43

@pytest.mark.parametrize('username',['alice','missing'])
def test_wrong_login(logged,username):
    response=logged.post('/api/auth/login',json={'username':username,'password':'wrongpass'})
    assert response.status_code == 401
    assert response.json()['detail'] == '用户名或密码错误'

@pytest.mark.parametrize('method,path,data',[
 ('GET','/api/auth/me',None),('GET','/api/surveys',None),('POST','/api/surveys',{'title':'a'}),
 ('GET','/api/surveys/012345678901234567890123',None),
 ('PUT','/api/surveys/012345678901234567890123',{'title':'a'}),
 ('DELETE','/api/surveys/012345678901234567890123',None),
 ('POST','/api/surveys/012345678901234567890123/publish',None),
 ('POST','/api/surveys/012345678901234567890123/close',None)])
def test_unauthenticated(client,method,path,data):
    assert client.request(method,path,json=data).status_code == 401

def test_create_serialization(logged,db):
    survey=make(logged,deadline='2030-01-01T08:00:00+08:00')
    assert survey['status']=='draft'
    assert survey['questions']==survey['jump_rules']==[]
    assert ObjectId.is_valid(survey['id']) and ObjectId.is_valid(survey['owner_id'])
    assert survey['deadline']=='2030-01-01T00:00:00Z'
    assert survey['created_at'].endswith('Z')
    assert isinstance(db.surveys.find_one()['_id'],ObjectId)
    assert len(survey['public_token'])>=43

def test_update_delete(logged):
    survey=make(logged)
    path='/api/surveys/'+survey['id']
    assert logged.put(path,json={'title':'新标题'}).json()['title']=='新标题'
    assert logged.delete(path).status_code==204
    assert logged.get(path).status_code==404

def test_owner_isolation(logged):
    other=make(logged)
    logged.post('/api/auth/register',json={'username':'bob','password':'password123'})
    logged.post('/api/auth/login',json={'username':'bob','password':'password123'})
    mine=make(logged)
    assert [s['id'] for s in logged.get('/api/surveys').json()]==[mine['id']]
    path='/api/surveys/'+other['id']
    for method,suffix,data in [('GET','',None),('PUT','',{'title':'attack'}),('DELETE','',None),('POST','/publish',None),('POST','/close',None)]:
        assert logged.request(method,path+suffix,json=data).status_code==404

def test_publish_close(logged):
    path='/api/surveys/'+make(logged)['id']
    assert logged.post(path+'/close').status_code==409
    assert logged.post(path+'/publish').json()['status']=='published'
    assert logged.post(path+'/publish').status_code==200
    assert logged.post(path+'/close').json()['status']=='closed'
    assert logged.post(path+'/close').status_code==200
    assert logged.post(path+'/publish').status_code==409

@pytest.mark.parametrize('sid',['invalid','a'*23,'z'*24])
def test_invalid_id(logged,sid):
    path='/api/surveys/'+sid
    for method,suffix,data in [('GET','',None),('PUT','',{'title':'a'}),('DELETE','',None),('POST','/publish',None),('POST','/close',None)]:
        assert logged.request(method,path+suffix,json=data).status_code==422

def test_missing_id(logged):
    assert logged.get('/api/surveys/'+str(ObjectId())).status_code==404

def test_logout_revokes(logged,db):
    token=logged.cookies.get('survey_session')
    assert logged.post('/api/auth/logout').status_code==204
    logged.cookies.set('survey_session',token)
    assert logged.get('/api/surveys').status_code==401
    assert db.sessions.count_documents({})==0

def test_expired_session(logged,db):
    db.sessions.update_many({}, {'$set':{'expires_at':utcnow()-timedelta(seconds=1)}})
    assert logged.get('/api/auth/me').status_code==401

def test_cookie_and_rotation(logged,db):
    response=logged.post('/api/auth/login',json={'username':'alice','password':'password123'})
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert db.sessions.count_documents({})==1
    assert 'token' not in db.sessions.find_one()

def test_cross_origin(logged):
    assert logged.post('/api/surveys',json={'title':'x'},headers={'Origin':'https://evil.example'}).status_code==403
    assert logged.post('/api/auth/login',json={'username':'alice','password':'password123'},headers={'Origin':'https://evil.example'}).status_code==403

@pytest.mark.parametrize('data',[{'title':' '},{'title':'x','owner_id':'bad'},{'title':'x','status':'published'},{'title':'x','questions':[{}]},{'title':'x','deadline':'2030-01-01T00:00:00'}])
def test_invalid_survey_input(logged,data):
    assert logged.post('/api/surveys',json=data).status_code==422

def test_indexes(logged,db):
    first=make(logged)
    with pytest.raises(DuplicateKeyError):
        db.surveys.insert_one({'public_token':first['public_token']})
    assert db.users.index_information()['username_1']['unique']
    assert 'owner_id_1_created_at_1' in db.surveys.index_information()
    assert 'survey_id_1' in db.responses.index_information()
    assert db.sessions.index_information()['expires_at_1']['expireAfterSeconds']==0

def test_token_collision_retry(logged,monkeypatch):
    from app.models import survey
    first=make(logged)
    tokens=iter([first['public_token'],'new-distinct-token'])
    monkeypatch.setattr(survey.secrets,'token_urlsafe',lambda _:next(tokens))
    assert make(logged)['public_token']=='new-distinct-token'

def test_home_and_health(client):
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert client.get('/health').json()=={'status':'ok'}
