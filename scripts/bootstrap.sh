#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

GREEN='\033[92m'
RED='\033[91m'
RESET='\033[0m'

ok()  { echo -e "${GREEN}[ok]${RESET}  $*"; }
err() { echo -e "${RED}[err]${RESET} $*"; }
sep() { echo; echo "──────────────────────────────────────────"; echo "$*"; echo "──────────────────────────────────────────"; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
INDEX_PID=""
FACTS_PID=""

cleanup() {
  echo
  echo "Stopping servers..."
  [[ -n "$INDEX_PID" ]] && kill "$INDEX_PID" 2>/dev/null && ok "index_server stopped"
  [[ -n "$FACTS_PID" ]] && kill "$FACTS_PID" 2>/dev/null && ok "agent_facts_server stopped"
}
trap cleanup EXIT

# ── Step 1: Install dependencies ─────────────────────────────────────────────
sep "Step 1/8 · Install dependencies"
pip install -q -r requirements.txt
ok "dependencies installed"

# ── Step 2: Start index_server ────────────────────────────────────────────────
sep "Step 2/8 · Start index_server (port 5001)"
python3 -m uvicorn index_server.app:app --host 0.0.0.0 --port 5001 \
  --log-level warning &
INDEX_PID=$!
ok "index_server started (pid $INDEX_PID)"

# ── Step 3: Start agent_facts_server ─────────────────────────────────────────
sep "Step 3/8 · Start agent_facts_server (port 5002)"
python3 -m uvicorn agent_facts_server.app:app --host 0.0.0.0 --port 5002 \
  --log-level warning &
FACTS_PID=$!
ok "agent_facts_server started (pid $FACTS_PID)"

# ── Step 4: Wait for servers to be ready ─────────────────────────────────────
sep "Step 4/8 · Waiting for servers to be ready"
sleep 2

wait_for() {
  local url="$1" name="$2" attempts=10
  for i in $(seq 1 $attempts); do
    if curl -sf "$url" > /dev/null 2>&1; then
      ok "$name is up"
      return 0
    fi
    sleep 1
  done
  err "$name did not respond at $url after $attempts seconds"
  exit 1
}

wait_for "http://localhost:5001/health" "index_server"
wait_for "http://localhost:5002/health" "agent_facts_server"

# ── Step 5: Register @translation-agent ──────────────────────────────────────
register_agent() {
  local name="$1" facts_url="$2"
  local body
  body=$(curl -s -X POST http://localhost:5001/register \
    -H "Content-Type: application/json" \
    -d "{\"agent_name\":\"${name}\",\"primary_facts_url\":\"${facts_url}\",\"ttl\":3600}")
  if [[ -n "$body" ]]; then
    echo "$body" | python3 -m json.tool
  fi
  ok "${name} registered"
}

sep "Step 5/8 · Register @translation-agent"
register_agent "@translation-agent" "http://localhost:5002/agents/translation-agent/facts"

# ── Step 6: Register @weather-agent ──────────────────────────────────────────
sep "Step 6/8 · Register @weather-agent"
register_agent "@weather-agent" "http://localhost:5002/agents/weather-agent/facts"

# ── Step 7: Run resolution client for both agents ─────────────────────────────
sep "Step 7/8 · Resolve @translation-agent"
python3 client/resolve.py @translation-agent

sep "Step 7/8 · Resolve @weather-agent"
python3 client/resolve.py @weather-agent

# ── Step 8: Tamper demo ───────────────────────────────────────────────────────
sep "Step 8/8 · Tamper demo (@translation-agent --tamper-demo)"
python3 client/resolve.py @translation-agent --tamper-demo || true

ok "Bootstrap complete."
