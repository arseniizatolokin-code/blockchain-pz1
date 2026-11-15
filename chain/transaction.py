"""Транзакція: відправник, отримувач, сума, комісія, nonce, публічний ключ і підпис."""
import re
from dataclasses import dataclass

from . import crypto

COINBASE_SENDER = "COINBASE"
_ADDR = re.compile(r"^[0-9a-f]{40}$")
_PUB = re.compile(r"^[0-9a-f]{64}$")
_SIG = re.compile(r"^[0-9a-f]{128}$")
MAX_AMOUNT = 10 ** 12


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@dataclass
class Transaction:
    sender: str
    recipient: str
    amount: int
    fee: int
    nonce: int
    pubkey: str = ""      # потрібен вузлам для перевірки підпису; адреса відправника = хеш цього ключа
    signature: str = ""

    FIELDS = ("sender", "recipient", "amount", "fee", "nonce", "pubkey", "signature")

    def is_coinbase(self) -> bool:
        return self.sender == COINBASE_SENDER

    def signing_payload(self) -> bytes:
        """Що саме підписується: усі поля, крім самого підпису. Через це підпис
        не можна «переклеїти» на транзакцію з іншою сумою, отримувачем чи nonce."""
        return crypto.canonical_json(
            {
                "sender": self.sender,
                "recipient": self.recipient,
                "amount": self.amount,
                "fee": self.fee,
                "nonce": self.nonce,
                "pubkey": self.pubkey,
            }
        )

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        if not isinstance(d, dict) or set(d.keys()) != set(cls.FIELDS):
            raise ValueError("некоректний набір полів транзакції")
        return cls(**{k: d[k] for k in cls.FIELDS})

    def tx_id(self) -> str:
        """Ідентифікатор = SHA-256 від усієї транзакції разом з підписом."""
        return crypto.sha256_hex(crypto.canonical_json(self.to_dict()))

    def sign(self, wallet) -> None:
        self.pubkey = wallet.public_key_hex
        self.signature = wallet.sign(self.signing_payload())

    # ---- перевірки ----
    def check_structure(self) -> None:
        """Кидає ValueError з причиною, якщо поля мають неправильний тип чи формат."""
        for name in ("amount", "fee", "nonce"):
            if not _is_int(getattr(self, name)):
                raise ValueError(f"поле {name} має бути цілим числом")
        if not (0 < self.amount <= MAX_AMOUNT):
            raise ValueError("сума має бути додатною")
        if not (0 <= self.fee <= MAX_AMOUNT) or self.nonce < 0:
            raise ValueError("комісія та nonce не можуть бути від'ємними")
        if not isinstance(self.recipient, str) or not _ADDR.match(self.recipient):
            raise ValueError("некоректна адреса отримувача")
        if self.is_coinbase():
            return
        if not isinstance(self.sender, str) or not _ADDR.match(self.sender):
            raise ValueError("некоректна адреса відправника")
        if not isinstance(self.pubkey, str) or not _PUB.match(self.pubkey):
            raise ValueError("некоректний публічний ключ")
        if not isinstance(self.signature, str) or not _SIG.match(self.signature):
            raise ValueError("некоректний формат підпису")

    def verify_signature(self) -> bool:
        """Адреса має збігатися з хешем ключа, а підпис — з вмістом транзакції."""
        if crypto.address_from_pubkey(self.pubkey) != self.sender:
            return False
        return crypto.verify_signature(self.pubkey, self.signing_payload(), self.signature)


def make_coinbase(miner_address: str, amount: int, height: int) -> Transaction:
    """Транзакція-винагорода: створює нові монети, підпису не має.
    У nonce кладемо висоту блоку, щоб tx_id різних винагород не збігались."""
    return Transaction(COINBASE_SENDER, miner_address, amount, 0, height)
