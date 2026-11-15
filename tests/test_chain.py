import copy

import pytest

from conftest import mine_block, signed
from chain import config
from chain.block import Block
from chain.blockchain import (Blockchain, ChainError, State, apply_transactions, chain_work,
                              expected_difficulty)
from chain.merkle import merkle_root
from chain.transaction import make_coinbase


def test_miner_gets_reward_plus_fees(funded):
    chain, alice, bob, carol = funded
    mine_block(chain, carol, [signed(alice, bob.address, 10, 3, 0), signed(alice, bob.address, 5, 2, 1)])
    assert chain.balance(carol.address) == config.BLOCK_REWARD + 5
    assert chain.balance(bob.address) == 15
    assert chain.balance(alice.address) == 150 - 15 - 5


def test_state_matches_balance_scan(funded):
    chain, alice, bob, carol = funded
    mine_block(chain, bob, [signed(alice, carol.address, 40, 1, 0)])
    mine_block(chain, alice, [signed(carol, bob.address, 7, 1, 0)])
    for w in (alice, bob, carol):
        assert chain.balance(w.address) == chain.balance_by_scan(w.address)


def test_valid_chain_validates(funded):
    assert funded[0].validate() == (True, "")


def test_changed_amount_in_old_block_is_detected(funded):
    chain, alice, bob, _ = funded
    mine_block(chain, alice, [signed(alice, bob.address, 20, 1, 0)])
    mine_block(chain, alice)
    chain.blocks[4].transactions[1].amount = 2000
    ok, reason = chain.validate()
    assert not ok and "Меркла" in reason


def test_remined_block_breaks_link_to_next(funded):
    chain, alice, bob, _ = funded
    mine_block(chain, alice, [signed(alice, bob.address, 20, 1, 0)])
    mine_block(chain, alice)
    blocks = copy.deepcopy(chain.blocks)
    blocks[4].transactions[1] = signed(alice, bob.address, 1, 1, 0)
    blocks[4].merkle_root = blocks[4].compute_merkle_root()
    blocks[4].mine()
    assert Blockchain.from_blocks(blocks[:5])             # сам по собі блок 4 коректний
    with pytest.raises(ChainError, match="prev_hash"):
        Blockchain.from_blocks(blocks)


def test_inflated_coinbase_rejected(funded):
    chain, alice, _, _ = funded
    b = chain.build_block(alice.address, [])
    b.transactions[0] = make_coinbase(alice.address, 1000, b.index)
    b.merkle_root = b.compute_merkle_root()
    b.mine()
    with pytest.raises(ChainError, match="винагород"):
        chain.add_block(b)


def test_double_spend_in_one_block_rejected(funded):
    chain, alice, bob, carol = funded
    b = chain.build_block(bob.address, [signed(alice, bob.address, 100, 1, 0), signed(alice, carol.address, 100, 1, 1)])
    b.mine()
    with pytest.raises(ChainError, match="недостатньо коштів"):
        chain.add_block(b)


def test_replay_rejected_by_nonce_even_without_tx_history(funded):
    chain, alice, bob, _ = funded
    tx = signed(alice, bob.address, 10, 1, 0)
    mine_block(chain, alice, [tx])
    state = State()
    state.balances, state.nonces = dict(chain.state.balances), dict(chain.state.nonces)   # tx_id не передаємо
    with pytest.raises(ChainError, match="nonce"):
        apply_transactions(state, chain.build_block(alice.address, [tx]))


def test_replay_rejected_as_duplicate(funded):
    chain, alice, bob, _ = funded
    tx = signed(alice, bob.address, 10, 1, 0)
    mine_block(chain, alice, [tx])
    b = chain.build_block(alice.address, [tx]); b.mine()
    with pytest.raises(ChainError, match="дублікат"):
        chain.add_block(b)


def test_block_with_wrong_difficulty_rejected(funded):
    chain, alice, _, _ = funded
    b = chain.build_block(alice.address, [])
    b.difficulty = 4
    b.mine()
    with pytest.raises(ChainError, match="складність"):
        chain.add_block(b)


def _chain_with_spacing(spacing_ms, n):
    chain = Blockchain()
    w = chain.tip
    from chain.wallet import Wallet
    miner = Wallet.generate()
    ts = chain.tip.timestamp
    for _ in range(n):
        ts += spacing_ms
        mine_block(chain, miner, ts=ts)
    return chain


def test_difficulty_rises_when_blocks_are_fast():
    chain = _chain_with_spacing(100, config.ADJUST_INTERVAL)      # блоки приходять у 100 разів швидше за ціль
    assert chain.next_difficulty() == config.INITIAL_DIFFICULTY + config.MAX_ADJUST_STEP


def test_difficulty_falls_when_blocks_are_slow():
    chain = _chain_with_spacing(100_000, config.ADJUST_INTERVAL)
    assert chain.next_difficulty() == config.INITIAL_DIFFICULTY - config.MAX_ADJUST_STEP


def test_difficulty_unchanged_when_on_target():
    chain = _chain_with_spacing(int(config.TARGET_BLOCK_TIME * 1000), config.ADJUST_INTERVAL)
    assert chain.next_difficulty() == config.INITIAL_DIFFICULTY


def test_difficulty_stays_between_blocks_of_a_window():
    chain = _chain_with_spacing(100, config.ADJUST_INTERVAL - 2)
    assert chain.next_difficulty() == config.INITIAL_DIFFICULTY


def test_save_and_load_roundtrip(funded, tmp_path):
    chain, alice, bob, _ = funded
    mine_block(chain, alice, [signed(alice, bob.address, 10, 1, 0)])
    p = str(tmp_path / "chain.json")
    chain.save(p)
    loaded = Blockchain.load(p)
    assert loaded.tip.hash() == chain.tip.hash() and loaded.balance(bob.address) == 10


def test_tampered_file_is_refused(funded, tmp_path):
    import json
    chain, alice, bob, _ = funded
    mine_block(chain, alice, [signed(alice, bob.address, 10, 1, 0)])
    p = str(tmp_path / "chain.json")
    chain.save(p)
    data = json.load(open(p))
    data["blocks"][-1]["transactions"][1]["amount"] = 9
    json.dump(data, open(p, "w"))
    with pytest.raises(ChainError):
        Blockchain.load(p)


def test_block_hash_changes_with_any_header_field(funded):
    chain, _, _, _ = funded
    b = chain.tip
    base = b.hash()
    for field, val in (("timestamp", b.timestamp + 1), ("nonce", b.nonce + 1), ("difficulty", b.difficulty + 1),
                       ("prev_hash", "f" * 64), ("merkle_root", "e" * 64)):
        c = copy.deepcopy(b)
        setattr(c, field, val)
        assert c.hash() != base, field
