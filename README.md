![](static/Stank.gif)

# StankBot

**StankBot** is a server-side Discord Application that tracks "Stank" sticker chains in community servers. It's the ground-up Python rewrite of the original BetterDiscord plugin — a real bot user, slash commands, durable storage, per-server configuration, and a web dashboard.

## What the bot does

Players cooperate to build the longest chain of a designated sticker in a designated channel (the **altar**). The chain breaks when anyone posts a non-sticker message. Players earn Stank Points (SP) for contributing and Punishment Points (PP) for breaking chains.

Rankings are **net SP** (earned SP minus PP).

| Action | Points |
|---|---|
| Chain starter (first stank in a new chain) | +10 SP base + 15 SP starter bonus |
| Each subsequent stank at position *N* | +10 SP base + (N−1) SP position bonus |
| Last contributor when a chain breaks (not the breaker) | +15 SP finish bonus |
| React to an in-chain sticker with the altar emoji | +1 SP (once per user per message) |
| Break the chain | −(25 + chain_length × 2) PP |

All values are per-guild defaults, editable on the web dashboard. The same user cannot stank twice within the configurable cooldown (default 10 minutes).

Sessions roll over on a cron (default 07:00 / 15:00 / 23:00 UTC) with configurable warning minutes. Chain continuity across sessions is on by default — the live chain survives the session boundary.

## Feature highlights

- **Slash commands only.** Every user reply is ephemeral unless it's an announcement.
- **Rich embed rendering** for the board, record announcements, and session transitions — no ASCII code blocks.
- **Multi-guild from day one.** Every row keyed by guild id.
- **Event-sourced.** Every SP/PP change is an immutable event row. Player totals, session summaries, and records are derived — `rebuild-from-history` can always reconstruct them.
- **Multi-altar per guild.** Run a themed event (Halloween sticker, Founders Day) alongside the normal chain with its own scoring overrides and a `custom_event_key` tag on every emitted event.
- **Achievements / badges** derived from the event log — First Stank, Centurion, Finisher, Chainbreaker, Comeback Kid, Perfect Session, Streaker.
- **Web dashboard** (FastAPI + Jinja2 + HTMX) with Discord OAuth — public board, player profiles, chain/session history, admin pages with live embed-template preview.

## Running it yourself

### Local dev (Windows)

