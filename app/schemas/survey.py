from datetime import datetime, timezone
from typing import Any, Literal
from app.schemas.question import QuestionDefinition
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

class SurveyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=5000)
    allow_anonymous: bool = False
    allow_multiple_submissions: bool = False
    deadline: AwareDatetime | None = None
    @field_validator('title')
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('标题不能为空')
        return value.strip()
    @field_validator('deadline')
    @classmethod
    def normalize_deadline(cls, value):
        return value.astimezone(timezone.utc) if value else None

class SurveyOut(SurveyInput):
    id: str
    owner_id: str
    status: Literal['draft', 'published', 'closed']
    public_token: str
    questions: list[QuestionDefinition]
    jump_rules: list[dict[str, Any]]
    question_bindings: list[dict[str, Any]] = Field(default_factory=list)
    revision_of: str | None = None
    revision_source_schema_version: int | None = None
    schema_version: int
    created_at: datetime
    updated_at: datetime

def survey_out(doc: dict) -> dict:
    from app.services.draft_bindings import binding_out
    fields = SurveyOut.model_fields.keys() - {'id', 'owner_id', 'question_bindings', 'revision_of', 'revision_source_schema_version'}
    return {**{k: doc[k] for k in fields}, 'id': str(doc['_id']), 'owner_id': str(doc['owner_id']),
            'question_bindings': [binding_out(b) for b in doc.get('question_bindings', [])],
            'revision_of': str(doc['revision_of']) if doc.get('revision_of') else None,
            'revision_source_schema_version': doc.get('revision_source_schema_version')}
