from conftest import mine_block, signed
from chain import config
from chain.block import BlockHeader, meets_difficulty
from chain.blockchain import Blockchain, make_genesis
from chain.mempool import Mempool


def test_genesis_is_deterministic_and_valid():
    g1, g2 = make_genesis(), make_genesis()
    assert g1.hash() == g2.hash()
    assert meets_difficulty(g1.hash(), g1.difficulty)


def test_mined_block_meets_difficulty_and_nonce_matters(funded):
    chain, alice, _, _ = funded
    b = chain.build_block(alice.address, [])
    b.mine()
    assert meets_difficulty(b.hash(), b.difficulty)
    # перебираємо інші nonce: хоча б один із 1000 не задовольняє умову
    broken = 0
    for n in range(b.nonce + 1, b.nonce + 1000):
        other = BlockHeader(b.index, b.timestamp, b.prev_hash, b.merkle_root, b.difficulty, n)
        broken += not meets_difficulty(other.hash(), b.difficulty)
    assert broken > 900


def test_mempool_accepts_valid_tx(funded):
    chain, alice, bob, _ = funded
    ok, reason = Mempool().add(signed(alice, bob.address, 10, 1, 0), chain)
    assert ok, reason


def test_mempool_rejects_bad_signature(funded):
    chain, alice, bob, _ = funded
    tx = signed(alice, bob.address, 10, 1, 0)
    tx.amount = 11
    ok, reason = Mempool().add(tx, chain)
    assert not ok and "підпис" in reason


def test_mempool_rejects_duplicate(funded):
    chain, alice, bob, _ = funded
    m = Mempool()
    tx = signed(alice, bob.address, 10, 1, 0)
    assert m.add(tx, chain)[0]
    ok, reason = m.add(tx, chain)
    assert not ok and "дублікат" in reason


def test_mempool_rejects_wrong_nonce(funded):
    chain, alice, bob, _ = funded
    ok, reason = Mempool().add(signed(alice, bob.address, 10, 1, 5), chain)
    assert not ok and "nonce" in reason


def test_mempool_rejects_insufficient_funds(funded):
    chain, alice, bob, _ = funded
    ok, reason = Mempool().add(signed(alice, bob.address, 1000, 1, 0), chain)
    assert not ok and "недостатньо" in reason


def test_mempool_counts_pending_spending(funded):
    chain, alice, bob, _ = funded            # у Alice 150
    m = Mempool()
    assert m.add(signed(alice, bob.address, 100, 1, 0), chain)[0]
    ok, reason = m.add(signed(alice, bob.address, 100, 1, 1), chain)
    assert not ok and "недостатньо" in reason


def test_sequential_nonces_accepted_in_order(funded):
    chain, alice, bob, _ = funded
    m = Mempool()
    assert m.add(signed(alice, bob.address, 10, 1, 0), chain)[0]
    assert m.add(signed(alice, bob.address, 10, 1, 1), chain)[0]
