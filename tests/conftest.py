import os
import uuid
import mongomock
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from app.core.config import Settings
from app.main import create_app

@pytest.fixture(params=['mock', pytest.param('mongo', marks=pytest.mark.integration)] if os.getenv('TEST_MONGODB_URI') else ['mock'])
def db(request):
    name = 'survey_test_' + uuid.uuid4().hex
    if request.param == 'mongo':
        client = MongoClient(os.environ['TEST_MONGODB_URI'], tz_aware=True, serverSelectionTimeoutMS=3000)
        client.admin.command('ping')
    else:
        client = mongomock.MongoClient(tz_aware=True)
    try:
        yield client[name]
    finally:
        # Only a newly generated test database is ever dropped.
        client.drop_database(name)
        client.close()

@pytest.fixture
def client(db):
    with TestClient(create_app(Settings(_env_file=None), database=db)) as c:
        yield c

@pytest.fixture
def logged(client):
    credentials={'username':'alice','password':'password123'}
    assert client.post('/api/auth/register',json=credentials).status_code == 201
    assert client.post('/api/auth/login',json=credentials).status_code == 200
    return client
