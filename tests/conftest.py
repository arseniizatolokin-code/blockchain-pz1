import os
import sys

# малі параметри для швидких тестів; задаються до імпорту chain.config
os.environ["BC_DIFFICULTY"] = "8"
os.environ["BC_K"] = "5"
os.environ["BC_TARGET"] = "10"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from chain.blockchain import Blockchain
from chain.transaction import Transaction
from chain.wallet import Wallet


def mine_block(chain, miner, txs=(), ts=None):
    b = chain.build_block(miner.address if hasattr(miner, "address") else miner, list(txs), ts)
    b.mine()
    chain.add_block(b)
    return b


def signed(wallet, to, amount, fee, nonce):
    tx = Transaction(wallet.address, to, amount, fee, nonce)
    tx.sign(wallet)
    return tx


@pytest.fixture
def wallets():
    return Wallet.generate(), Wallet.generate(), Wallet.generate()


@pytest.fixture
def funded(wallets):
    """Ланцюг, де Alice вже замайнила 3 блоки (150 монет)."""
    alice, bob, carol = wallets
    chain = Blockchain()
    for _ in range(3):
        mine_block(chain, alice)
    return chain, alice, bob, carol
