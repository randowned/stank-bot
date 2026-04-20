#!/bin/sh
# Start as root so we can fix ownership of the mounted volume (Railway
# mounts volumes as root), then drop to the stankbot user.
set -e

chown -R stankbot:stankbot /data 2>/dev/null || true

# Apply DB migrations before handing off to the bot. Runs as the
# stankbot user so the SQLite file ends up owned correctly.
cd /app
gosu stankbot alembic upgrade head

exec gosu stankbot "$@"
