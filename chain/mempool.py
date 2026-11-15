"""Черга непідтверджених транзакцій із чотирма перевірками."""
from collections import OrderedDict

from . import config
from .transaction import Transaction


class Mempool:
    def __init__(self):
        self.txs = OrderedDict()   # tx_id -> Transaction, у порядку надходження

    def __len__(self):
        return len(self.txs)

    def __contains__(self, tx_id):
        return tx_id in self.txs

    def pending_of(self, sender: str) -> list:
        return [t for t in self.txs.values() if t.sender == sender]

    def next_nonce(self, chain, sender: str) -> int:
        return chain.next_nonce(sender) + len(self.pending_of(sender))

    def add(self, tx: Transaction, chain):
        """Повертає (True, '') або (False, причина). Перевірки: підпис, дублікат, nonce, баланс."""
        try:
            tx.check_structure()
        except ValueError as e:
            return False, f"некоректна транзакція: {e}"
        if tx.is_coinbase():
            return False, "винагороду майнеру не можна надсилати в мемпул"
        # 1. підпис
        if not tx.verify_signature():
            return False, "недійсний підпис"
        # 2. дублікат (у черзі або вже в ланцюгу)
        tid = tx.tx_id()
        if tid in self.txs:
            return False, "дублікат: така транзакція вже є в черзі"
        if tid in chain.state.tx_ids:
            return False, "дублікат: така транзакція вже підтверджена в ланцюгу"
        # 3. nonce має бути наступним за підтвердженими і вже очікуваними транзакціями цього відправника
        expected = self.next_nonce(chain, tx.sender)
        if tx.nonce != expected:
            return False, f"неправильний nonce: очікувався {expected}, отримано {tx.nonce}"
        # 4. баланс з урахуванням тих витрат відправника, що вже чекають у черзі
        reserved = sum(t.amount + t.fee for t in self.pending_of(tx.sender))
        available = chain.balance(tx.sender) - reserved
        if available < tx.amount + tx.fee:
            return False, f"недостатньо коштів: доступно {available}, потрібно {tx.amount + tx.fee}"
        self.txs[tid] = tx
        return True, ""

    def select_for_block(self, chain, limit: int = config.MAX_TXS_PER_BLOCK) -> list:
        """Бере транзакції в порядку надходження (він зберігає порядок nonce кожного відправника)."""
        return list(self.txs.values())[:limit]

    def remove_confirmed(self, block) -> None:
        for tx in block.transactions:
            self.txs.pop(tx.tx_id(), None)

    def rebuild(self, chain, extra_first: list = ()) -> int:
        """Після зміни ланцюга заново перевіряє всі транзакції проти нового стану.
        `extra_first` — транзакції з відкинутих блоків: вони йдуть першими, щоб не втратитись.
        Повертає, скільки транзакцій з extra_first повернулося в чергу."""
        old = list(self.txs.values())
        self.txs = OrderedDict()
        returned = 0
        for tx in extra_first:
            if self.add(tx, chain)[0]:
                returned += 1
        for tx in old:
            self.add(tx, chain)
        return returned
