# AGENTS.md

Operational guide for AI agents (Claude Code, etc.) working in this repository. Keep this file current: update it when workflow rules or architecture change.

## Workflow rules

These rules override any default behavior. Follow them strictly.

### Branches
- **Only work on `main`, or on a branch the user explicitly names.** Never create, switch, rebase, or merge branches on your own. No worktrees — edit the files in place.
- **No pull requests.** Never run `gh pr create` or open a PR. The project ships directly from branches.
- **Save changes directly to files and stop.** Do not stage, do not commit. The user previews changes in another editor via its git integration, so unstaged edits are exactly what they want to see.

### Commits
- **Never commit unless the user explicitly asks.** After finishing a change, stop and wait. The user will say "commit it" (or equivalent) when ready.
- **No `Co-Authored-By` trailer.** Never add AI co-author trailers to commit messages or PR bodies. (Also enforced via `~/.claude/CLAUDE.md`.)
- **Commit message format:** `vX.Y.Z - {short context}`
  - Example: `v2.1.0 - feat: add altar multi-sticker support`
  - Example: `v2.0.1 - fix: cooldown leaking across altars`
- **Version bumps are managed by the agent.** Decide the bump based on the change:
  - **Patch (`Z`):** bug fixes, internal tweaks, no behavior change for users.
  - **Minor (`Y`):** new user-visible features, new slash commands, new settings, dashboard additions, non-breaking behavioral changes.
  - **Major (`X`):** breaking changes to database schema (requires migration work beyond alembic autogenerate), removed commands, changed scoring math that invalidates historical data.
- **The version source of truth is the `version` field in [pyproject.toml](pyproject.toml).** Update it as part of the commit; the commit message version must match.
- **Update [README.md](README.md) before every commit** that changes user-visible surface (commands, settings, scoring, game rules, dashboard pages, install/run steps). Review the staged/unstaged changes and sync any drifted sections. If a change is purely internal (refactor, test-only, CI, internal service rename) and the README genuinely needs no edit, say so explicitly when asking to commit.

### Subagents
Use subagents (the `Agent` tool with `Explore`, `Plan`, or `general-purpose`) when the work genuinely benefits from delegation. The v2 codebase is multi-file Python, so cross-cog or cross-service investigations may benefit more than in v1.

**Use a subagent when:**
- Tracing a concept across many files (e.g. "how does the cooldown flow from ChainService through the repositories and into the embed").
- Designing a non-trivial change that touches services + cogs + DB together — spawn a `Plan` agent to validate the approach before editing.
- Running independent investigations in parallel (e.g. one maps scoring math, another maps dashboard routes) so the main context stays clean.
- Using a tool whose output is noisy or large (broad greps, multi-file reads) that would otherwise bloat context for little signal.

**Don't use a subagent for:**
- Edits to a known function at a known line.
- One-shot greps or reads you can do directly with `Grep`/`Read`.
- "Find this string" tasks — use `Grep` directly.

When delegating, brief the agent self-contained: state the goal, name the files/symbols already known, and cap the response length. Never ask a subagent to commit, push, or open PRs — that stays with the main session under the rules above.

**Track whether subagents are actually helping.** After a delegation, notice: did the subagent save time and context, or did it just add a round-trip that you ended up re-doing? Tune this section based on what actually works in this codebase.

### Other defaults
- Stay inside the repo; don't touch external systems without being asked.
- Prefer editing existing code to adding new files. v2 is intentionally multi-file, but resist inventing new modules when an existing one is the right home.
- Do not invent abstractions (base classes, plugin interfaces, dependency-injection frameworks) until a second concrete implementation forces the shape.

## What this project is

**StankBot** is a server-side Python Discord Application that runs the Stank chain game for one or more guilds. It replaces **v1**, a single-file BetterDiscord client-side plugin (`StankBot.plugin.js`) that still lives on the `main` branch for archive but is frozen.

