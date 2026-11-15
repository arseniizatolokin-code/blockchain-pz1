"""Блок: заголовок + список транзакцій. Хеш блоку = SHA-256 від заголовка."""
import hashlib
import time
from dataclasses import dataclass, field

from .merkle import merkle_root
from .transaction import Transaction


def header_bytes(index: int, timestamp: int, prev_hash: str, merkle: str, difficulty: int, nonce: int) -> bytes:
    """Детермінована серіалізація заголовка: фіксований порядок полів, розділювач '|'."""
    return f"{index}|{timestamp}|{prev_hash}|{merkle}|{difficulty}|{nonce}".encode("ascii")


def meets_difficulty(block_hash: str, difficulty: int) -> bool:
    """Хеш задовольняє складність, якщо його перші `difficulty` бітів нульові."""
    return int(block_hash, 16) >> (256 - difficulty) == 0


@dataclass
class BlockHeader:
    index: int
    timestamp: int      # мілісекунди
    prev_hash: str
    merkle_root: str
    difficulty: int
    nonce: int

    def hash(self) -> str:
        return hashlib.sha256(
            header_bytes(self.index, self.timestamp, self.prev_hash, self.merkle_root, self.difficulty, self.nonce)
        ).hexdigest()

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["hash"] = self.hash()
        return d


@dataclass
class Block:
    index: int
    timestamp: int
    prev_hash: str
    merkle_root: str
    difficulty: int
    nonce: int
    transactions: list = field(default_factory=list)

    def header(self) -> BlockHeader:
        return BlockHeader(self.index, self.timestamp, self.prev_hash, self.merkle_root, self.difficulty, self.nonce)

    def hash(self) -> str:
        # хеш завжди рахується заново, а не береться зі збереженого поля,
        # тому будь-яка підміна даних помітна одразу
        return self.header().hash()

    def compute_merkle_root(self) -> str:
        return merkle_root([tx.tx_id() for tx in self.transactions])

    def mine(self) -> "Block":
        """Підбираємо nonce, поки хеш заголовка не стане меншим за ціль (Proof of Work)."""
        prefix = f"{self.index}|{self.timestamp}|{self.prev_hash}|{self.merkle_root}|{self.difficulty}|".encode("ascii")
        base = hashlib.sha256(prefix)
        target = (1 << (256 - self.difficulty)).to_bytes(32, "big")
        nonce = 0
        while True:
            h = base.copy()
            h.update(str(nonce).encode("ascii"))
            if h.digest() < target:
                self.nonce = nonce
                return self
            nonce += 1

    def to_dict(self) -> dict:
        d = self.header().to_dict()
        d["transactions"] = [tx.to_dict() for tx in self.transactions]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        try:
            return cls(
                index=d["index"],
                timestamp=d["timestamp"],
                prev_hash=d["prev_hash"],
                merkle_root=d["merkle_root"],
                difficulty=d["difficulty"],
                nonce=d["nonce"],
                transactions=[Transaction.from_dict(t) for t in d["transactions"]],
            )
        except (KeyError, TypeError) as e:
            raise ValueError(f"некоректний блок: {e}")


def now_ms() -> int:
    return int(time.time() * 1000)
