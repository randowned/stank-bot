# Railway Deployment

stank-bot is deployed on [Railway](https://railway.app) using Nixpacks (Railway's default build system).

## Build

Railway auto-detects the Python project via `pyproject.toml` and runs:

```bash
uv sync
```

This installs all `[project] dependencies`, including `numpy` and `faster-whisper` for voice message stank detection.

## System dependencies

System packages are declared in [`nixpacks.toml`](nixpacks.toml) at the project root:

```toml
[phases.setup]
aptPkgs = ["ffmpeg"]
```

**ffmpeg** is required for voice stank detection (Opus → PCM audio decoding via faster-whisper). The bot works without it — voice messages simply aren't classified as stanks if ffmpeg is missing — but the admin dashboard shows a warning banner.

## Environment variables

Defined in Railway's dashboard (not committed):

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Postgres connection string (or SQLite path) |
| `DISCORD_TOKEN` | ✅ | Discord bot token |
| `ENABLE_WEB` | | Set `false` to disable the dashboard |
| `ENV` | | Set `dev-mock` for local testing only |

## Deploy process

Deploys are triggered by the **Deploy** workflow (`.github/workflows/deploy.yml`):

1. A maintainer manually triggers the workflow with a version bump type (`patch`/`minor`/`major`)
2. The workflow bumps the version in `pyproject.toml` and opens a release PR
3. Merging the release PR triggers Railway's auto-deploy from the `main` branch

## Database migrations

Alembic migrations run automatically on Railway. The `[phases.setup]` section in `nixpacks.toml` can run setup commands if needed, but migrations are handled by the application at startup.

See [`AGENTS.md`](AGENTS.md) for migration conventions.
