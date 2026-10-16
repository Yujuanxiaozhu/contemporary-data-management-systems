"""Run a real Uvicorn process against a disposable MongoDB database."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
import httpx
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]

def main(extension=None, log_name='startup-server.txt'):
    name = 'survey_test_smoke_' + uuid.uuid4().hex
    uri = os.environ.get('TEST_MONGODB_URI', 'mongodb://127.0.0.1:27017')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'MONGODB_URI': uri, 'MONGODB_DATABASE': name, 'PYTHONIOENCODING': 'utf-8'}
    with (ROOT/'docs'/log_name).open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10, trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError('Uvicorn exited before startup; see startup-server.txt')
                    try:
                        response = client.get('/health', timeout=httpx.Timeout(2, connect=0.3))
                        if response.status_code == 200:
                            break
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        time.sleep(0.1)
                else:
                    raise RuntimeError('Startup timeout')
                def check(method, path, expected, data=None):
                    response = client.request(method, path, json=data)
                    print(f'{method} {path}: {response.status_code}')
                    assert response.status_code == expected, response.text
                    return response
                check('GET','/',200)
                check('GET','/health',200)
                check('GET','/static/app.js',200)
                check('GET','/openapi.json',200)
                credentials={'username':'smoke','password':'password123'}
                check('POST','/api/auth/register',201,credentials)
                check('POST','/api/auth/login',200,credentials)
                survey=check('POST','/api/surveys',201,{'title':'启动验证'}).json()
                if extension is not None:
                    extension(client, check, survey, uri, name)
                check('POST',f"/api/surveys/{survey['id']}/publish",200)
                check('POST',f"/api/surveys/{survey['id']}/close",200)
                check('POST','/api/auth/logout',204)
                check('GET','/api/surveys',401)
                print('REAL_UVICORN_SMOKE=PASS')
        finally:
            process.terminate()
            process.wait(timeout=10)
            with MongoClient(uri, serverSelectionTimeoutMS=3000) as mongo:
                assert name.startswith('survey_test_smoke_')
                mongo.drop_database(name)
            print('Temporary server stopped; disposable test database removed.')

if __name__ == '__main__':
    main()
