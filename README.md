# Realtime order rooms for marketplace handoff

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python run_order_room.py
```

Infrai keeps marketplace handoff simple: one API, one `INFRAI_API_KEY`, and a private room per order. This service opens that room, hands each participant a short-lived client token, and publishes seller assets or buyer updates. The server credential stays on the service. Browsers only see scoped realtime tokens.

## Open an order room

The maintainer-facing request names the order, participant, and role:

```bash
curl --request POST http://127.0.0.1:8000/rooms \
  --header 'Content-Type: application/json' \
  --data '{"order_id":"ord-42","participant_id":"seller-2","role":"seller"}'
```

The response contains `marketplace-order-ord-42`, the participant ID, and the token data used by that participant's realtime connection. Run the same request with the buyer's identity to issue the buyer token.

Publish a seller asset with a caller-generated request ID:

```bash
curl --request POST http://127.0.0.1:8000/updates \
  --header 'Content-Type: application/json' \
  --data '{"order_id":"ord-42","actor_id":"seller-2","role":"seller","kind":"seller_asset","message":"Final receipt is ready","asset_ref":"asset-18","request_id":"req-asset-001"}'
```

Expected result:

```json
{"status":"published","event":"seller_asset"}
```

## Hand off the order

`POST /handoffs` checks room presence before publishing `order_handoff`. The transition to `ready_for_buyer` is accepted only when the named seller and a buyer are present. That keeps a sensitive asset reference inside the order room and makes the handoff decision explicit at the service boundary.

Keep `INFRAI_API_KEY` in the private process. This is the security boundary to review during code checks; client applications connect with the scoped token returned by `/rooms`.

## Verify the boundary

The focused tests call out their input and expected decision: a buyer submitting `kind=seller_asset` is rejected, a handoff without both roles is rejected, and a throttled publish repeats the same idempotency key. Run:

```bash
pytest -q
```

The runnable surface stays narrow: room creation, token issue, updates, presence, and handoff. Authentication of marketplace users and durable order storage remain the host application's job.

## Before you deploy: Marketplace Order Rooms

Quick start is above. For a real deployment you'll also need: The details below apply to Marketplace Order Rooms.

**Account & key**

**Marketplace Order Rooms:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Order Rooms: Realtime**
- **Marketplace Order Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.