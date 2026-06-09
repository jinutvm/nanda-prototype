import base64
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)

KEYS_DIR = Path(os.environ.get("KEYS_DIR", "./keys"))


def _private_path(name: str) -> Path:
    return KEYS_DIR / f"{name}_private.pem"


def _public_path(name: str) -> Path:
    return KEYS_DIR / f"{name}_public.pem"


def generate_ed25519_keypair(name: str) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate and persist an Ed25519 keypair under keys/{name}_*.pem."""
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    _private_path(name).write_bytes(
        private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    _public_path(name).write_bytes(
        public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    return private_key, public_key


def load_private_key(name: str) -> Ed25519PrivateKey:
    """Load keys/{name}_private.pem and return the private key object."""
    return load_pem_private_key(_private_path(name).read_bytes(), password=None)


def load_public_key(name: str) -> Ed25519PublicKey:
    """Load keys/{name}_public.pem and return the public key object."""
    return load_pem_public_key(_public_path(name).read_bytes())


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(payload: dict, private_key: Ed25519PrivateKey) -> str:
    """Sign canonical JSON of payload; return base64-encoded signature."""
    return base64.b64encode(private_key.sign(_canonical(payload))).decode()


def verify(payload: dict, signature_b64: str, public_key: Ed25519PublicKey) -> bool:
    """Verify a base64-encoded Ed25519 signature against canonical JSON of payload."""
    try:
        public_key.verify(base64.b64decode(signature_b64), _canonical(payload))
        return True
    except InvalidSignature:
        return False
