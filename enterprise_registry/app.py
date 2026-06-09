import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from shared import crypto

FACTS_DIR = Path(__file__).parent / "facts"
AGENTS = ["support-agent"]

# slug → { "facts": <signed dict>, "public_key_pem": <str> }
_cache: dict[str, dict] = {}

_enterprise_private_key = None
_enterprise_public_key_pem: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_and_sign(slug: str) -> tuple[dict, str]:
    raw = json.loads((FACTS_DIR / f"{slug}.json").read_text())

    if not crypto._private_path("enterprise-support-agent").exists():
        crypto.generate_ed25519_keypair("enterprise-support-agent")

    private_key = crypto.load_private_key("enterprise-support-agent")
    public_key_pem = crypto._public_path("enterprise-support-agent").read_text()

    signed = {
        **raw,
        "proof": {
            "type": "Ed25519Signature",
            "verificationMethod": "http://localhost:5003/agents/support-agent/did.json",
            "created": _now(),
            "signature": crypto.sign(raw, private_key),
        },
    }
    return signed, public_key_pem


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _enterprise_private_key, _enterprise_public_key_pem
    key_name = "enterprise-support-agent"
    _enterprise_private_key = crypto.load_private_key(key_name)
    _enterprise_public_key_pem = crypto._public_path(key_name).read_text()
    for slug in AGENTS:
        signed, pub_pem = _load_and_sign(slug)
        _cache[slug] = {"facts": signed, "public_key_pem": pub_pem}
    yield


app = FastAPI(title="ACME Enterprise Registry", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ACME Enterprise Registry"}


@app.get("/public-key")
def public_key():
    return {"public_key_pem": _enterprise_public_key_pem}


@app.get("/agents/{agent_name}/facts")
def get_facts(agent_name: str):
    entry = _cache.get(agent_name)
    if not entry:
        raise HTTPException(status_code=404, detail="agent not found")
    return entry["facts"]


@app.get("/agents/{agent_name}/did.json")
def get_did(agent_name: str):
    entry = _cache.get(agent_name)
    if not entry:
        raise HTTPException(status_code=404, detail="agent not found")
    did = f"did:web:localhost:agents:{agent_name}"
    return {
        "@context": "https://www.w3.org/ns/did/v1",
        "id": did,
        "verificationMethod": [{
            "id": f"{did}#key-1",
            "type": "Ed25519VerificationKey",
            "publicKeyPem": entry["public_key_pem"],
        }],
    }


@app.get("/resolve/{agent_name:path}")
def resolve(agent_name: str):
    slug = agent_name.lstrip("@")
    if slug.startswith("acme:"):
        slug = slug[len("acme:"):]
    entry = _cache.get(slug)
    if not entry:
        raise HTTPException(status_code=404, detail="agent not found")
    payload = {
        "agent_id":          f"enterprise:acme:{slug}",
        "agent_name":        f"@acme:{slug}",
        "primary_facts_url": f"http://localhost:5003/agents/{slug}/facts",
        "ttl":               1800,
        "resolved_at":       _now(),
        "issuer":            "acme",
    }
    signature = crypto.sign(payload, _enterprise_private_key)
    return {**payload, "enterprise_signature": signature}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("enterprise_registry.app:app", host="0.0.0.0", port=5003, reload=True)
