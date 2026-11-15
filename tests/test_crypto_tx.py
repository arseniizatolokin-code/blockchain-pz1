from conftest import signed
from chain import crypto
from chain.transaction import Transaction, make_coinbase


def test_address_is_hash_of_pubkey(wallets):
    a, _, _ = wallets
    assert a.address == crypto.sha256_hex(bytes.fromhex(a.public_key_hex))[:40]


def test_valid_signature_passes(wallets):
    a, b, _ = wallets
    assert signed(a, b.address, 10, 1, 0).verify_signature()


def test_changed_amount_breaks_signature(wallets):
    a, b, _ = wallets
    tx = signed(a, b.address, 10, 1, 0)
    tx.amount = 1000
    assert not tx.verify_signature()


def test_foreign_key_does_not_match_address(wallets):
    a, b, m = wallets
    tx = Transaction(a.address, m.address, 10, 1, 0)
    tx.sign(m)                                   # підписав чужий гаманець, але sender = адреса Alice
    assert not tx.verify_signature()


def test_serialization_is_deterministic(wallets):
    a, b, _ = wallets
    tx = signed(a, b.address, 10, 1, 0)
    shuffled = dict(reversed(list(tx.to_dict().items())))
    assert crypto.canonical_json(shuffled) == crypto.canonical_json(tx.to_dict())
    assert Transaction.from_dict(shuffled).tx_id() == tx.tx_id()


def test_structure_rejects_bad_values(wallets):
    a, b, _ = wallets
    for amount in (0, -5, True, 1.5):
        tx = signed(a, b.address, 10, 1, 0)
        tx.amount = amount
        try:
            tx.check_structure()
            assert False, amount
        except ValueError:
            pass


def test_coinbase_ids_differ_by_height(wallets):
    a, _, _ = wallets
    assert make_coinbase(a.address, 50, 1).tx_id() != make_coinbase(a.address, 50, 2).tx_id()
