# NANDA Prototype

A minimal Python prototype demonstrating the NANDA agent discovery and resolution flow using two FastAPI services and a resolution client.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  client/resolve.py                                       │
│  1. Fetch index public key  GET /health                  │
│  2. Resolve agent           GET /resolve/{@agent-name}   │
│  3. Verify AgentAddr Ed25519 signature                   │
│  4. Fetch AgentFacts        GET /agents/{slug}/facts     │
│  5. Fetch DID document      GET /agents/{slug}/did.json  │
│  6. Verify AgentFacts Ed25519 signature                  │
│  7. Print summary                                        │
└────────┬─────────────────────────┬───────────────────────┘
         │                         │
         ▼                         ▼
┌─────────────────┐   ┌──────────────────────────────┐
│  index_server   │   │  agent_facts_server          │
│  :5001          │   │  :5002                       │
│                 │   │                              │
│  GET  /health   │   │  GET /health                 │
│  POST /register │   │  GET /agents/{slug}/facts    │
│  GET  /resolve/ │   │  GET /agents/{slug}/did.json │
│       {name}    │   │  GET /agents/{slug}/facts/   │
│  GET  /agents   │   │       tampered               │
│  DELETE /agents/│   │                              │
│       {name}    │   │                              │
└─────────────────┘   └──────────────────────────────┘
```

Each agent generates an Ed25519 keypair on first boot and stores it in the shared `keys/` directory. The agent facts server signs every facts response; the client fetches the agent's DID document to get the public key and verifies the signature.

## Quick Start

### Option A — Docker (all-in-one)

```bash
docker compose up --build
```

The client container runs the resolution demo and exits. Re-run it with:

```bash
docker compose run --rm client
```

### Option B — Local (no Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Start both servers, register agents, and print useful curl commands
bash scripts/start.sh

# In another terminal — run the resolution client
python3 client/resolve.py @translation-agent
python3 client/resolve.py @weather-agent

# Stop servers
bash scripts/stop.sh
```

### Option C — Full end-to-end demo (bootstrap)

`bootstrap.sh` starts servers, registers agents, runs the full resolution flow for both agents, and runs the tamper demo — then stops everything on exit.

```bash
bash scripts/bootstrap.sh
```

## Services

| Service            | Port | Description                                          |
|--------------------|------|------------------------------------------------------|
| index_server       | 5001 | Agent registration, resolution, and listing         |
| agent_facts_server | 5002 | Signed agent facts + DID documents per agent        |
| client             | —    | Runs the 7-step resolution demo and exits           |

## API Reference

### index_server (port 5001)

| Method | Path                    | Description                                     |
|--------|-------------------------|-------------------------------------------------|
| GET    | /health                 | Health check; returns service name + public key |
| POST   | /register               | Register an agent (body: `RegisterRequest`)     |
| GET    | /resolve/{agent_name}   | Resolve agent → signed AgentAddr                |
| GET    | /agents                 | List all registered agents                      |
| DELETE | /agents/{agent_name}    | Revoke / remove an agent                        |

**RegisterRequest body**

```json
{
  "agent_name":            "@weather-agent",
  "primary_facts_url":     "http://localhost:5002/agents/weather-agent/facts",
  "private_facts_url":     null,
  "adaptive_resolver_url": null,
  "ttl":                   3600
}
```

### agent_facts_server (port 5002)

| Method | Path                               | Description                                       |
|--------|------------------------------------|---------------------------------------------------|
| GET    | /health                            | Health check                                      |
| GET    | /agents/{slug}/facts               | Signed AgentFacts JSON (Ed25519 proof embedded)   |
| GET    | /agents/{slug}/did.json            | DID document with agent's Ed25519 public key      |
| GET    | /agents/{slug}/facts/tampered      | Facts with injected capability (for tamper demo)  |

Available slugs: `translation-agent`, `weather-agent`

## Client Usage

```bash
python3 client/resolve.py @<agent-name>
python3 client/resolve.py @<agent-name> --tamper-demo
```

## Project Structure

```
nanda-prototype/
├── docker-compose.yml
├── requirements.txt
├── scripts/
│   ├── bootstrap.sh          # Full end-to-end demo (start → register → resolve → stop)
│   ├── start.sh              # Start servers, register agents, print curl examples
│   └── stop.sh               # Stop servers using saved PID files
├── keys/                     # Gitignored; Ed25519 PEM files written here at boot
├── logs/                     # Gitignored; server logs and PID files
├── shared/
│   └── crypto.py             # Ed25519 key generation, signing, and verification
├── index_server/
│   ├── app.py                # FastAPI routes
│   ├── db.py                 # SQLite-backed agent store
│   └── crypto.py             # Key loading shim (delegates to shared/crypto.py)
├── agent_facts_server/
│   ├── app.py                # FastAPI routes
│   ├── crypto.py             # Key loading shim (delegates to shared/crypto.py)
│   └── facts/
│       ├── translation-agent.json
│       └── weather-agent.json
└── client/
    └── resolve.py            # 7-step end-to-end resolution and verification demo
```

## Keys

The `keys/` directory is gitignored — **never commit key material**. Both servers auto-generate their Ed25519 keypairs on first boot if the files don't exist:

| File generated                     | Generated by        |
|------------------------------------|---------------------|
| `keys/index_server_*.pem`          | index_server        |
| `keys/translation-agent_*.pem`     | agent_facts_server  |
| `keys/weather-agent_*.pem`         | agent_facts_server  |

**A fresh clone just works** — run `docker compose up` or `bash scripts/start.sh` and keys are created automatically. Every deployment gets its own unique keypair.

## Environment Variables

| Variable           | Default                          | Used by            |
|--------------------|----------------------------------|--------------------|
| KEYS_DIR           | `keys/` (relative to project)    | Both servers       |
| INDEX_SERVER_URL   | `http://localhost:5001`          | client (Docker)    |
| FACTS_SERVER_URL   | `http://localhost:5002`          | client (Docker)    |
