#!/bin/sh
# Start as root so we can fix ownership of the mounted volume (Railway
# mounts volumes as root), then drop to the stankbot user.
set -e

# uvicorn and alembic write INFO logs to stderr by default; Railway
# colors anything on fd2 red. Merge stderr into stdout so routine
# startup/request logs aren't mis-flagged as errors.
exec 2>&1

echo "[entrypoint] chown /data"
chown -R stankbot:stankbot /data 2>/dev/null || true

# Bind to Railway's injected PORT if present (their proxy routes to
# that port); otherwise default to 8000 for local/Docker runs. The
# public-domain "target port" setting in Railway must match this.
PORT_TO_BIND="${PORT:-8000}"
export WEB_BIND="0.0.0.0:$PORT_TO_BIND"
echo "[entrypoint] WEB_BIND=$WEB_BIND (PORT=${PORT:-<unset>})"

echo "[entrypoint] alembic upgrade head"
cd /app
gosu stankbot alembic upgrade head

echo "[entrypoint] exec $*"
exec gosu stankbot "$@"
