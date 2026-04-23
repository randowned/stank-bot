# v2 parity map — legacy Jinja → SvelteKit

Feature parity ledger for the legacy FastAPI+Jinja dashboard and the
SvelteKit v2 dashboard. Retiring the legacy routes is a separate future
track; this document makes the eventual cutover a checklist, not an
investigation.

Both dashboards are mounted in the same process during the transition.
`AppConfig.dashboard_frontend` (`"legacy"` | `"v2"`) picks which URL
family the bot's embeds link to — see `stankbot.services.dashboard_urls`.

## Public routes

| Legacy (Jinja)            | v2 (SvelteKit)          | Status |
| ------------------------- | ----------------------- | ------ |
| `GET /`                   | `GET /v2/`              | ✅     |
| `GET /player/{id}`        | `GET /v2/player/{id}`   | ✅     |
| `GET /history/chain/{id}` | `GET /v2/chain/{id}`    | ✅     |
| `GET /history/session/{id}` | `GET /v2/session/{id}`  | ✅ (v2.7) |
| `GET /history`            | `GET /v2/sessions`, `GET /v2/chains` | ✅ |
| `GET /healthz`            | `GET /healthz` (shared) | ✅     |

## Auth

| Legacy                   | v2                    | Status |
| ------------------------ | --------------------- | ------ |
| `GET /auth/login`        | shared                | ✅     |
| `GET /auth/callback`     | shared                | ✅     |
| `GET /auth/logout`       | shared                | ✅     |
| `POST /auth/mock-login`  | shared (dev only)     | ✅     |

Post-login landing is driven by `?next=` with a config-driven default so
flipping `dashboard_frontend` from `legacy` to `v2` is a one-line change.

## Admin routes

Legacy admin is HTML-rendering (`routes/admin.py`). v2 admin is JSON
(`v2_admin.py`) + SvelteKit pages under `/v2/admin/*`.

| Legacy (HTML)                         | v2 API (JSON)                                | v2 SvelteKit page              | Status |
| ------------------------------------- | -------------------------------------------- | ------------------------------ | ------ |
| `GET /admin`                          | (dashboard tiles are client-side)            | `/v2/admin`                    | ✅ (v2.7) |
| `GET /admin/settings`                 | `GET /v2/api/admin/settings`                 | `/v2/admin/settings`           | ✅ |
| `POST /admin/settings`                | `POST /v2/api/admin/settings`                | same page                      | ✅ |
| `GET /admin/altar`                    | `GET /v2/api/admin/altar`                    | `/v2/admin/altar`              | ✅ |
| `POST /admin/altar/set`               | `POST /v2/api/admin/altar/set`               | same page                      | ✅ |
| `POST /admin/altar/remove`            | `POST /v2/api/admin/altar/remove`            | same page                      | ✅ |
| `GET /admin/roles`                    | `GET /v2/api/admin/roles`                    | `/v2/admin/roles`              | ✅ |
| `POST /admin/roles/add`               | `POST /v2/api/admin/roles/add`               | same page                      | ✅ |
| `POST /admin/roles/remove`            | `POST /v2/api/admin/roles/remove`            | same page                      | ✅ |
| `POST /admin/roles/users/add`         | `POST /v2/api/admin/roles/users/add`         | same page                      | ✅ |
| `POST /admin/roles/users/remove`      | `POST /v2/api/admin/roles/users/remove`      | same page                      | ✅ |
| `GET /admin/audit`                    | `GET /v2/api/admin/audit`                    | `/v2/admin/audit`              | ✅ |
| `GET /admin/announcements`            | `GET /v2/api/admin/announcements`            | `/v2/admin/announcements`      | ✅ |
| `POST /admin/announcements`           | `POST /v2/api/admin/announcements`           | same page                      | ✅ |
| `POST /admin/announcements/remove`    | `POST /v2/api/admin/announcements/remove`    | same page                      | ✅ |
| `GET /admin/maintenance`              | `GET /v2/api/admin/maintenance`              | `/v2/admin/maintenance`        | ✅ |
| `POST /admin/maintenance`             | `POST /v2/api/admin/maintenance`             | same page                      | ✅ |
| `GET /admin/config`                   | `GET /v2/api/admin/config`                   | `/v2/admin/config`             | ✅ |
| `GET /admin/templates`                | `GET /v2/api/admin/templates`                | `/v2/admin/templates`          | ✅ |
| `GET /admin/templates/{key}`          | `GET /v2/api/admin/templates/{key}`          | same page (tabs)               | ✅ |
| `POST /admin/templates/{key}`         | `POST /v2/api/admin/templates/{key}`         | same page                      | ✅ |
| (new)                                 | `POST /v2/api/admin/templates/{key}/preview` | live preview pane              | ✅ (new in v2) |
| `POST /admin/new-session`             | `POST /v2/api/admin/new-session`             | `/v2/admin/session/new`        | ✅ |
| `POST /admin/reset`                   | `POST /v2/api/admin/reset`                   | `/v2/admin/session/reset`      | ✅ |
| `POST /admin/rebuild`                 | `POST /v2/api/admin/rebuild`                 | `/v2/admin/session/rebuild`    | ✅ |
| `GET /admin/guilds/select?guild_id=…` | `POST /v2/api/admin/guild?guild_id=…`        | in header UserMenu             | ✅ |

Both guild-switch code paths write `request.session["guild"]` identically
so removing the HTML redirect later will be a no-op behavioral change.

## New in v2 (no legacy counterpart)

- `GET /v2/api/guilds` — user's accessible guilds with bot-presence flags.
- `GET /v2/api/players/batch?ids=…` — resolve contributor IDs to names for
  chain detail + session pages.
- WebSocket at `/v2/ws` — msgpack-framed live updates.
- Header UserMenu with inline guild switcher.

## External links audit

Grep `src/stankbot/cogs/` and template defaults for hardcoded
`/player/…` / `/history/…` / `/admin/…`. Replace call sites with:

```python
from stankbot.services.dashboard_urls import dashboard_url_for

url = dashboard_url_for(
    "chain",
    base_url=config.public_base_url,
    frontend=config.dashboard_frontend,
    chain_id=chain.id,
)
```

Flipping `dashboard_frontend` from `legacy` to `v2` then updates every
bot embed at once, with zero code changes at the retirement milestone.

## Retirement checklist (future track — NOT this plan)

1. Flip `dashboard_frontend` default from `legacy` to `v2`.
2. Smoke-test each row in the table above against v2 in staging.
3. Delete `src/stankbot/web/routes/admin.py` (+ `player.py`, `public.py`,
   `history.py` to the extent their jobs moved to v2).
4. Delete `src/stankbot/web/templates/`.
5. Drop the `/admin/guilds/select` redirect and the legacy `/` handler.
6. Bump major version.
