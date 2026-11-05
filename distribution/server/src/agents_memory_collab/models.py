from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
)

Label = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[^\x00-\x1f\x7f]+$")]
Text = Annotated[str, Field(min_length=1, max_length=32_000, pattern=r"^[^\x00]*$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Operation(Model):
    op_id: UUID
    memory_id: UUID
    project: Label
    kind: Literal["memory", "summary", "prompt"] = "memory"
    base_revision: Annotated[StrictInt, Field(ge=0)] = 0
    deleted: StrictBool = False
    text: Text | None = None
    session_id: Label | None = None
    source_id: Label | None = None
    # Set only by the local hook path for the user's own typed prompt; MCP tools reject it.
    origin: Literal["user_prompt"] | None = None

    @field_validator("text")
    @classmethod
    def bounded_source(cls, value):
        if value is not None and len(value.encode("utf-8")) > 32_000:
            raise ValueError("Source exceeds the 32000-byte processing budget")
        return value


def tool_operation(args: dict) -> Operation:
    """Model-supplied tool arguments never attest a user-prompt origin."""
    if "origin" in args:
        raise Failure(400, "origin_not_accepted_from_tools")
    # Strict models accept UUID strings only through JSON validation, as the edges do.
    return Operation.model_validate_json(json.dumps(args, default=str, allow_nan=False))


def tool_operation_schema() -> dict:
    schema = Operation.model_json_schema()
    schema["properties"].pop("origin")
    return schema


class Checkpoint(Model):
    epoch: UUID
    cursor: Annotated[StrictInt, Field(ge=0)]
    chain_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Push(Model):
    operations: Annotated[list[Operation], Field(min_length=1, max_length=100)]
    checkpoint: Checkpoint | None = None


class Search(Model):
    query: Annotated[str, Field(min_length=1, max_length=1000)]
    project: Label | None = None
    limit: Annotated[StrictInt, Field(ge=1, le=50)] = 10


class Named(Model):
    name: Label


class Invite(Model):
    role: Literal["member", "viewer"] = "member"
    projects: Annotated[list[UUID], Field(min_length=1, max_length=100)]
    expires_hours: Annotated[StrictInt, Field(ge=1, le=168)] = 24


class AcceptInvite(Model):
    invite: Annotated[str, Field(min_length=40, max_length=100)]


class ShareMapping(Model):
    source_project: Label
    project_id: UUID


class Sharing(Model):
    mappings: Annotated[list[ShareMapping], Field(max_length=100)]


class Preferences(Model):
    upload_prompts: StrictBool


class Device(Model):
    name: Label
    writable: StrictBool = True


class Failure(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code
        super().__init__(code)
