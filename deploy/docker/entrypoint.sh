#!/bin/sh
# Start as root so we can fix ownership of the mounted volume (Railway
# mounts volumes as root), then drop to the stankbot user.
set -e

echo "[entrypoint] chown /data"
chown -R stankbot:stankbot /data 2>/dev/null || true

# Railway injects a random PORT env var and expects the service to bind
# to it. Use it if present; otherwise fall back to the Dockerfile's 8000.
if [ -n "$PORT" ]; then
    export WEB_BIND="0.0.0.0:$PORT"
    echo "[entrypoint] using Railway PORT=$PORT (WEB_BIND=$WEB_BIND)"
fi

echo "[entrypoint] alembic upgrade head"
cd /app
gosu stankbot alembic upgrade head

echo "[entrypoint] exec $*"
exec gosu stankbot "$@"
