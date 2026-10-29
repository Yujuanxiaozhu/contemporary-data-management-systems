from datetime import timezone
from fastapi import Request
from pymongo import MongoClient

def connect(settings):
    client = MongoClient(settings.mongodb_uri, tz_aware=True, tzinfo=timezone.utc,
                         serverSelectionTimeoutMS=5000)
    try:
        client.admin.command('ping')
    except Exception:
        client.close()
        raise
    return client

def ensure_indexes(db):
    db.users.create_index('username', unique=True)
    db.surveys.create_index('public_token', unique=True)
    db.surveys.create_index([('owner_id', 1), ('created_at', 1)])
    db.responses.create_index('survey_id')
    db.responses.create_index([('survey_id', 1), ('survey_schema_version', 1)])
    db.responses.create_index('dedupe_key', unique=True, sparse=True)
    db.survey_versions.create_index([('survey_id', 1), ('schema_version', 1)], unique=True)
    db.sessions.create_index('token_hash', unique=True)
    db.sessions.create_index('expires_at', expireAfterSeconds=0)

def ensure_question_indexes(db):
    # Lazy initialization: legacy survey-only use does not create new collections.
    db.questions.create_index([('owner_id', 1), ('status', 1), ('_id', 1)])
    db.question_versions.create_index([('question_id', 1), ('version_no', 1)], unique=True)
    db.question_versions.create_index('operation_id', unique=True)
    db.stage2_operations.create_index([('owner_id', 1), ('action', 1), ('key', 1)], unique=True)
    db.stage2_operations.create_index([('question_id', 1), ('state', 1)])

def get_db(request: Request):
    return request.app.state.db
