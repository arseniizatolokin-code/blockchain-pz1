"""Додаткове завдання: атака 51 %.
Частина 1 — на справжньому коді: атакувальник приховано майнить довшу гілку й переписує історію (подвійна витрата).
Частина 2 — Монте-Карло: ймовірність успіху залежно від частки потужності q та кількості підтверджень z."""
import math
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from chain.blockchain import Blockchain, common_prefix_len
from chain.mempool import Mempool
from chain.transaction import Transaction
from chain.wallet import Wallet


def real_demo():
    attacker, shop, honest = Wallet.generate(), Wallet.generate(), Wallet.generate()
    chain = Blockchain()
    for _ in range(2):                                   # Атакувальник заробляє початкові монети
        b = chain.build_block(attacker.address, []); b.mine(); chain.add_block(b)
    fork_point = chain.height
    print(f"Висота {chain.height}, у атакувальника {chain.balance(attacker.address)} монет. Він платить магазину 60.")
    pool = Mempool()
    tx = Transaction(attacker.address, shop.address, 60, 1, 0); tx.sign(attacker)
    pool.add(tx, chain)
    private = Blockchain(list(chain.blocks))              # копія для прихованої гілки
    b = chain.build_block(honest.address, pool.select_for_block(chain)); b.mine(); chain.add_block(b)
    for _ in range(2):                                   # ще 2 підтвердження від чесних майнерів
        b = chain.build_block(honest.address, []); b.mine(); chain.add_block(b)
    print(f"Платіж у блоці {fork_point + 1}, підтверджень 3, висота {chain.height}. Магазин віддає товар. "
          f"Баланс магазину: {chain.balance(shop.address)}")
    print("Атакувальник усе цей час приховано майнить свою гілку без цього платежу...")
    for _ in range(4):                                   # приховано: 4 блоки проти 3 чесних
        b = private.build_block(attacker.address, []); b.mine(); private.add_block(b)
    print(f"Прихована гілка після розгалуження: {private.height - fork_point} блоків проти {chain.height - fork_point} чесних; "
          f"сумарна робота {private.total_work()} проти {chain.total_work()}")
    if private.total_work() > chain.total_work():
        fork = common_prefix_len(chain.blocks, private.blocks)
        chain = Blockchain.from_blocks(private.blocks)   # вузол перевіряє гілку: вона коректна й важча
        print(f"Атакувальник публікує гілку. Вузли її приймають (розгалуження після блоку {fork - 1}).")
        print(f"Баланс магазину тепер: {chain.balance(shop.address)}, баланс атакувальника: {chain.balance(attacker.address)}. Платіж зник, товар уже віддано.")


def nb_success(q: float, z: int) -> float:
    """Аналітична ймовірність успіху: сума по k блоків, які атакувальник встигає знайти, поки чесні знаходять z."""
    if q >= 0.5:
        return 1.0
    p = 1 - q
    total = 0.0
    for k in range(0, 400):
        pk = math.comb(k + z - 1, k) * p ** z * q ** k
        total += pk * (1.0 if k > z else (q / p) ** (z - k + 1))
    return total


def simulate(q: float, z: int, trials: int, rng: random.Random, give_up: int = 40) -> float:
    wins = 0
    for _ in range(trials):
        honest = attacker = 0
        while honest < z:                                # магазин чекає z підтверджень
            if rng.random() < q:
                attacker += 1
            else:
                honest += 1
        while True:                                      # гонка триває, поки хтось не відірветься
            if attacker > honest:
                wins += 1
                break
            if honest - attacker > give_up:
                break
            if rng.random() < q:
                attacker += 1
            else:
                honest += 1
    return wins / trials


def chart(path="results/attack51.png"):
    rng = random.Random(7)
    qs = [0.05 * i for i in range(1, 13)]
    plt.figure(figsize=(7.5, 4.6))
    for z, color in ((1, "#c0392b"), (3, "#2980b9"), (6, "#27ae60")):
        xs = [i / 100 for i in range(2, 61)]
        plt.plot(xs, [nb_success(x, z) for x in xs], color=color, label=f"формула, z={z}")
        plt.scatter(qs, [simulate(x, z, 3000, rng) for x in qs], color=color, s=18)
    plt.axvline(0.5, color="gray", ls="--", lw=1)
    plt.xlabel("частка обчислювальної потужності атакувальника q")
    plt.ylabel("ймовірність переписати історію")
    plt.title("Атака 51 %: точки — симуляція, лінії — формула")
    plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(path, dpi=140)
    for z in (1, 3, 6):
        print(f"z={z}: q=0.10 → {nb_success(0.10, z):.4f}   q=0.30 → {nb_success(0.30, z):.4f}   q=0.45 → {nb_success(0.45, z):.4f}")


if __name__ == "__main__":
    print("== Частина 1. Переписування історії (справжній код) ==")
    real_demo()
    print("\n== Частина 2. Ймовірність успіху атаки ==")
    chart()
