"""Вузол мережі: HTTP API (Flask), мемпул, сусіди, розсилка, вибір найважчого ланцюга."""
import argparse
import logging
import os
import threading

import requests
from flask import Flask, jsonify, request

from chain import config
from chain.block import Block
from chain.blockchain import Blockchain, ChainError, chain_work, common_prefix_len
from chain.mempool import Mempool
from chain.merkle import merkle_proof
from chain.transaction import Transaction


class Node:
    def __init__(self, port: int, data_path: str = None, peers=()):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.data_path = data_path
        self.peers = set(peers)
        self.online = True              # імітація розриву мережі
        self.lock = threading.RLock()
        self.mempool = Mempool()
        self.last_reorg = None
        self.chain = self._load_chain()

    def log(self, msg: str) -> None:
        print(f"[вузол {self.port}] {msg}", flush=True)

    def _load_chain(self) -> Blockchain:
        if self.data_path and os.path.exists(self.data_path):
            try:
                chain = Blockchain.load(self.data_path)
                self.log(f"ланцюг завантажено з диска, висота {chain.height}")
                return chain
            except (ChainError, ValueError, KeyError) as e:
                os.replace(self.data_path, self.data_path + ".corrupt")
                self.log(f"файл ланцюга пошкоджено ({e}); починаю з генезису")
        return Blockchain()

    def _save(self) -> None:
        if self.data_path:
            self.chain.save(self.data_path)

    # ---- мережа ----
    def _post(self, peer: str, path: str, payload: dict):
        try:
            return requests.post(peer + path, json=payload, headers={"X-Peer": "1"}, timeout=3)
        except requests.RequestException:
            return None

    def broadcast(self, path: str, payload: dict) -> None:
        if not self.online:
            return
        for p in list(self.peers):
            threading.Thread(target=self._post, args=(p, path, payload), daemon=True).start()

    def add_peer(self, url: str, reciprocal: bool = True) -> None:
        url = url.rstrip("/")
        if url == self.url or url in self.peers:
            return
        self.peers.add(url)
        self.log(f"додано сусіда {url}")
        if reciprocal:
            self._post(url, "/peers", {"url": self.url, "reciprocal": False})

    # ---- транзакції та блоки ----
    def receive_tx(self, tx: Transaction):
        with self.lock:
            ok, reason = self.mempool.add(tx, self.chain)
        if ok:
            self.log(f"транзакцію {tx.tx_id()[:8]} прийнято в мемпул")
            self.broadcast("/transactions", tx.to_dict())
        elif not reason.startswith("дублікат"):      # відлуння розсилки від сусідів не логуємо
            self.log(f"транзакцію {tx.tx_id()[:8]} відхилено: {reason}")
        return ok, reason

    def mine(self, miner_address: str):
        with self.lock:
            txs = self.mempool.select_for_block(self.chain)
            block = self.chain.build_block(miner_address, txs)
        block.mine()                    # довга робота — поза блокуванням
        with self.lock:
            if block.prev_hash != self.chain.tip.hash():
                self.log("під час майнінгу прийшов новий блок, свій відкидаю")
                return None
            self.chain.add_block(block)
            self.mempool.remove_confirmed(block)
            self._save()
        self.log(f"замайнено блок {block.index} {block.hash()[:12]}… (складність {block.difficulty}, транзакцій {len(block.transactions) - 1})")
        self.broadcast("/blocks", block.to_dict())
        return block

    def receive_block(self, block: Block) -> str:
        with self.lock:
            tip = self.chain.tip
            if block.hash() == tip.hash() or any(b.hash() == block.hash() for b in self.chain.blocks[-20:]):
                return "known"
            if block.index == tip.index + 1 and block.prev_hash == tip.hash():
                try:
                    self.chain.add_block(block)
                except ChainError as e:
                    self.log(f"блок {block.index} відхилено: {e}")
                    return f"rejected: {e}"
                self.mempool.remove_confirmed(block)
                self.mempool.rebuild(self.chain)
                self._save()
                self.log(f"прийнято блок {block.index} {block.hash()[:12]}…")
                self.broadcast("/blocks", block.to_dict())
                return "accepted"
            behind = block.index >= tip.index
        if behind:
            # блок не продовжує наш ланцюг: можливо, ми відстали або це чужа гілка
            threading.Thread(target=self.sync, daemon=True).start()
            return "sync"
        return "ignored"

    def sync(self) -> dict:
        """Запитує ланцюги сусідів, повністю перевіряє кожен і бере той, у якому найбільше роботи."""
        best, best_from = None, None
        for peer in list(self.peers):
            if not self.online:
                break
            try:
                r = requests.get(peer + "/chain", headers={"X-Peer": "1"}, timeout=5)
                blocks = [Block.from_dict(b) for b in r.json()["blocks"]]
            except (requests.RequestException, ValueError, KeyError):
                continue
            if chain_work(blocks) <= (chain_work(best.blocks) if best else self.chain.total_work()):
                continue
            try:
                candidate = Blockchain.from_blocks(blocks)       # повна перевірка
            except ChainError as e:
                self.log(f"ланцюг від {peer} відхилено: {e}")
                continue
            best, best_from = candidate, peer
        if best is None:
            return {"replaced": False}
        return self.replace_chain(best, best_from)

    def replace_chain(self, new_chain: Blockchain, source: str = "") -> dict:
        with self.lock:
            old = self.chain.blocks
            fork = common_prefix_len(old, new_chain.blocks)
            orphaned = old[fork:]
            orphan_txs = [tx for b in orphaned for tx in b.transactions if not tx.is_coinbase()]
            self.chain = new_chain
            returned = self.mempool.rebuild(new_chain, orphan_txs)
            self._save()
            info = {
                "replaced": True,
                "from": source,
                "old_height": old[-1].index,
                "new_height": new_chain.height,
                "fork_after_block": fork - 1,
                "orphaned_blocks": len(orphaned),
                "txs_returned_to_mempool": returned,
            }
            self.last_reorg = info
        self.log(f"РЕОРГАНІЗАЦІЯ: висота {info['old_height']} → {info['new_height']}, "
                 f"розгалуження після блоку {info['fork_after_block']}, відкинуто блоків {info['orphaned_blocks']}, "
                 f"транзакцій повернуто в мемпул {returned}")
        return info


