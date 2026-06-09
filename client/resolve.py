"""
NANDA resolution client.

Usage:
  python resolve.py @translation-agent
  python resolve.py @weather-agent
  python resolve.py @translation-agent --tamper-demo
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from shared.crypto import verify

INDEX = "http://localhost:5001"

GREEN = "\033[92m"
RED   = "\033[91m"
RESET = "\033[0m"

OK  = f"{GREEN}✓ VALID{RESET}"
BAD = f"{RED}✗ INVALID{RESET}"


def _step(n: int, msg: str) -> None:
    print(f"\n[{n}/7] {msg}")


def _ok(msg: str)  -> None: print(f"  {GREEN}✓{RESET} {msg}")
def _err(msg: str) -> None: print(f"  {RED}✗{RESET} {msg}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print("Usage: python resolve.py <@agent-name> [--tamper-demo]")
        sys.exit(1)

    agent_name  = args[0]
    tamper_demo = "--tamper-demo" in args

    # ── Step 1: Fetch index public key ────────────────────────────────────────
    _step(1, "Fetching index server public key")
    r = requests.get(f"{INDEX}/health", timeout=10)
    r.raise_for_status()
    health = r.json()
    index_pub_pem: str = health["index_public_key"]
    index_public_key = load_pem_public_key(index_pub_pem.encode())
    _ok(f"Index server: {health['service']}")

    # ── Step 2: Resolve agent ─────────────────────────────────────────────────
    _step(2, f"Resolving agent  {agent_name}")
    r = requests.get(f"{INDEX}/resolve/{agent_name}", timeout=10)
    if r.status_code == 404:
        _err(f"Agent '{agent_name}' not found in index")
        sys.exit(1)
    r.raise_for_status()
    resolved = r.json()
    print(f"  agent_id  : {resolved['agent_id']}")
    print(f"  facts_url : {resolved['primary_facts_url']}")
    print(f"  ttl       : {resolved['ttl']}s")

    # ── Step 3: Verify AgentAddr signature ────────────────────────────────────
    _step(3, "Verifying AgentAddr signature")
    index_sig  = resolved.pop("index_signature")
    addr_valid = verify(resolved, index_sig, index_public_key)
    if addr_valid:
        _ok(f"AgentAddr signature  {OK}")
    else:
        _err(f"AgentAddr signature  {BAD}")
        sys.exit(1)

    # ── Step 4: Fetch AgentFacts ──────────────────────────────────────────────
    facts_url = resolved["primary_facts_url"]
    if tamper_demo:
        facts_url = facts_url.rstrip("/") + "/tampered"
        _step(4, f"Fetching TAMPERED AgentFacts  ({facts_url})")
    else:
        _step(4, f"Fetching AgentFacts  ({facts_url})")

    r = requests.get(facts_url, timeout=10)
    r.raise_for_status()
    facts = r.json()
    print(f"  label   : {facts.get('label')}")
    print(f"  version : {facts.get('version')}")
    skills = facts.get("skills", [])
    print(f"  skills  : {', '.join(s['id'] for s in skills)}")

    # ── Step 5: Fetch agent public key ────────────────────────────────────────
    _step(5, "Fetching agent public key (DID document)")
    proof = facts.get("proof", {})
    did_url = proof.get("verificationMethod", "")
    r = requests.get(did_url, timeout=10)
    r.raise_for_status()
    did_doc = r.json()
    agent_pub_pem: str = did_doc["verificationMethod"][0]["publicKeyPem"]
    agent_public_key = load_pem_public_key(agent_pub_pem.encode())
    _ok(f"Public key loaded from {did_url}")

    # ── Step 6: Verify AgentFacts signature ───────────────────────────────────
    _step(6, "Verifying AgentFacts signature")
    facts_without_proof = {k: v for k, v in facts.items() if k != "proof"}
    facts_sig   = proof.get("signature", "")
    facts_valid = verify(facts_without_proof, facts_sig, agent_public_key)
    if facts_valid:
        _ok(f"AgentFacts signature  {OK}")
    else:
        _err(f"AgentFacts signature  {BAD}")

    # ── Step 7: Summary ───────────────────────────────────────────────────────
    _step(7, "Summary")
    caps  = facts.get("capabilities", {})
    trust = f"{GREEN}VERIFIED ✓{RESET}" if facts_valid else f"{RED}TAMPERED ✗{RESET}"
    static = facts.get("endpoints", {}).get("static", [])
    print(f"  Agent      : {facts.get('agent_name')}")
    print(f"  Endpoint   : {static[0] if static else 'n/a'}")
    print(f"  Modalities : {', '.join(caps.get('modalities', []))}")
    print(f"  Skills     : {', '.join(s['id'] for s in skills)}")
    print(f"  Auth       : {', '.join(caps.get('authentication', {}).get('methods', []))}")
    print(f"  Trust    : {trust}")
    print()

    if not facts_valid:
        sys.exit(1)


if __name__ == "__main__":
    main()
