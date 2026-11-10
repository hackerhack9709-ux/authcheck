#!/usr/bin/env bash
# Register a curated set of MCP servers with the local OpenHands agent server.
#
# The agent server exposes /api/settings/mcp/{key} guarded by the
# X-Session-API-Key header. The key lives in the agent-server process
# environment (SESSION_API_KEY).
#
# Usage:
#   bash scripts/setup-mcp.sh
#   AGENT_SERVER=http://127.0.0.1:60000 bash scripts/setup-mcp.sh
#
# Only servers that were verified to start and list tools are included.
set -u

AGENT_SERVER="${AGENT_SERVER:-http://127.0.0.1:60000}"
WS="${WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}"

if [ -z "${SESSION_API_KEY:-}" ]; then
  pid=$(pgrep -f 'openhands-agent-server' | head -1)
  if [ -n "$pid" ] && [ -r "/proc/$pid/environ" ]; then
    SESSION_API_KEY=$(tr '\0' '\n' < "/proc/$pid/environ" | sed -n 's/^SESSION_API_KEY=//p')
  fi
fi
if [ -z "${SESSION_API_KEY:-}" ]; then
  echo "error: SESSION_API_KEY not found (export it or run where the agent server is visible)" >&2
  exit 1
fi

add() {
  key="$1"; body="$2"
  printf '%-14s ' "$key"
  code=$(curl -s -m 20 -X POST \
    -H "X-Session-API-Key: $SESSION_API_KEY" -H 'Content-Type: application/json' \
    "$AGENT_SERVER/api/settings/mcp/$key" -d "$body" -o /dev/null -w '%{http_code}')
  case "$code" in
    201) echo "added" ;;
    409) echo "already present" ;;
    *)   echo "failed (HTTP $code)" ;;
  esac
}

add memory '{"transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-memory"],"enabled":true,"description":"Persistent knowledge-graph memory"}'
add sequential '{"transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-sequential-thinking"],"enabled":true,"description":"Structured step-by-step reasoning"}'
add github '{"transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-github"],"env":{"GITHUB_PERSONAL_ACCESS_TOKEN":"'"${GITHUB_TOKEN:-}"'"},"enabled":true,"description":"GitHub repos, issues, PRs, files, search"}'
add puppeteer '{"transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-puppeteer"],"enabled":true,"description":"Headless browser automation and screenshots"}'
add fetch '{"transport":"stdio","command":"uvx","args":["mcp-server-fetch"],"enabled":true,"description":"Fetch a URL and convert it to markdown"}'
add time '{"transport":"stdio","command":"uvx","args":["mcp-server-time"],"enabled":true,"description":"Current time and timezone conversion"}'
add git '{"transport":"stdio","command":"uvx","args":["mcp-server-git","--repository","'"$WS"'"],"enabled":true,"description":"Git status, diff, log, commit on the workspace repo"}'
add filesystem '{"transport":"stdio","command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","'"$WS"'"],"enabled":true,"description":"File read/write/search scoped to the workspace"}'

echo
echo "Registered servers:"
curl -s -m 10 -H "X-Session-API-Key: $SESSION_API_KEY" "$AGENT_SERVER/api/settings" \
  | python3 -c "import json,sys; m=json.load(sys.stdin)['agent_settings']['mcp_config']; [print('  -',k,'('+str(v.get('command'))+')') for k,v in m.items()]"
