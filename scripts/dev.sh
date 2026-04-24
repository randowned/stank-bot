#!/bin/bash
# StankBot one-command dev startup (macOS/Linux)
# Starts the Python backend in ENV=dev-mock and the Vite frontend dev server.

set -e

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
export ENV=dev-mock

echo "Starting StankBot in dev-mock mode..."

# Start backend
python -m stankbot &
backend_pid=$!

# Give backend a moment to boot
sleep 2

# Start frontend
cd "$repo_root/src/stankbot/web/frontend"
npm run dev

# Cleanup on exit
echo "Shutting down backend (PID $backend_pid)..."
kill $backend_pid 2>/dev/null || true
