# Runbook: reset / adjust a player's PP (reverse a chain-break penalty)

Use this when a player's PP (punishment points) needs correcting — e.g. a
chain break that shouldn't have counted (wrong sticker before a rule change,
test message, duplicate post).

## Why not just edit the DB

This project is **event-sourced**. `events` is the append-only source of truth;
`player_totals` (`earned_sp`, `punishments`, …) is a **write-through cache**
updated inside `events_repo.append()`. So:

- ❌ `UPDATE player_totals SET punishments = …` — patches the cache; drifts from
  the log and is reverted by any rebuild.
- ❌ `DELETE FROM events …` — rewrites history (forbidden) and (raw SQL) leaves
  the cache stale anyway.
- ✅ **Append a compensating `pp_break` event with a negative `delta`** through
  `events_repo.append()`. PP lives only on `EventType.PP_BREAK` events
  (`pp_delta = delta` in the write-through), so a `-N` event decrements
  `punishments` by `N` on the all-time row (`session_id = 0`) **and** the row
  for the event's `session_id`. Add an `audit_log` row too.

Caveat: `/stank-admin rebuild-from-history` wipes the log and replays Discord
history — it will **re-introduce** the original penalty unless the sticker that
caused it is, by then, in the altar's accepted patterns.

## Production access

- DB: **SQLite** at `/data/stankbot.db` inside the `stank-bot` Railway service
  (`railway status --json` → service id, currently `603aaecb-…`). Env
  `DATABASE_URL = sqlite+aiosqlite:////data/stankbot.db`. Python 3.12 in-container.
- Run commands non-interactively and dodge shell-quoting by base64-piping a
  script:

  ```bash
  cat > /tmp/x.py <<'PYEOF'
  ...script...
  PYEOF
  B64=$(base64 -w0 /tmp/x.py)
  railway ssh -s <SERVICE_ID> "echo $B64 | base64 -d | python3"
  ```

- **Read-only** queries: open `sqlite3.connect("file:/data/stankbot.db?mode=ro", uri=True)`.

## Procedure

### 1. Inspect (read-only) — find the event(s) and confirm amounts

```python
import sqlite3
db = sqlite3.connect("file:/data/stankbot.db?mode=ro", uri=True); db.row_factory = sqlite3.Row
uid = <USER_ID>
for r in db.execute("SELECT id,guild_id,delta,session_id,chain_id,message_id,created_at,reason FROM events WHERE user_id=? AND type='pp_break' ORDER BY id",(uid,)): print(dict(r))
for r in db.execute("SELECT session_id,earned_sp,punishments FROM player_totals WHERE user_id=? AND session_id IN (0, <BREAK_SESSION_ID>)",(uid,)): print(dict(r))
```

Note the total PP to reverse (`N`), the `guild_id`, and the break's
`session_id` (set the correcting event's `session_id` to the same one so its
per-session row also zeroes; the all-time `session_id=0` row always updates).

### 2. Apply (write) — compensating event + audit, via the app's append path

```python
import asyncio, os
from sqlalchemy import text
from stankbot.db.engine import build_engine, build_sessionmaker, session_scope
from stankbot.db.repositories import events as events_repo
from stankbot.db.repositories import audit_log as audit_repo
from stankbot.db.models import EventType

GUILD=<GUILD>; USER=<USER>; ORIG=<ORIG_EVENT_ID>; DELTA=-<N>
SID=<BREAK_SESSION_ID>; CHAIN=<CHAIN_ID_OR_None>; MSG=<MSG_ID_OR_None>
ACTOR=<ACTOR_DISCORD_ID>   # bot id 1494266000064122930 for a system/manual op

async def main():
    eng=build_engine(os.environ["DATABASE_URL"]); sm=build_sessionmaker(eng)
    async with session_scope(sm) as s:
        # guard: don't double-apply
        if (await s.execute(text("SELECT COUNT(*) FROM events WHERE guild_id=:g AND user_id=:u AND type='pp_break' AND delta<0"),{"g":GUILD,"u":USER})).scalar():
            print("ABORT: negative pp_break already exists"); return
        # guard: confirm current all-time PP equals what we expect to reverse
        cur=(await s.execute(text("SELECT punishments FROM player_totals WHERE guild_id=:g AND user_id=:u AND session_id=0"),{"g":GUILD,"u":USER})).scalar()
        if cur != -DELTA:
            print("ABORT: all-time punishments=%r, expected %d"%(cur,-DELTA)); return
        altar=(await s.execute(text("SELECT altar_id FROM events WHERE id=:i"),{"i":ORIG})).scalar()
        ev=await events_repo.append(s, guild_id=GUILD, type=EventType.PP_BREAK, delta=DELTA,
            user_id=USER, altar_id=altar, session_id=SID, chain_id=CHAIN, message_id=MSG,
            reason="admin correction: reverses event %d"%ORIG,
            payload={"corrects_event_id":ORIG,"kind":"pp_correction"})
        await audit_repo.append(s, guild_id=GUILD, actor_id=ACTOR, action="pp_correction",
            payload={"target_user_id":USER,"reverses_event_id":ORIG,"pp_delta":DELTA})
        print("OK event id=%s"%ev.id)
    await eng.dispose()

asyncio.run(main())
```

### 3. Verify (read-only)

```python
# player_totals punishments should be 0 on session 0 and the break session;
# SUM(delta) over the user's pp_break events should net to 0.
for r in db.execute("SELECT session_id,punishments FROM player_totals WHERE user_id=? AND session_id IN (0, <BREAK_SESSION_ID>)",(uid,)): print(dict(r))
for r in db.execute("SELECT COALESCE(SUM(delta),0) FROM events WHERE user_id=? AND type='pp_break'",(uid,)): print(dict(r))
```

No bot restart needed — totals are read fresh, so the dashboard/leaderboard
reflect the change on next fetch.

## Notes

- To reverse **all** of a player's PP, set `N = current all-time punishments`.
  To reverse only one break, set `N` to that event's `delta`.
- Reducing PP by more than they have would make `punishments` negative — the
  guards above prevent the common mistakes; double-check `N`.
- This pattern generalizes to any SP/PP correction: emit a correcting event of
  the matching `EventType` through `append()` — never patch the cache directly.

## History

- 2026-06-09 — reversed user `325229730003419136`'s first chain break (event
  `187906`, `+31` PP) with correcting event `188043` (`-31`); audit row `#138`.
