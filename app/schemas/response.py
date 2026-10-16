from datetime import datetime
from typing import Annotated, Any
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from app.schemas.question import StableId

VersionNumber = Annotated[StrictInt, Field(ge=1, le=2**63-1)]


class AnswerInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question_id: StableId
    value: Any


class ResponseInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: VersionNumber
    answers: list[AnswerInput] = Field(max_length=200)


class NextInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: VersionNumber
    current_question_id: StableId
    answer: Any = None


class ResponseOut(BaseModel):
    id: str
    survey_id: str
    survey_schema_version: int
    visited_question_ids: list[str]
    submitted_at: datetime
