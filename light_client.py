"""Додаткове завдання: легкий клієнт (SPV). Хоче знати, чи є транзакція в ланцюгу, але не завантажує
блоки повністю — лише заголовки та доказ Меркла (log2(N) хешів замість усіх транзакцій блоку)."""
import sys

import client
from chain.block import BlockHeader, meets_difficulty
from chain.blockchain import expected_difficulty
from chain.merkle import verify_proof
from chain.transaction import Transaction


class LightClient:
    def __init__(self, node: str):
        self.node = node
        self.headers = []

    def sync_headers(self) -> int:
        """Завантажує заголовки й перевіряє зв'язки, Proof of Work та правило складності."""
        raw = client.api(self.node, "GET", "/headers")["headers"]
        headers = [BlockHeader(h["index"], h["timestamp"], h["prev_hash"], h["merkle_root"], h["difficulty"], h["nonce"]) for h in raw]
        for i in range(1, len(headers)):
            h, prev = headers[i], headers[i - 1]
            if h.prev_hash != prev.hash():
                raise ValueError(f"заголовок {i}: розірваний зв'язок")
            if not meets_difficulty(h.hash(), h.difficulty):
                raise ValueError(f"заголовок {i}: недійсний Proof of Work")
            if h.difficulty != expected_difficulty(headers, i):
                raise ValueError(f"заголовок {i}: неправильна складність")
        self.headers = headers
        return len(headers)

    def verify_tx(self, tx_id: str):
        """Повертає номер блоку, якщо вузол довів входження транзакції в корінь Меркла заголовка."""
        r = client.api(self.node, "GET", f"/proof/{tx_id}")
        if "error" in r:
            return None
        tx = Transaction.from_dict(r["tx"])
        if tx.tx_id() != tx_id:
            return None                      # вузол підсунув іншу транзакцію
        idx = r["block_index"]
        if idx >= len(self.headers):
            return None
        return idx if verify_proof(tx_id, [tuple(p) for p in r["proof"]], self.headers[idx].merkle_root) else None


if __name__ == "__main__":
    node, txid = sys.argv[1], sys.argv[2]
    lc = LightClient(node)
    print("заголовків перевірено:", lc.sync_headers())
    blk = lc.verify_tx(txid)
    print(f"транзакція підтверджена в блоці {blk}" if blk is not None else "транзакцію підтвердити не вдалося")
