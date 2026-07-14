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

## Railway CLI

Install the CLI:

```bash
curl -fsSL https://railway.app/install.sh | sh
# adds to ~/.railway/bin/railway
```

Add `~/.railway/bin` to your PATH or use the full path.

### Authentication

**Log in interactively:**

```bash
railway login --browserless
# → Go to https://railway.com/activate and enter the code shown
```

This persists credentials to `~/.railway/` and allows full CLI access (including SSH).

**Project tokens (CI/automation only):**

Create a **Project Token** in the Railway dashboard (Project → Tokens). Tokens are scoped to a single project and can only perform project-level actions (deploy, variable read, status). They cannot run account-level commands (`whoami`, SSH key management).

```bash
# Use a project token for status / variable queries
RAILWAY_TOKEN=<token> railway status
RAILWAY_TOKEN=<token> railway variable list --json
```

### SSH into the service

The production database is **SQLite** on the persistent volume at `/data/stankbot.db`.

```bash
# 1. Add an SSH key (needs account-level auth, not project token)
railway ssh keys add -k ~/.ssh/id_ed25519 -n my-key-name

# 2. Configure SSH host alias (writes to ~/.ssh/config)
railway ssh config --identity-file ~/.ssh/id_ed25519

# 3. SSH in and query the DB
ssh railway-stank-bot 'python3 -c "
import sqlite3
conn = sqlite3.connect(\"/data/stankbot.db\")
# ... queries ...
"'
```

To query via SSH without setting up a config entry:

```bash
ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519 -p 22 \
  <user>@ssh.railway.com \
  <command>
```

You can find the user/host alias by running `railway ssh config --identity-file ~/.ssh/id_ed25519 --dry-run`.

### Production database

| Property | Value |
|----------|-------|
| Engine | SQLite (no PostgreSQL) |
| Path | `/data/stankbot.db` (persistent volume) |
| Volume | `stank-bot-volume` (5 GB, ~735 MB used) |
| Access | SSH only (no direct tunnel) |

The `DATABASE_URL` is **not set** in Railway env vars — the bot uses the default `sqlite+aiosqlite:///./data/stankbot.db` and relies on the volume mount at `/data/`.

### Read-only querying (safe)

When investigating production data, pipe a Python script via SSH. The volume is on-disk SQLite — no replication lag, no connection pool pressure:

```bash
cat query.py | ssh railway-stank-bot python3
```
