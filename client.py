"""Клієнтська частина: підпис транзакцій та виклики API вузла."""
import os

import requests

from chain.transaction import Transaction
from chain.wallet import Wallet

WALLET_DIR = "wallets"


def wallet_path(name: str) -> str:
    return os.path.join(WALLET_DIR, f"{name}.json")


def load_wallet(name: str) -> Wallet:
    return Wallet.load(wallet_path(name))


def create_wallet(name: str) -> Wallet:
    if os.path.exists(wallet_path(name)):
        raise FileExistsError(f"гаманець {name} уже існує")
    w = Wallet.generate()
    w.save(wallet_path(name))
    return w


def api(node: str, method: str, path: str, **kw):
    r = requests.request(method, node.rstrip("/") + path, timeout=kw.pop("timeout", 120), **kw)
    return r.json()


def send(node: str, wallet: Wallet, to: str, amount: int, fee: int = 1) -> dict:
    nonce = api(node, "GET", f"/nonce/{wallet.address}")["nonce"]
    tx = Transaction(wallet.address, to, amount, fee, nonce)
    tx.sign(wallet)                      # підпис ставиться тут, приватний ключ на вузол не передається
    return api(node, "POST", "/transactions", json=tx.to_dict())


def mine(node: str, miner_address: str) -> dict:
    return api(node, "POST", "/mine", json={"miner": miner_address})
