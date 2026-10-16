from typing import Any, Annotated
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr
from app.schemas.question import StableId


class JumpRuleDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StableId
    source_question_id: StableId
    operator: StrictStr
    value: Any
    target_question_id: StableId
    priority: Annotated[StrictInt, Field(ge=1, le=1000000)] = 1
