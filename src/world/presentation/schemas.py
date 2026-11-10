from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Hello(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["hello"]
    room: Literal["world", "lake", "halloween"] = "world"
    skin: Literal["angler", "girl", "girl_blue", "boy", "ghost", "ranger", "knight"] = "angler"


class Move(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["move"]
    seq: int = Field(ge=0, le=2**53 - 1)
    x: float = Field(ge=0, le=10000, allow_inf_nan=False)
    y: float = Field(ge=0, le=10000, allow_inf_nan=False)
    face: Literal[-1, 1] = 1
    direction: Literal["up", "down", "side"] = "down"
    skin: Literal["angler", "girl", "girl_blue", "boy", "ghost", "ranger", "knight"] = "angler"
    pose: Literal["idle", "walk", "rod"] = "idle"


class CastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    connection_id: UUID


class CatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cast_id: UUID
