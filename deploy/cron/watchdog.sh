#!/usr/bin/env bash
# Fallback for hosts that refuse systemd (some cPanel providers). Install as
# a user cron @reboot + a periodic check — restarts the bot if it died.
#
# Cron entries (edit paths to match your install):
#   @reboot    /home/you/stankbot/deploy/cron/watchdog.sh
#   */5 * * * * /home/you/stankbot/deploy/cron/watchdog.sh

set -euo pipefail

STANKBOT_HOME="${STANKBOT_HOME:-$HOME/stankbot}"
VENV_PY="$STANKBOT_HOME/.venv/bin/python"
LOG_DIR="$STANKBOT_HOME/data/logs"
LOG_FILE="$LOG_DIR/stankbot.log"
ENV_FILE="$STANKBOT_HOME/.env"

mkdir -p "$LOG_DIR"

if pgrep -u "$USER" -f "python -m stankbot" >/dev/null 2>&1; then
    exit 0
fi

cd "$STANKBOT_HOME"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a

nohup "$VENV_PY" -m stankbot >> "$LOG_FILE" 2>&1 &
echo "$(date --iso-8601=seconds) watchdog: started stankbot (pid $!)" >> "$LOG_FILE"
