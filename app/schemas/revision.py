from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class RevisionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_schema_version: Annotated[StrictInt, Field(ge=1)]
    expected_schema_version: Annotated[StrictInt, Field(ge=1)]
