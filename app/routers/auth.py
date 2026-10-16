import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from app.core.database import get_db
from app.core.security import DUMMY_HASH, current_user, require_same_origin, token_hash, utcnow, verify_password
from app.models.user import new_user
from app.schemas.auth import Credentials, UserOut, user_out
router = APIRouter(prefix='/api/auth', tags=['auth'], dependencies=[Depends(require_same_origin)])

@router.post('/register', status_code=201, response_model=UserOut)
def register(data: Credentials, db=Depends(get_db)):
    user = new_user(data.username, data.password)
    try:
        user['_id'] = db.users.insert_one(user).inserted_id
    except DuplicateKeyError:
        raise HTTPException(409, '用户名已存在') from None
    return user_out(user)

@router.post('/login', response_model=UserOut)
def login(data: Credentials, request: Request, response: Response, db=Depends(get_db)):
    user = db.users.find_one({'username': data.username})
    valid = verify_password(data.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, '用户名或密码错误')
    settings = request.app.state.settings
    old = request.cookies.get(settings.cookie_name)
    if old:
        db.sessions.delete_one({'token_hash': token_hash(old)})
    token = secrets.token_urlsafe(32)
    db.sessions.insert_one({'token_hash': token_hash(token), 'user_id': user['_id'],
                           'created_at': utcnow(), 'expires_at': utcnow() + timedelta(seconds=settings.session_ttl_seconds)})
    response.set_cookie(settings.cookie_name, token, httponly=True, secure=settings.cookie_secure,
                        samesite='strict', max_age=settings.session_ttl_seconds, path='/')
    return user_out(user)

@router.post('/logout', status_code=204)
def logout(request: Request, db=Depends(get_db)):
    settings = request.app.state.settings
    token = request.cookies.get(settings.cookie_name)
    if token:
        db.sessions.delete_one({'token_hash': token_hash(token)})
    response = Response(status_code=204)
    response.delete_cookie(settings.cookie_name, path='/', secure=settings.cookie_secure, httponly=True, samesite='strict')
    return response

@router.get('/me', response_model=UserOut)
def me(user=Depends(current_user)):
    return user_out(user)
