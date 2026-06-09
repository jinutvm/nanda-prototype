import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from index_server import db
from shared import crypto


_private_key = None
_public_key_pem: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_keys() -> None:
    global _private_key, _public_key_pem
    key_name = "index_server"
    if not crypto._private_path(key_name).exists():
        _private_key, _ = crypto.generate_ed25519_keypair(key_name)
    else:
        _private_key = crypto.load_private_key(key_name)
    _public_key_pem = crypto._public_path(key_name).read_text()


def _agent_addr(row: dict, extra: dict | None = None) -> dict:
    payload = {
        "agent_id":              row["id"],
        "agent_name":            row["agent_name"],
        "primary_facts_url":     row["primary_facts_url"],
        "private_facts_url":     row["private_facts_url"],
        "adaptive_resolver_url": row["adaptive_resolver_url"],
        "ttl":                   row["ttl"],
        "registered_at":         row["registered_at"],
    }
    if extra:
        payload.update(extra)
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    _load_keys()
    yield


app = FastAPI(title="NANDA Index Server", lifespan=lifespan)


class RegisterRequest(BaseModel):
    agent_name: str
    primary_facts_url: str
    private_facts_url: Optional[str] = None
    adaptive_resolver_url: Optional[str] = None
    ttl: int = 3600


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "NANDA Index Server",
        "index_public_key": _public_key_pem,
    }


@app.post("/register", status_code=201)
def register(req: RegisterRequest):
    if db.get_agent(req.agent_name):
        raise HTTPException(status_code=409, detail="agent already registered")
    row = db.register_agent(req.model_dump())
    addr = _agent_addr(row)
    signature = crypto.sign(addr, _private_key)
    return {**addr, "index_signature": signature}


@app.get("/resolve/{agent_name:path}")
def resolve(agent_name: str, request: Request):
    row = db.get_agent(agent_name)
    delegated_name = None

    if not row and ":" in agent_name.lstrip("@"):
        parent = "@" + agent_name.lstrip("@").split(":")[0]
        row = db.get_agent(parent)
        if row:
            delegated_name = agent_name

    if not row:
        raise HTTPException(status_code=404, detail="agent not found")
    client_hint = request.headers.get("x-client-hint")
    db.log_resolution(agent_name, client_hint)
    if delegated_name:
        addr = _agent_addr(row, extra={"resolved_at": _now(), "delegated_name": delegated_name})
    else:
        addr = _agent_addr(row, extra={"resolved_at": _now()})
    signature = crypto.sign(addr, _private_key)
    return {**addr, "index_signature": signature}


@app.get("/agents")
def list_agents():
    return {"agents": db.get_all_agents()}


@app.delete("/agents/{agent_name:path}")
def delete_agent(agent_name: str):
    removed = db.delete_agent(agent_name)
    if not removed:
        raise HTTPException(status_code=404, detail="agent not found")
    return {"status": "revoked", "agent_name": agent_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("index_server.app:app", host="0.0.0.0", port=5001, reload=True)
