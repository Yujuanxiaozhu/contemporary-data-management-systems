"""Standalone definitions deliberately exclude survey-local id/order."""
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class CreateQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    definition: dict[str, Any]


class CreateVersion(CreateQuestion):
    parent_version_id: str
    expected_revision: Annotated[StrictInt, Field(ge=1)]


class RestoreVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_version_id: str
    expected_revision: Annotated[StrictInt, Field(ge=1)]


class RepairLatest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: Annotated[StrictInt, Field(ge=1)]


class ShareByUsername(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)


class ShareUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: Annotated[StrictInt | None, Field(ge=1)] = None


class ForkVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    definition: dict[str, Any] | None = None
