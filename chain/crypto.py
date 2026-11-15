"""Хешування, адреси та цифровий підпис Ed25519 (готова бібліотека лише для примітивів)."""
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj) -> bytes:
    """Детермінована серіалізація: відсортовані ключі, без пробілів, лише ASCII.
    Ті самі дані завжди дають ті самі байти на будь-якому вузлі."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def address_from_pubkey(pubkey_hex: str) -> str:
    """Адреса = перші 20 байтів (40 hex-символів) SHA-256 від публічного ключа."""
    return sha256_hex(bytes.fromhex(pubkey_hex))[:40]


def generate_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def private_to_hex(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return raw.hex()


def private_from_hex(h: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(h))


def public_hex(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return raw.hex()


def verify_signature(pubkey_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex)).verify(
            bytes.fromhex(signature_hex), message
        )
        return True
    except (InvalidSignature, ValueError):
        return False
