import hashlib

import pytest

from chain.merkle import merkle_proof, merkle_root, verify_proof


def leaf(i):
    return hashlib.sha256(str(i).encode()).hexdigest()


def h(a, b):
    return hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()


def test_single_leaf_is_root():
    assert merkle_root([leaf(1)]) == leaf(1)


def test_two_leaves():
    assert merkle_root([leaf(1), leaf(2)]) == h(leaf(1), leaf(2))


def test_odd_count_duplicates_last():
    assert merkle_root([leaf(1), leaf(2), leaf(3)]) == h(h(leaf(1), leaf(2)), h(leaf(3), leaf(3)))


def test_empty_list_has_defined_root():
    assert merkle_root([]) == hashlib.sha256(b"").hexdigest()


def test_changing_any_leaf_changes_root():
    leaves = [leaf(i) for i in range(5)]
    base = merkle_root(leaves)
    for i in range(5):
        changed = list(leaves)
        changed[i] = leaf(100 + i)
        assert merkle_root(changed) != base


def test_order_matters():
    assert merkle_root([leaf(1), leaf(2)]) != merkle_root([leaf(2), leaf(1)])


@pytest.mark.parametrize("n", range(1, 10))
def test_proofs_verify_for_every_leaf(n):
    leaves = [leaf(i) for i in range(n)]
    root = merkle_root(leaves)
    for i in range(n):
        assert verify_proof(leaves[i], merkle_proof(leaves, i), root)


def test_wrong_leaf_or_tampered_proof_fails():
    leaves = [leaf(i) for i in range(6)]
    root = merkle_root(leaves)
    proof = merkle_proof(leaves, 2)
    assert not verify_proof(leaf(99), proof, root)
    bad = [(leaf(7), proof[0][1])] + proof[1:]
    assert not verify_proof(leaves[2], bad, root)
