"""Ланцюг блоків, стан рахунків і повна перевірка всіх правил."""
import copy
import json
import math
import os

from . import config
from .block import Block, meets_difficulty, now_ms
from .merkle import merkle_root
from .transaction import Transaction, make_coinbase


class ChainError(Exception):
    """Порушено одне з правил ланцюга; у тексті — причина."""


class State:
    """Стан після застосування блоків: баланси, nonce-лічильники та вже бачені транзакції."""

    def __init__(self):
        self.balances = {}
        self.nonces = {}     # скільки транзакцій відправника вже підтверджено
        self.tx_ids = set()

    def copy(self) -> "State":
        s = State()
        s.balances = dict(self.balances)
        s.nonces = dict(self.nonces)
        s.tx_ids = set(self.tx_ids)
        return s


def work_of(difficulty: int) -> int:
    """Очікувана кількість спроб для блоку такої складності."""
    return 1 << difficulty


def expected_difficulty(blocks: list, index: int) -> int:
    """Складність, яку МАЄ мати блок з номером `index`, якщо перед ним лежать blocks[:index].
    Кожні K блоків дивимося, скільки часу пішло на останні K, і зсуваємо складність
    так, щоб середній час блоку наблизився до TARGET_BLOCK_TIME."""
    if index == 0:
        return config.INITIAL_DIFFICULTY
    prev = blocks[index - 1]
    k = config.ADJUST_INTERVAL
    if index % k != 0:
        return prev.difficulty
    window = blocks[max(index - k, 1):index]       # генезис у вікно не беремо: його час умовний
    intervals = len(window) - 1
    if intervals < 1:
        return prev.difficulty
    actual = max(window[-1].timestamp - window[0].timestamp, 1)
    expected = config.TARGET_BLOCK_TIME * 1000 * intervals
    shift = round(math.log2(expected / actual))
    shift = max(-config.MAX_ADJUST_STEP, min(config.MAX_ADJUST_STEP, shift))
    return max(config.MIN_DIFFICULTY, min(config.MAX_DIFFICULTY, prev.difficulty + shift))


def make_genesis() -> Block:
    """Генезис однаковий у всіх вузлів: усі поля фіксовані, nonce підбирається детерміновано."""
    b = Block(0, config.GENESIS_TIMESTAMP, "0" * 64, merkle_root([]), config.INITIAL_DIFFICULTY, 0, [])
    return b.mine()


def apply_transactions(state: State, block: Block) -> None:
    """Перевіряє всі транзакції блоку і змінює стан. Кидає ChainError при будь-якому порушенні."""
    txs = block.transactions
    if not txs or not txs[0].is_coinbase():
        raise ChainError("перша транзакція блоку має бути винагородою майнеру")
    fees = 0
    seen = set()
    for tx in txs[1:]:
        if tx.is_coinbase():
            raise ChainError("у блоці більше однієї винагороди майнеру")
        try:
            tx.check_structure()
        except ValueError as e:
            raise ChainError(f"транзакція {tx.tx_id()[:8]}: {e}")
        if not tx.verify_signature():
            raise ChainError(f"транзакція {tx.tx_id()[:8]}: недійсний підпис")
        tid = tx.tx_id()
        if tid in state.tx_ids or tid in seen:
            raise ChainError(f"транзакція {tid[:8]} уже була в ланцюгу (дублікат)")
        seen.add(tid)
        expected_nonce = state.nonces.get(tx.sender, 0)
        if tx.nonce != expected_nonce:
            raise ChainError(f"транзакція {tid[:8]}: неправильний nonce (очікувався {expected_nonce}, отримано {tx.nonce})")
        cost = tx.amount + tx.fee
        if state.balances.get(tx.sender, 0) < cost:
            raise ChainError(f"транзакція {tid[:8]}: недостатньо коштів (баланс {state.balances.get(tx.sender, 0)}, потрібно {cost})")
        state.balances[tx.sender] -= cost
        state.balances[tx.recipient] = state.balances.get(tx.recipient, 0) + tx.amount
        state.nonces[tx.sender] = expected_nonce + 1
        fees += tx.fee
    cb = txs[0]
    try:
        cb.check_structure()
    except ValueError as e:
        raise ChainError(f"винагорода майнеру: {e}")
    if cb.fee != 0 or cb.nonce != block.index:
        raise ChainError("некоректні поля винагороди майнеру")
    if cb.amount != config.BLOCK_REWARD + fees:
        raise ChainError(f"завищена винагорода майнеру: {cb.amount}, дозволено {config.BLOCK_REWARD + fees}")
    state.balances[cb.recipient] = state.balances.get(cb.recipient, 0) + cb.amount
    for tx in txs:
        state.tx_ids.add(tx.tx_id())
    # комісії переходять майнеру: вони вже вирахувані з відправників і входять до cb.amount


