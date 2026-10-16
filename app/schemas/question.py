"""Transport/storage types; cross-field business rules live in validation.py."""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

StableId = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]


class Option(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StableId
    label: Annotated[StrictStr, Field(min_length=1, max_length=500)]


class QuestionDefinition(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: StableId
    type: Literal['single_choice', 'multiple_choice', 'text', 'number']
    title: Annotated[StrictStr, Field(min_length=1, max_length=500)]
    required: StrictBool = False
    order: Annotated[StrictInt, Field(ge=1)]
    options: list[Option] = Field(default_factory=list, max_length=100)
    validation: dict[str, Any] = Field(default_factory=dict)