def create_app(node: Node) -> Flask:
    app = Flask(__name__)

    @app.before_request
    def offline_guard():
        if not node.online and request.headers.get("X-Peer"):
            return jsonify(error="вузол відключено від мережі"), 503

    @app.get("/status")
    def status():
        c = node.chain
        return jsonify(url=node.url, height=c.height, tip=c.tip.hash(), work=c.total_work(),
                       difficulty=c.next_difficulty(), mempool=len(node.mempool),
                       peers=sorted(node.peers), online=node.online, last_reorg=node.last_reorg)

    @app.get("/chain")
    def get_chain():
        return jsonify(height=node.chain.height, work=node.chain.total_work(),
                       blocks=[b.to_dict() for b in node.chain.blocks])

    @app.get("/headers")
    def headers():
        return jsonify(headers=[b.header().to_dict() for b in node.chain.blocks])

    @app.get("/mempool")
    def mempool():
        return jsonify(transactions=[t.to_dict() | {"tx_id": t.tx_id()} for t in node.mempool.txs.values()])

    @app.post("/transactions")
    def post_tx():
        try:
            tx = Transaction.from_dict(request.get_json(force=True))
        except (ValueError, TypeError) as e:
            return jsonify(ok=False, reason=str(e)), 400
        ok, reason = node.receive_tx(tx)
        return jsonify(ok=ok, reason=reason, tx_id=tx.tx_id()), (200 if ok else 400)

    @app.post("/mine")
    def mine():
        addr = (request.get_json(force=True) or {}).get("miner")
        if not isinstance(addr, str) or len(addr) != 40:
            return jsonify(ok=False, reason="потрібна адреса майнера"), 400
        block = node.mine(addr)
        if block is None:
            return jsonify(ok=False, reason="майнінг перервано новим блоком"), 409
        return jsonify(ok=True, block=block.to_dict())

    @app.post("/blocks")
    def post_block():
        try:
            block = Block.from_dict(request.get_json(force=True))
        except (ValueError, TypeError) as e:
            return jsonify(result=f"rejected: {e}"), 400
        return jsonify(result=node.receive_block(block))

    @app.get("/peers")
    def get_peers():
        return jsonify(peers=sorted(node.peers))

    @app.post("/peers")
    def post_peer():
        d = request.get_json(force=True)
        node.add_peer(d["url"], reciprocal=d.get("reciprocal", True))
        return jsonify(peers=sorted(node.peers))

    @app.post("/sync")
    def post_sync():
        return jsonify(node.sync())

    @app.post("/network")
    def network():
        node.online = bool(request.get_json(force=True)["online"])
        node.log("мережу " + ("підключено" if node.online else "ВІДКЛЮЧЕНО (вузол працює автономно)"))
        return jsonify(online=node.online)

    @app.get("/balance/<addr>")
    def balance(addr):
        reserved = sum(t.amount + t.fee for t in node.mempool.pending_of(addr))
        return jsonify(address=addr, balance=node.chain.balance(addr), available=node.chain.balance(addr) - reserved)

    @app.get("/nonce/<addr>")
    def nonce(addr):
        return jsonify(nonce=node.mempool.next_nonce(node.chain, addr))

    @app.get("/validate")
    def validate():
        ok, reason = node.chain.validate()
        return jsonify(valid=ok, reason=reason, height=node.chain.height)

    @app.get("/proof/<tx_id>")
    def proof(tx_id):
        found = node.chain.find_tx(tx_id)
        if not found:
            return jsonify(error="транзакцію не знайдено"), 404
        block, pos = found
        leaves = [t.tx_id() for t in block.transactions]
        return jsonify(block_index=block.index, tx=block.transactions[pos].to_dict(),
                       proof=merkle_proof(leaves, pos))

    return app


def main():
    ap = argparse.ArgumentParser(description="Вузол блокчейну")
    ap.add_argument("--port", type=int, default=5001)
    ap.add_argument("--data", default=None, help="файл для збереження ланцюга")
    ap.add_argument("--peers", default="", help="адреси сусідів через кому")
    a = ap.parse_args()
    data = a.data or os.path.join("data", f"node_{a.port}.json")
    node = Node(a.port, data, [p for p in a.peers.split(",") if p])
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    import flask.cli
    flask.cli.show_server_banner = lambda *args, **kwargs: None
    node.log(f"запущено на {node.url}, складність {config.INITIAL_DIFFICULTY} біт, K={config.ADJUST_INTERVAL}")
    create_app(node).run(host="127.0.0.1", port=a.port, threaded=True)


if __name__ == "__main__":
    main()
