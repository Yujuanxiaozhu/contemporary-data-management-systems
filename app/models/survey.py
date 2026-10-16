import secrets
from app.core.security import utcnow

def new_survey(owner_id, fields: dict) -> dict:
    now = utcnow()
    return {**fields, 'owner_id': owner_id, 'status': 'draft',
            'public_token': secrets.token_urlsafe(32), 'questions': [], 'jump_rules': [],
            'schema_version': 1, 'created_at': now, 'updated_at': now}
