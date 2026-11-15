"""Гаманець: пара ключів Ed25519. Приватний ключ ніколи не покидає клієнта і не потрапляє на вузол."""
import json
import os

from . import crypto


class Wallet:
    def __init__(self, private_key):
        self._key = private_key
        self.public_key_hex = crypto.public_hex(private_key)
        self.address = crypto.address_from_pubkey(self.public_key_hex)

    @classmethod
    def generate(cls) -> "Wallet":
        return cls(crypto.generate_private_key())

    def sign(self, message: bytes) -> str:
        return self._key.sign(message).hex()

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump({"private_key": crypto.private_to_hex(self._key), "address": self.address}, f)
        os.chmod(path, 0o600)

    @classmethod
    def load(cls, path: str) -> "Wallet":
        with open(path) as f:
            data = json.load(f)
        return cls(crypto.private_from_hex(data["private_key"]))
