#!/usr/bin/env bash
# AuthCheck one-command launcher.
#   ./start.sh            install deps, start the server, print every link
#   ./start.sh --test     also run the self-test before starting
#   ./start.sh --stop     stop a running instance
set -uo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-12000}"
HOST="${HOST:-0.0.0.0}"
LOG="server.log"
PIDFILE=".authcheck.pid"

say() { printf '\033[1;33m%s\033[0m\n' "$*"; }
ok()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
err() { printf '\033[1;31m%s\033[0m\n' "$*"; }

if [ "${1:-}" = "--stop" ]; then
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    kill "$(cat "$PIDFILE")" && rm -f "$PIDFILE" && ok "Stopped."
  else
    pkill -f "uvicorn app:app" 2>/dev/null && ok "Stopped (by pattern)." || say "Nothing running."
  fi
  exit 0
fi

say "==> 1/4  Installing dependencies"
python3 -m pip install --quiet --disable-pip-version-check -r requirements.txt || {
  err "Dependency install failed."; exit 1; }

if [ "${1:-}" = "--test" ]; then
  say "==> 2/4  Running self-test"
  python3 selftest.py || { err "Self-test failed — not starting."; exit 1; }
else
  say "==> 2/4  Self-test skipped (use --test to run it)"
fi

# PIN gate: reuse the saved one, or generate a fresh 6-digit PIN.
if [ -z "${PANEL_PIN:-}" ]; then
  if [ -f .panel_pin ]; then
    PANEL_PIN="$(grep -oE '[0-9]{6}' .panel_pin | head -1)"
  else
    PANEL_PIN="$(python3 -c "import secrets;print(''.join(secrets.choice('0123456789') for _ in range(6)))")"
    echo "PANEL_PIN=$PANEL_PIN" > .panel_pin
  fi
fi
export PANEL_PIN

say "==> 3/4  Starting server on port $PORT"
pkill -f "uvicorn app:app" 2>/dev/null
sleep 1
PANEL_PIN="$PANEL_PIN" nohup python3 -m uvicorn app:app --host "$HOST" --port "$PORT" > "$LOG" 2>&1 &
echo $! > "$PIDFILE"

for i in $(seq 1 30); do
  sleep 1
  if curl -sf -m 2 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then break; fi
done

if ! curl -sf -m 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
  err "Server did not come up. Last log lines:"; tail -20 "$LOG"; exit 1
fi

say "==> 4/4  Ready"
echo
ok "  CONTROL ROOM (one-click panel)  http://127.0.0.1:$PORT/panel"
ok "  The app itself                  http://127.0.0.1:$PORT/"
ok "  API health                      http://127.0.0.1:$PORT/api/health"
echo
say "  Control Room PIN:  $PANEL_PIN   (saved in .panel_pin)"
echo
say "  Public URL (if exposed):"
echo "    ${AUTHCHECK_PUBLIC_URL:-<not set>}"
echo
say "  Stop with:  ./start.sh --stop    |    Logs: $LOG"
