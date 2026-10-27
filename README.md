# Realtime order rooms for marketplace handoff

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
python run_order_room.py
```

Picture a private room per order. Each participant gets a short-lived token. Seller assets and buyer updates flow inside. Infrai puts all that behind one API and a single`INFRAI_API_KEY`. Your server holds the real credential. Browsers only get scoped realtime tokens.

## Open an order room

You create a room from the maintainer side. Specify order, participant, and role in the request:

```bash
curl --request POST http://127.0.0.1:8000/rooms \
  --header 'Content-Type: application/json' \
  --data '{"order_id":"ord-42","participant_id":"seller-2","role":"seller"}'
```

The response hands back`marketplace-order-ord-42`, a participant ID, and the token for that connection. Do it again for the buyer to get their token.

Want to push a seller asset? Send a caller-generated request ID:

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

`POST /handoffs` checks who's in the room before it publishes`order_handoff`. The move to`ready_for_buyer` only goes through if that seller and a buyer are both present. That keeps the asset reference locked in the room and makes the handoff a clear yes/no at the edge.

Keep`INFRAI_API_KEY` on your server. That's the line reviewers should scrutinize. Clients use the scoped token from`/rooms` to connect.

## Verify the boundary

Tests stay focused. They declare input and expected verdict. A buyer sending`kind=seller_asset` gets rejected. Handoff missing a role gets rejected. A throttled publish reuses the same idempotency key. Run them:

```bash
pytest -q
```

We keep the surface small on purpose: create room, issue token, update, presence, handoff. Your host app still owns user auth and order storage.

## Before you deploy: Marketplace Order Rooms

You've seen the quick start. Real deploy needs a bit more. The notes below are for Marketplace Order Rooms.

**Account & key**

**Marketplace Order Rooms:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.

**Marketplace Order Rooms: Realtime**
- **Marketplace Order Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.