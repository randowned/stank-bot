# Railway Deployment

stank-bot is deployed on [Railway](https://railway.app). The deploy config is in [`railway.json`](../railway.json) at the repo root.

## Builder: Dockerfile

Railway builds using a **Dockerfile** (`deploy/docker/Dockerfile`), **not** Nixpacks. The `railway.json` specifies:

```json
"builder": "DOCKERFILE",
"dockerfilePath": "deploy/docker/Dockerfile"
```

This means `nixpacks.toml` — if present — is ignored. All system dependencies must be added to the Dockerfile.

### Adding system packages

Edit `deploy/docker/Dockerfile` and add the package name to the `apt-get install` line:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu fonts-dejavu-core fonts-liberation ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

## Voice detection dependencies

| Dependency | Where | How installed |
|---|---|---|
| `ffmpeg` | system package | Dockerfile `apt-get install ffmpeg` |
| `numpy` | `[project] dependencies` | `pip install .` / `uv sync` |
| `faster-whisper` | `[project] dependencies` | `pip install .` / `uv sync` |

Voice detection gracefully degrades if deps are missing — the altar settings page shows a warning banner with the reason.

## Checking Railway logs

1. Go to [Railway dashboard](https://railway.app/dashboard)
2. Select the stank-bot project
3. Click **Deployments** → select the latest deployment
4. Click **View logs** — you'll see build logs and runtime logs

Common log patterns:
- `"ffmpeg not found on PATH"` — ffmpeg missing from the Docker image
- `"nacl not installed, voice not available"` — harmless, discord.py warning about voice channel (VC) support, not voice messages
- `ModuleNotFoundError: No module named 'numpy'` / `'faster_whisper'` — missing Python dependency

## Healthcheck

Railway pings `/healthz` every 30s. The endpoint returns `200 OK` with `{"status": "ok"}` when the bot is alive. If the bot fails healthchecks for 300s (configurable via `railway.json`), Railway restarts it.

## Manual deploy trigger

Deploys are triggered by pushing to `main`. The release workflow (`deploy.yml`) bumps the version, creates a release PR, and after merge triggers a Railway deploy.
