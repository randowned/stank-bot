#!/bin/sh
# Start as root so we can fix ownership of the mounted volume (Railway
# mounts volumes as root), then drop to the stankbot user.
set -e

chown -R stankbot:stankbot /data 2>/dev/null || true

exec gosu stankbot "$@"
