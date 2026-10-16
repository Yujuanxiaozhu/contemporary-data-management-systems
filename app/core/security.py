import hashlib
import secrets
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from app.core.database import get_db
password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def current_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get(request.app.state.settings.cookie_name)
    if token:
        session = db.sessions.find_one({'token_hash': token_hash(token),
                                       'expires_at': {'$gt': utcnow()}})
        if session:
            user = db.users.find_one({'_id': session['user_id']})
            if user:
                return user
    raise HTTPException(401, '请先登录')

def require_same_origin(request: Request):
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return
    # Reject cross-site browser writes, including login CSRF.
    origin = request.headers.get('origin')
    if (origin and origin != str(request.base_url).rstrip('/')) or request.headers.get('sec-fetch-site') == 'cross-site':
        raise HTTPException(403, '不允许跨站请求')


def optional_user(request: Request, db=Depends(get_db)):
    try:
        return current_user(request, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise
