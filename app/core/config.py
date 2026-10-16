from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
ROOT = Path(__file__).resolve().parents[2]
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    mongodb_uri: str = 'mongodb://127.0.0.1:27017'
    mongodb_database: str = 'survey_system'
    session_ttl_seconds: int = Field(default=86400, ge=60)
    cookie_secure: bool = False
    cookie_name: str = 'survey_session'
