from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    @field_validator('username')
    @classmethod
    def clean_username(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('用户名不能为空')
        return value.strip()

class UserOut(BaseModel):
    id: str
    username: str
    created_at: datetime

def user_out(user: dict) -> dict:
    return {'id': str(user['_id']), 'username': user['username'], 'created_at': user['created_at']}
