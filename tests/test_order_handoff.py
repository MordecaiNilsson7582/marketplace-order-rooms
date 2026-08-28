import httpx
import pytest

from marketplace_rooms.infrai_realtime import InfraiRealtimeClient
from marketplace_rooms.order_handoff import (
    ParticipantRole,
    UpdateRequest,
    require_handoff_participants,
    validate_update,
)


def test_buyer_cannot_publish_seller_asset() -> None:
    update = UpdateRequest(
        order_id="ord-42",
        actor_id="buyer-9",
        role=ParticipantRole.BUYER,
        kind="seller_asset",
        message="Final files attached",
        asset_ref="asset-18",
        request_id="req-0009",
    )

    with pytest.raises(ValueError, match="seller role"):
        validate_update(update)


def test_handoff_requires_both_roles_present() -> None:
    presence = {"members": [{"client_id": "seller-2", "role": "seller"}]}

    with pytest.raises(ValueError, match="seller and buyer"):
        require_handoff_participants(presence, "seller-2")


def test_publish_retries_429_with_same_idempotency_key() -> None:
    seen_keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers["Idempotency-Key"])
        if len(seen_keys) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"ok": False, "error": {"code": "RATE_LIMITED"}})
        return httpx.Response(200, json={"ok": True, "data": {"event_id": "evt-1"}, "error": None, "metadata": {}})

    client = InfraiRealtimeClient("test-key", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    result = client.publish("marketplace-order-42", "buyer_update", {"message": "Reviewed"}, "buyer-9", "req-0009")
    client.close()

    assert result == {"event_id": "evt-1"}
    assert seen_keys == ["req-0009", "req-0009"]