def check_and_apply(blocks: list, block: Block, state: State, now: int = None) -> None:
    """Повна перевірка одного блоку відносно ланцюга blocks (перед ним). Змінює state."""
    now = now_ms() if now is None else now
    prev = blocks[-1]
    if block.index != prev.index + 1:
        raise ChainError(f"блок {block.index}: неправильний номер, очікувався {prev.index + 1}")
    if block.prev_hash != prev.hash():
        raise ChainError(f"блок {block.index}: prev_hash не збігається з хешем попереднього блоку (зв'язок розірвано)")
    exp = expected_difficulty(blocks, block.index)
    if block.difficulty != exp:
        raise ChainError(f"блок {block.index}: складність {block.difficulty}, а за правилами має бути {exp}")
    if not meets_difficulty(block.hash(), block.difficulty):
        raise ChainError(f"блок {block.index}: хеш не задовольняє складність (Proof of Work недійсний)")
    if block.timestamp < prev.timestamp or block.timestamp > now + config.FUTURE_DRIFT_MS:
        raise ChainError(f"блок {block.index}: недопустима мітка часу")
    if len(block.transactions) > config.MAX_TXS_PER_BLOCK + 1:
        raise ChainError(f"блок {block.index}: забагато транзакцій")
    if block.merkle_root != block.compute_merkle_root():
        raise ChainError(f"блок {block.index}: корінь Меркла не збігається з транзакціями")
    apply_transactions(state, block)


class Blockchain:
    def __init__(self, blocks: list = None):
        """Без аргументів створює новий ланцюг із генезис-блоку. Зі списком блоків —
        повністю перевіряє його (ChainError, якщо хоч одне правило порушено)."""
        self.blocks = []
        self.state = State()
        if blocks is None:
            self.blocks = [make_genesis()]
        else:
            self._load_blocks(blocks)

    def _load_blocks(self, blocks: list) -> None:
        if not blocks:
            raise ChainError("порожній ланцюг")
        if blocks[0].hash() != make_genesis().hash() or blocks[0].transactions:
            raise ChainError("генезис-блок відрізняється від еталонного")
        state = State()
        for i in range(1, len(blocks)):
            check_and_apply(blocks[:i], blocks[i], state)
        self.blocks, self.state = list(blocks), state

    @classmethod
    def from_blocks(cls, blocks: list) -> "Blockchain":
        return cls(blocks)

    # ---- властивості ----
    @property
    def tip(self) -> Block:
        return self.blocks[-1]

    @property
    def height(self) -> int:
        return self.blocks[-1].index

    def total_work(self) -> int:
        return sum(work_of(b.difficulty) for b in self.blocks)

    def next_difficulty(self) -> int:
        return expected_difficulty(self.blocks, len(self.blocks))

    def balance(self, address: str) -> int:
        return self.state.balances.get(address, 0)

    def next_nonce(self, address: str) -> int:
        return self.state.nonces.get(address, 0)

    def balance_by_scan(self, address: str) -> int:
        """Баланс, порахований проходом по всіх блоках (для перехресної перевірки стану)."""
        total = 0
        for b in self.blocks:
            for tx in b.transactions:
                if tx.recipient == address:
                    total += tx.amount
                if tx.sender == address:
                    total -= tx.amount + tx.fee
        return total

    def find_tx(self, tx_id: str):
        for b in self.blocks:
            for pos, tx in enumerate(b.transactions):
                if tx.tx_id() == tx_id:
                    return b, pos
        return None

    # ---- зміни ----
    def add_block(self, block: Block) -> None:
        state = self.state.copy()
        check_and_apply(self.blocks, block, state)
        self.blocks.append(block)
        self.state = state

    def build_block(self, miner_address: str, txs: list, timestamp: int = None) -> Block:
        """Збирає блок-кандидат: винагорода майнеру (фіксована сума + усі комісії) + транзакції."""
        height = len(self.blocks)
        fees = sum(t.fee for t in txs)
        coinbase = make_coinbase(miner_address, config.BLOCK_REWARD + fees, height)
        all_txs = [coinbase] + list(txs)
        ts = max(now_ms() if timestamp is None else timestamp, self.tip.timestamp)
        block = Block(height, ts, self.tip.hash(), merkle_root([t.tx_id() for t in all_txs]),
                      self.next_difficulty(), 0, all_txs)
        return block

    def validate(self):
        """Повна перевірка ланцюга з нуля: (True, '') або (False, причина).
        Стан не береться зі збережених лічильників — його відтворюємо заново по блоках."""
        try:
            Blockchain._check_all(self.blocks)
            return True, ""
        except ChainError as e:
            return False, str(e)

    @staticmethod
    def _check_all(blocks: list) -> None:
        if not blocks:
            raise ChainError("порожній ланцюг")
        if blocks[0].hash() != make_genesis().hash() or blocks[0].transactions:
            raise ChainError("генезис-блок відрізняється від еталонного")
        state = State()
        for i in range(1, len(blocks)):
            check_and_apply(blocks[:i], blocks[i], state)

    # ---- файл ----
    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"blocks": [b.to_dict() for b in self.blocks]}, f)
        os.replace(tmp, path)       # атомарно: файл ніколи не лишиться напівзаписаним

    @classmethod
    def load(cls, path: str) -> "Blockchain":
        with open(path) as f:
            data = json.load(f)
        return cls([Block.from_dict(b) for b in data["blocks"]])


def common_prefix_len(a: list, b: list) -> int:
    """Скільки перших блоків збігаються (за хешем) у двох ланцюгів, тобто де відбулося розгалуження."""
    n = 0
    for x, y in zip(a, b):
        if x.hash() != y.hash():
            break
        n += 1
    return n


def chain_work(blocks: list) -> int:
    return sum(work_of(b.difficulty) for b in blocks)