v2 is:
- A long-running Python process built on `discord.py` (Gateway-based) and `FastAPI` (web dashboard).
- Multi-guild from day one; every domain table keyed by `guild_id`.
- **Event-sourced**: the `events` table is the source of truth. Totals, session summaries, records, achievements — all derived from event queries. Snapshot tables (`records`, `player_totals`) are caches, regenerable at any time from the event log.
- Rendered as Discord rich embeds (not ASCII). Templates for the board / record announcement / session-start / session-end / points / cooldown embeds are authored per-guild on the web dashboard.
- Single process by default (`python -m stankbot` starts the bot + the dashboard on port 8000); can be split later.

### Core gameplay
Members post messages containing the `:Stank:` emoji/sticker in a designated **altar channel**. Consecutive valid stanks build a **chain**. Any non-stank message in the altar **breaks** the chain. A guild may register multiple altars (`altars` table), each with its own sticker, chain, and optional scoring overrides.

- **SP (Stank Points):** reward currency for stankers.
- **PP (Punishment Points):** sin counter for chainbreakers.
- **Cooldown:** per (user, altar); configurable; default 20 min. Restanking inside cooldown reacts but awards nothing and doesn't advance the chain.

### SP / PP math (defaults; per-altar override on `altars` row)
- Per valid stank: `sp_flat` (10) + (chain position − 1).
- Chain starter (position 1): extra `sp_starter_bonus` (15).
- **Finish bonus** `sp_finish_bonus` (15) — retroactively on chain break, to the most recent stanker **who is not the chainbreaker** (walks back `chain_messages`; if the entire chain is just the breaker, no bonus is awarded).
- Reactions award `sp_reaction` (1) to the reactor — only on messages in the live chain, and only the **first** time the pair (message, user, sticker) is recorded in `reaction_awards`. Removing + re-adding a reaction cannot re-trigger.
- Chainbreaker penalty: `pp_break_base` (25) + (broken chain length × `pp_break_per_stank` (2)).

### Key architectural invariants
- `services/` is framework-agnostic: no `discord.py` imports. Services take plain data, return plain data + events.
- `cogs/` is the only place `discord.py` types cross in. Cogs translate Discord events → service calls, and service outputs → embeds.
- `web/` is FastAPI; it imports services and repos directly. No duplicated business logic.
- Every mutation writes an `events` row and, for admin actions, an `audit_log` row. The event log must remain complete and append-only — even synthesized rebuild runs rewrite the log; they never patch totals in place.
- Template variables are `{snake_case}` — matches Python identifiers so the service layer can pass context dicts directly.

### Where to look first
- **Scoring math & constants:** [src/stankbot/services/scoring_service.py](src/stankbot/services/scoring_service.py).
- **Live chain handling:** [src/stankbot/services/chain_service.py](src/stankbot/services/chain_service.py). The ONLY place chain state transitions happen.
- **Session boundaries:** [src/stankbot/services/session_service.py](src/stankbot/services/session_service.py). Emits `session_start`/`session_end` events — no snapshot tables.
- **Schema:** [src/stankbot/db/models.py](src/stankbot/db/models.py). Authority for all tables.
- **Embed rendering:** [src/stankbot/services/board_renderer.py](src/stankbot/services/board_renderer.py) + [template_engine.py](src/stankbot/services/template_engine.py).
- **Cogs (Discord surface):** [src/stankbot/cogs/](src/stankbot/cogs/).
- **Dashboard routes:** [src/stankbot/web/routes/](src/stankbot/web/routes/).

### Reference files
- [pyproject.toml](pyproject.toml) — dependencies, version, tool config.
- [alembic.ini](alembic.ini) + [migrations/](migrations/) — schema migrations.
- [deploy/](deploy/) — systemd unit, Docker setup, watchdog fallback.
- [README.md](README.md) — user-facing install & usage. Source of truth is the code; README must not drift.
- [StankBot.plugin.js](StankBot.plugin.js) — **v1 archive only**. Do not edit as part of v2 work. Consult it only as a historical reference for original scoring formulas and template defaults; everything user-facing lives in Python now.
