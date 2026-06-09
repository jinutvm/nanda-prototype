import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import copy
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from shared import crypto

FACTS_DIR = Path(__file__).parent / "facts"
AGENTS = ["translation-agent", "weather-agent"]

# slug → { "facts": <signed dict>, "public_key_pem": <str> }
_cache: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_and_sign(slug: str) -> tuple[dict, str]:
    raw = json.loads((FACTS_DIR / f"{slug}.json").read_text())

    if not crypto._private_path(slug).exists():
        crypto.generate_ed25519_keypair(slug)

    private_key = crypto.load_private_key(slug)
    public_key_pem = crypto._public_path(slug).read_text()

    signed = {
        **raw,
        "proof": {
            "type": "Ed25519Signature",
            "verificationMethod": f"http://localhost:5002/agents/{slug}/did.json",
            "created": _now(),
            "signature": crypto.sign(raw, private_key),
        },
    }
    return signed, public_key_pem


@asynccontextmanager
async def lifespan(app: FastAPI):
    for slug in AGENTS:
        signed, pub_pem = _load_and_sign(slug)
        _cache[slug] = {"facts": signed, "public_key_pem": pub_pem}
    yield


app = FastAPI(title="NANDA Agent Facts Server", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "NANDA Agent Facts Server"}


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


@app.get("/agents/{agent_name}/facts/tampered")
def get_tampered_facts(agent_name: str):
    entry = _cache.get(agent_name)
    if not entry:
        raise HTTPException(status_code=404, detail="agent not found")
    tampered = copy.deepcopy(entry["facts"])
    modalities = tampered.get("capabilities", {}).get("modalities")
    if isinstance(modalities, list) and "video" not in modalities:
        modalities.append("video")
    return tampered


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent_facts_server.app:app", host="0.0.0.0", port=5002, reload=True)
