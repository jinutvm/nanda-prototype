#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
RED='\033[91m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}[ok]${RESET}   $*"; }
info() { echo -e "${YELLOW}[info]${RESET} $*"; }
cmd()  { echo -e "${CYAN}  \$${RESET} $*"; }
err()  { echo -e "${RED}[err]${RESET}  $*"; }
sep()  { echo; echo "──────────────────────────────────────────"; echo "  $*"; echo "──────────────────────────────────────────"; }

# ── Kill any existing servers on those ports ──────────────────────────────────
kill_port() {
  local port="$1"
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    info "killed existing process on port $port (pid $pid)"
  fi
}

kill_port 5001
kill_port 5002

# ── Step 1: Start servers ─────────────────────────────────────────────────────
sep "Step 1 · Starting servers"

mkdir -p "$ROOT/logs"

python3 -m uvicorn index_server.app:app \
  --host 0.0.0.0 --port 5001 --log-level warning \
  >> "$ROOT/logs/index_server.log" 2>&1 &
INDEX_PID=$!
ok "index_server started  (pid $INDEX_PID)  → logs/index_server.log"

python3 -m uvicorn agent_facts_server.app:app \
  --host 0.0.0.0 --port 5002 --log-level warning \
  >> "$ROOT/logs/agent_facts_server.log" 2>&1 &
FACTS_PID=$!
ok "agent_facts_server started  (pid $FACTS_PID)  → logs/agent_facts_server.log"

echo "$INDEX_PID" > "$ROOT/logs/index_server.pid"
echo "$FACTS_PID" > "$ROOT/logs/agent_facts_server.pid"

# ── Step 2: Health checks ─────────────────────────────────────────────────────
sep "Step 2 · Health checks"

wait_for() {
  local url="$1" name="$2" attempts=15
  for i in $(seq 1 $attempts); do
    if curl -sf "$url" > /dev/null 2>&1; then
      ok "$name  →  $url"
      return 0
    fi
    sleep 1
  done
  err "$name did not respond after $attempts s"
  exit 1
}

wait_for "http://localhost:5001/health" "index_server"
wait_for "http://localhost:5002/health" "agent_facts_server"

echo
cmd "curl http://localhost:5001/health"
curl -s http://localhost:5001/health | python3 -m json.tool

echo
cmd "curl http://localhost:5002/health"
curl -s http://localhost:5002/health | python3 -m json.tool

# ── Step 3: Agent list ────────────────────────────────────────────────────────
sep "Step 3 · Agent list (before registration)"
cmd "curl http://localhost:5001/agents"
curl -s http://localhost:5001/agents | python3 -m json.tool

# ── Step 4: Register agents ───────────────────────────────────────────────────
sep "Step 4 · Registering agents"

register_agent() {
  local name="$1" facts_url="$2"
  cmd "curl -X POST http://localhost:5001/register -d '{\"agent_name\":\"${name}\", ...}'"
  local body
  body=$(curl -s -X POST http://localhost:5001/register \
    -H "Content-Type: application/json" \
    -d "{\"agent_name\":\"${name}\",\"primary_facts_url\":\"${facts_url}\",\"ttl\":3600}")
  echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
  local detail
  detail=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail',''))" 2>/dev/null || true)
  if [[ "$detail" == "agent already registered" ]]; then
    info "${name} already registered — skipping"
  else
    ok "${name} registered"
  fi
}

register_agent "@translation-agent" \
  "http://localhost:5002/agents/translation-agent/facts"

register_agent "@weather-agent" \
  "http://localhost:5002/agents/weather-agent/facts"

# ── Step 5: Register tampered variant ────────────────────────────────────────
sep "Step 5 · Registering @translation-agent-tampered"
register_agent "@translation-agent-tampered" \
  "http://localhost:5002/agents/translation-agent/facts/tampered"

# ── Final agent list ──────────────────────────────────────────────────────────
sep "Registered agents"
cmd "curl http://localhost:5001/agents"
curl -s http://localhost:5001/agents | python3 -m json.tool

# ── Useful commands ───────────────────────────────────────────────────────────
sep "Useful commands"
echo -e "  Resolve agent:"
cmd   "curl http://localhost:5001/resolve/@translation-agent | python3 -m json.tool"
echo -e "  Fetch facts:"
cmd   "curl http://localhost:5002/agents/translation-agent/facts | python3 -m json.tool"
cmd   "curl http://localhost:5002/agents/weather-agent/facts | python3 -m json.tool"
echo -e "  Fetch tampered facts:"
cmd   "curl http://localhost:5002/agents/translation-agent/facts/tampered | python3 -m json.tool"
echo -e "  Delete agent:"
cmd   "curl -X DELETE http://localhost:5001/agents/@translation-agent"
echo -e "  Run resolution client:"
cmd   "python3 client/resolve.py @translation-agent"
cmd   "python3 client/resolve.py @translation-agent-tampered"

echo
ok "Servers are running. To stop: bash scripts/stop.sh"
echo -e "  index_server       →  http://localhost:5001"
echo -e "  agent_facts_server →  http://localhost:5002"
echo
