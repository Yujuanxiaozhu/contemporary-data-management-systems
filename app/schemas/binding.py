from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class BindingInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question_version_id: StrictStr
    required_override: StrictBool | None = None
    expected_schema_version: Annotated[StrictInt, Field(ge=1)]


class ReferenceInput(BindingInput):
    order: Annotated[StrictInt, Field(ge=1)] | None = None
