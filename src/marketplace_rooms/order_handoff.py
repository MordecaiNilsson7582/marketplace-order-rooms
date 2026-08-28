from __future__ import annotations

import os
from enum import StrEnum
from typing import Any, Literal
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_realtime import InfraiError, InfraiRealtimeClient


class ParticipantRole(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"


class RoomRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    participant_id: str = Field(min_length=1, max_length=80)
    role: ParticipantRole


class UpdateRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    actor_id: str = Field(min_length=1, max_length=80)
    role: ParticipantRole
    kind: Literal["seller_asset", "buyer_update"]
    message: str = Field(min_length=1, max_length=500)
    asset_ref: str | None = Field(default=None, max_length=200)
    request_id: str = Field(min_length=8, max_length=120)


class HandoffRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=80)
    seller_id: str = Field(min_length=1, max_length=80)
    asset_ref: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=8, max_length=120)


def channel_for(order_id: str) -> str:
    return f"marketplace-order-{order_id}"


def validate_update(update: UpdateRequest) -> None:
    if update.kind == "seller_asset" and update.role != ParticipantRole.SELLER:
        raise ValueError("seller_asset requires the seller role")
    if update.kind == "buyer_update" and update.role != ParticipantRole.BUYER:
        raise ValueError("buyer_update requires the buyer role")
    if update.kind == "seller_asset" and not update.asset_ref:
        raise ValueError("seller_asset requires an asset_ref")


def require_handoff_participants(presence: dict[str, Any], seller_id: str) -> None:
    members = presence.get("members", [])
    ids = {member.get("client_id") for member in members}
    roles = {member.get("role") for member in members}
    if seller_id not in ids or not {"seller", "buyer"}.issubset(roles):
        raise ValueError("handoff requires the seller and buyer in the room")


def get_client() -> InfraiRealtimeClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("INFRAI_API_KEY is required")
    return InfraiRealtimeClient(api_key)


app = FastAPI(title="Marketplace order rooms")


def client_error(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": error.code, "message": str(error)})


@app.post("/rooms", status_code=201)
def open_room(request: RoomRequest, client: InfraiRealtimeClient = Depends(get_client)) -> dict[str, Any]:
    channel = channel_for(request.order_id)
    try:
        client.create_channel(channel, f"room:{request.order_id}")
        token = client.issue_token(
            request.participant_id,
            channel,
            f"token:{request.order_id}:{request.participant_id}",
        )
    except InfraiError as error:
        raise client_error(error) from error
    return {"channel": channel, "participant_id": request.participant_id, "token": token}


@app.post("/updates", status_code=202)
def publish_update(request: UpdateRequest, client: InfraiRealtimeClient = Depends(get_client)) -> dict[str, str]:
    try:
        validate_update(request)
        client.publish(
            channel_for(request.order_id),
            request.kind,
            {"message": request.message, "asset_ref": request.asset_ref},
            request.actor_id,
            request.request_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except InfraiError as error:
        raise client_error(error) from error
    return {"status": "published", "event": request.kind}


@app.post("/handoffs", status_code=202)
def handoff_order(request: HandoffRequest, client: InfraiRealtimeClient = Depends(get_client)) -> dict[str, str]:
    channel = channel_for(request.order_id)
    try:
        require_handoff_participants(client.presence(channel), request.seller_id)
        client.publish(
            channel,
            "order_handoff",
            {"asset_ref": request.asset_ref, "state": "ready_for_buyer"},
            request.seller_id,
            request.request_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except InfraiError as error:
        raise client_error(error) from error
    return {"status": "published", "state": "ready_for_buyer"}
