import os
import threading
import time

import pytest
from werkzeug.serving import make_server

import client
from conftest import mine_block, signed
from chain.blockchain import Blockchain, chain_work
from chain.wallet import Wallet
from node import Node, create_app


class Running:
    def __init__(self, port, peers=(), chain=None):
        self.node = Node(port, None, peers)
        if chain is not None:
            self.node.chain = chain
        self.srv = make_server("127.0.0.1", port, create_app(self.node), threaded=True)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = self.node.url

    def stop(self):
        self.srv.shutdown()


def wait(cond, timeout=10):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def pair():
    a, b = Running(5301), Running(5302)
    a.node.add_peer(b.url)
    yield a, b
    a.stop(); b.stop()


def test_block_and_tx_propagate_between_nodes(pair):
    a, b = pair
    alice, bob = Wallet.generate(), Wallet.generate()
    client.mine(a.url, alice.address)
    assert wait(lambda: b.node.chain.height == 1)
    client.send(a.url, alice, bob.address, 10)
    assert wait(lambda: len(b.node.mempool) == 1)
    client.mine(b.url, bob.address)
    assert wait(lambda: a.node.chain.height == 2 and len(a.node.mempool) == 0)
    assert a.node.chain.tip.hash() == b.node.chain.tip.hash()
    assert a.node.chain.balance(bob.address) == 10 + 50 + 1


def test_offline_node_catches_up_after_sync(pair):
    a, b = pair
    alice = Wallet.generate()
    client.api(b.url, "POST", "/network", json={"online": False})
    for _ in range(3):
        client.mine(a.url, alice.address)
    time.sleep(0.5)
    assert b.node.chain.height == 0
    client.api(b.url, "POST", "/network", json={"online": True})
    info = client.api(b.url, "POST", "/sync")
    assert info["replaced"] and b.node.chain.height == 3


def test_node_rejects_invalid_peer_chain(pair):
    a, b = pair
    alice = Wallet.generate()
    for _ in range(3):
        mine_block(a.node.chain, alice)
    forged = Blockchain(list(a.node.chain.blocks))
    forged.blocks[2].transactions[0].amount = 999999            # шахрай міняє винагороду в старому блоці
    b.node.chain = Blockchain()
    a.node.chain = forged                                       # вузол A тепер роздає підроблений ланцюг
    assert b.node.sync()["replaced"] is False
    assert b.node.chain.height == 0


def test_heavier_chain_wins_even_if_shorter():
    miner = Wallet.generate()
    slow = Blockchain()
    ts = slow.tip.timestamp
    for _ in range(10):
        ts += 100_000                                           # повільні блоки → складність падає
        mine_block(slow, miner, ts=ts)
    fast = Blockchain()
    ts = fast.tip.timestamp
    for _ in range(7):
        ts += 100                                               # швидкі блоки → складність росте
        mine_block(fast, miner, ts=ts)
    assert fast.height < slow.height and chain_work(fast.blocks) > chain_work(slow.blocks)
    x, y = Running(5311, chain=slow), Running(5312, chain=fast)
    try:
        x.node.add_peer(y.url, reciprocal=False)
        info = x.node.sync()
        assert info["replaced"] and x.node.chain.height == 7
    finally:
        x.stop(); y.stop()


def test_orphaned_transactions_return_to_mempool():
    alice, bob, carol = Wallet.generate(), Wallet.generate(), Wallet.generate()
    base = Blockchain()
    for _ in range(2):
        mine_block(base, alice)
        mine_block(base, bob)
    mine_block(base, alice); mine_block(base, bob)
    left = Blockchain(list(base.blocks))
    right = Blockchain(list(base.blocks))
    tx_left = signed(alice, carol.address, 10, 1, 0)
    mine_block(left, alice, [tx_left])
    mine_block(right, bob, [signed(bob, carol.address, 5, 1, 0)])
    mine_block(right, bob)
    node = Node(5399)
    node.chain = left
    ok, _ = node.mempool.add(signed(alice, carol.address, 1, 1, 1), left)   # ще одна, у мемпулі
    assert ok
    info = node.replace_chain(right)
    assert info["replaced"] and info["orphaned_blocks"] == 1
    assert tx_left.tx_id() in node.mempool and info["txs_returned_to_mempool"] == 1


def test_light_client_verifies_inclusion(pair):
    from light_client import LightClient
    a, _ = pair
    alice, bob = Wallet.generate(), Wallet.generate()
    client.mine(a.url, alice.address)
    r = client.send(a.url, alice, bob.address, 10)
    client.mine(a.url, alice.address)
    lc = LightClient(a.url)
    assert lc.sync_headers() == 3
    assert lc.verify_tx(r["tx_id"]) == 2
    assert lc.verify_tx("00" * 32) is None
