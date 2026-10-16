from datetime import datetime
from typing import Any, NotRequired, TypedDict
from bson import ObjectId

class ResponseDocument(TypedDict):
    _id: ObjectId
    survey_id: ObjectId
    respondent_user_id: ObjectId | None
    answers: list[dict[str, Any]]
    submitted_at: datetime
    survey_schema_version: int
    visited_question_ids: list[str]
    dedupe_key: NotRequired[str]
