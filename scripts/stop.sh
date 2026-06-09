#!/usr/bin/env bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

GREEN='\033[92m'
RESET='\033[0m'
ok() { echo -e "${GREEN}[ok]${RESET}  $*"; }

stop_pid_file() {
  local pidfile="$1" name="$2"
  if [[ -f "$pidfile" ]]; then
    local pid
    pid=$(cat "$pidfile")
    kill "$pid" 2>/dev/null && ok "$name stopped (pid $pid)" || true
    rm -f "$pidfile"
  else
    # fallback: kill by port
    local port="$3"
    local pid
    pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null && ok "$name stopped (pid $pid)" || true
  fi
}

stop_pid_file "$ROOT/logs/index_server.pid"       "index_server"       5001
stop_pid_file "$ROOT/logs/agent_facts_server.pid" "agent_facts_server" 5002
stop_pid_file "$ROOT/logs/enterprise_registry.pid" "enterprise_registry" 5003
