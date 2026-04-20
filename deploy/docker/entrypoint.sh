#!/bin/sh
# Start as root so we can fix ownership of the mounted volume (Railway
# mounts volumes as root), then drop to the stankbot user.
set -e

echo "[entrypoint] chown /data"
chown -R stankbot:stankbot /data 2>/dev/null || true

echo "[entrypoint] alembic upgrade head"
cd /app
gosu stankbot alembic upgrade head

echo "[entrypoint] exec $*"
exec gosu stankbot "$@"
