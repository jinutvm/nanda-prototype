"""Thin wrapper: generates/loads the index_server keypair via shared.crypto."""
from shared.crypto import (
    generate_ed25519_keypair,
    load_private_key,
    load_public_key,
    sign,
    verify,
    KEYS_DIR,
)

_KEY_NAME = "index_server"


def ensure_keypair():
    priv_path = KEYS_DIR / f"{_KEY_NAME}_private.pem"
    if not priv_path.exists():
        generate_ed25519_keypair(_KEY_NAME)
    return load_private_key(_KEY_NAME)


def sign_payload(payload: dict) -> str:
    return sign(payload, ensure_keypair())


def public_key_pem() -> str:
    ensure_keypair()
    return (KEYS_DIR / f"{_KEY_NAME}_public.pem").read_text()