Requires Python 3.12 and [`uv`](https://github.com/astral-sh/uv).

```powershell
winget install Python.Python.3.12
winget install astral-sh.uv
git clone <this-repo>
cd stank-bot
uv venv
uv sync
cp .env.example .env.local   # fill in tokens
uv run alembic upgrade head
uv run python -m stankbot
```

The bot connects outbound to Discord's Gateway (WebSocket over 443) — no inbound ports, no public URL, no tunnel needed. The dashboard binds to `127.0.0.1:8000` by default.

### Linux VPS (systemd)

`deploy/systemd/stankbot.service` runs `python -m stankbot` in a project-local venv with `EnvironmentFile=/etc/stankbot/stankbot.env` for secrets. Works with either root systemd (`/etc/systemd/system/`) or user systemd (`~/.config/systemd/user/` + `loginctl enable-linger`).

### Docker

```
docker compose up -d
```

Data persists in `./data/` (SQLite by default).

### Railway (auto-deploy from GitHub)

`railway.json` at the repo root points Railway at `deploy/docker/Dockerfile`. Every push to `main` triggers a build and rolling deploy. One-time setup in the Railway UI:

1. New project → Deploy from GitHub repo → pick this repo, branch `main`.
2. Add a **Volume** mounted at `/data` — the Dockerfile already bakes `DATABASE_URL=sqlite+aiosqlite:////data/stankbot.db` against it, so SQLite survives redeploys.
3. Set the same env vars you use locally: `DISCORD_TOKEN`, `DISCORD_APP_ID`, `WEB_SECRET_KEY`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `GUILD_IDS`, etc.
4. Expose port `8000`; Railway mints a public URL for the dashboard. Add `<that URL>/auth/callback` to the Discord OAuth2 redirects list.
5. Keep replicas at **1** — Discord only allows one gateway connection per shard.

Deploys are gated on the `/healthz` endpoint, which returns 200 only when the DB is reachable and the Discord client is `is_ready()`. On redeploy, Railway sends SIGTERM; the bot cancels scheduled jobs, closes the gateway cleanly, and disposes the engine before exiting. APScheduler jobs are rebuilt from guild settings on each boot, so no schedule state is lost.

## Creating the bot user

1. Discord Developer Portal → Applications → StankBot (App ID `1494266000064122930`).
2. **Bot** → *Reset Token* → copy into `DISCORD_TOKEN`.
3. Enable **Message Content Intent** and **Server Members Intent**. Presence intent is off.
4. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`; permissions Send Messages, Embed Links, Read Message History, Add Reactions, Use External Stickers, Manage Messages.
5. Open the generated URL, pick your guild, authorize.
6. In the Developer Portal, add your dashboard URL + `/auth/callback` to **OAuth2 → Redirects** so web login works.
7. Leave the **Interactions Endpoint URL** field empty — v2 uses the Gateway, not webhook interactions.

## Configuration

Environment (see `.env.example`):

| Var | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token |
| `DISCORD_APP_ID` | Application id (default `1494266000064122930`) |
| `DATABASE_URL` | SQLAlchemy URL, e.g. `sqlite+aiosqlite:///./data/stankbot.db` |
| `OWNER_ID` | Your Discord user id — bypass permission checks |
| `LOG_LEVEL` | `INFO` / `DEBUG` |
| `ENABLE_WEB` | `true` to run the dashboard in the same process |
| `WEB_HOST` / `WEB_PORT` | Dashboard bind (defaults `127.0.0.1:8000`) |
| `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` / `OAUTH_REDIRECT_URI` | Dashboard login |
| `GUILD_IDS` | Comma-separated guild ids for instant slash sync during dev |
| `SESSION_SECRET` | Cookie signing secret for the dashboard |

Everything else — scoring tuning, reset hours, embed templates, feature toggles — lives on the web dashboard.

## First-time guild setup

```
/stank-admin altars add channel:#altar sticker:<sticker_id>
/stank-admin channels add purpose:commands       channel:#bot-commands
/stank-admin channels add purpose:announcements  channel:#general
/stank-admin admin-roles add role:@Mods
/stank-admin rebuild-from-history        # optional — replay existing chat
```

## Command reference

### User (`/stank …`)

| Command | What it does |
|---|---|
| `/stank board` | Rich embed of the current chain, records, rankings. |
| `/stank points [rank] [user]` | Your (or target's) SP / PP / chains / badges. |
| `/stank cooldown` | Seconds left before you can stank again. |
| `/stank help` | Rules + scoring table. |
| `/stank history me` | Your per-session trend. |
| `/stank history user <user>` | Same for a target user. |
| `/stank history chain <id>` | Chain replay. |
| `/stank history session <id>` | Session summary. |

### Admin (`/stank-admin …`) — requires admin role or Manage Guild

| Command | What it does |
|---|---|
| `/stank-admin dashboard` | Posts the dashboard URL for this guild. |
| `/stank-admin new-session` | End current session, start next; chain persists. |
| `/stank-admin reset` | Wipe chain / events / records (destructive, confirmation). |
| `/stank-admin rebuild-from-history` | Wipe + replay altar channel history (destructive). |
| `/stank-admin record-test` | Ephemeral preview of the record announcement. |
| `/stank-admin log [lines]` | Tail recent bot log. |
| `/stank-admin config view` | Read-only snapshot of current settings. |
| `/stank-admin channels add\|remove` | Wire command / announcement channels. |
| `/stank-admin admin-roles add\|remove\|list` | Manage admin roles. |
| `/stank-admin altars add\|remove\|list` | Register / remove altars. |

Template bodies, scoring overrides, reset hours, and achievement tuning are web-only — `/stank-admin config view` surfaces the current values but does not edit them.

CLI alternative for rebuild: `python -m stankbot.rebuild --guild-id <id>`.

## Web dashboard

- `/` — guild list.
- `/g/{guild_id}/board` — public leaderboard + chain state.
- `/g/{guild_id}/me` → `/g/{guild_id}/player/{user_id}` — your stats, badges, history.
- `/g/{guild_id}/history/chains` · `/chain/{id}` — chain browser + replay.
- `/g/{guild_id}/history/sessions` · `/session/{id}` — session browser + summary.
- `/g/{guild_id}/admin/settings` — scoring / reset / feature toggles.
- `/g/{guild_id}/admin/templates` — embed editor with HTMX live preview.
- `/g/{guild_id}/admin/altars` · `/roles` · `/audit` — wiring + audit trail.

## Migrating from v1

v1 was a BetterDiscord client-side plugin bound to one user's client session. v2 is a real Discord Application — **they do not share storage**. The supported migration is a clean cutover:

1. Stop the v1 plugin.
2. Invite the v2 bot.
3. Configure altars / channels / roles.
4. Run `/stank-admin rebuild-from-history` to replay the altar channel from the beginning. Rebuild is idempotent — safe to re-run.

There is no v1 → v2 data importer. Channel history is the source of truth.

## License

See `LICENSE`.
