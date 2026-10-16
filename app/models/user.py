from app.core.security import hash_password, utcnow

def new_user(username: str, password: str) -> dict:
    return {'username': username, 'password_hash': hash_password(password), 'created_at': utcnow()}
