---
name: stank-ws-protocol
description: WebSocket message type constants (frontend MsgType enum vs backend MSG_TYPE_* in ws.py) must stay in sync. Trigger when editing src/stankbot/web/ws.py, src/stankbot/web/frontend/src/lib/ws.ts, or src/stankbot/web/frontend/src/lib/ws.test.ts.
---

# stank-bot WebSocket message type protocol

The frontend `MsgType` enum in `ws.ts` and the backend `MSG_TYPE_*` constants in `ws.py` define the same numeric values for every message sent over the WebSocket. Translations happen in `ws.ts` (`handleMessage` switch) and `ws.py` (the `msg_type == MSG_TYPE_PING` .. `MSG_TYPE_VERSION_RESPONSE` handler).

## Rules

1. **Every numeric type in the enum MUST have a matching constant on the backend.**
   - Frontend: `src/stankbot/web/frontend/src/lib/ws.ts` — `MsgType` enum.
   - Backend: `src/stankbot/web/ws.py` — top-level `MSG_TYPE_*` module constants.

2. **If you insert a new message type ID in the middle of the enum, you MUST shift all subsequent types.** Inserting does not just append — it renumbers everything after it. The original VERSION_MISMATCH bug (108 → 109) happened precisely because `GAME_EVENT = 107` was inserted between SESSION (106) and ERROR (107), shifting ERROR→108 and VERSION_MISMATCH→109, but the backend never got the memo.

3. **When adding a new message type, update ALL of these:**
   - `ws.ts` — `MsgType` enum + interface + `ServerMsg` union + `handleMessage` case.
   - `ws.py` — `MSG_TYPE_*` constant + handler or `broadcast_json` call.
   - `ws.test.ts` — `it('should have correct server message types')` block.
   - `test_ws.py` — `TestMessageTypes.test_msgtype_values` + relevant broadcast test.
   - `board.spec.ts` or `events.spec.ts` — if the new type has a visible effect, add an E2E case for it.

4. **No hardcoded numbers.** Backend broadcast helpers must use the named constants (`MSG_TYPE_CHAIN_UPDATE`, not `103`). Frontend message handling must use the enum (`MsgType.CHAIN_UPDATE`, not `103`).

5. **When intercepting WS frames in Playwright E2E tests,** use `ws.on('framereceived', handler)` — not `ws.on('frames')`. The latter receives a batch array; `framereceived` fires for each individual message and gives access to `frame.payload` (Buffer for binary msgpack frames).

## Red flags

- A hardcoded integer in a `broadcast_json` or `send_bytes` call that could be replaced with a `MSG_TYPE_*` constant.
- A new message type added to `ws.ts` with no corresponding `MSG_TYPE_*` in `ws.py`.
- `ws.test.ts` values that disagree with the current `MsgType` enum — they tend to drift when types shift but tests aren't updated.
