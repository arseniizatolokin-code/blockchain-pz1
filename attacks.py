"""П'ять атак на власний блокчейн. Запуск: python attacks.py
Кожна атака виконується проти справжнього вузла (HTTP API) або справжньої перевірки ланцюга."""
import contextlib
import copy
import io
import json
import os
import tempfile
import threading

from werkzeug.serving import make_server

import client
from chain.block import Block
from chain.blockchain import Blockchain, ChainError, State, apply_transactions
from chain.transaction import Transaction
from chain.wallet import Wallet
from node import Node, create_app

PORT = 5201
URL = f"http://127.0.0.1:{PORT}"


def short(a):
    return a[:8] + "…"


def setup():
    """Вузол + кілька блоків історії: Alice майнить, платить Bob, Bob платить назад."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "node.json")
    node = Node(PORT, path)
    srv = make_server("127.0.0.1", PORT, create_app(node), threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    alice, bob, mallory = Wallet.generate(), Wallet.generate(), Wallet.generate()
    client.mine(URL, alice.address)
    client.mine(URL, alice.address)
    client.send(URL, alice, bob.address, 20)
    client.mine(URL, alice.address)            # блок 3 містить Alice → Bob 20
    client.send(URL, bob, alice.address, 5)
    client.mine(URL, bob.address)              # блок 4 містить Bob → Alice 5
    return node, srv, path, alice, bob, mallory


def attack1(node, path, alice, bob):
    print("Атака 1. Змінити суму в старому блоці")
    print(f"Ланцюг на вузлі: висота {node.chain.height}, коректний: {node.chain.validate()[0]}")
    blocks = [b.to_dict() for b in node.chain.blocks]
    tx = blocks[3]["transactions"][1]
    print(f"Блок 3, транзакція Alice → Bob: сума {tx['amount']}. Атакувальник правит файл і ставить 2000.")
    tx["amount"] = 2000
    tampered = [Block.from_dict(b) for b in blocks]
    try:
        Blockchain.from_blocks(tampered)
        print("УВАГА: підміну не виявлено")
    except ChainError as e:
        print(f"Перевірка ланцюга: ВІДХИЛЕНО — {e}")
    print("Той самий підроблений файл кладемо на диск вузла й перезапускаємо його:")
    with open(path, "w") as f:
        json.dump({"blocks": blocks}, f)
    restarted = Node(PORT + 50, path)
    print(f"Вузол після запуску: висота {restarted.chain.height} (файл відкинуто, починає з генезису)")


def attack2(node, alice, bob):
    print("Атака 2. Змінити дані блоку й перерахувати його хеш (перемайнити блок)")
    blocks = copy.deepcopy(node.chain.blocks)
    old = blocks[3]
    old_tx = old.transactions[1]
    print(f"Блок 3: Alice → Bob {old_tx.amount}. Alice сама є автором транзакції, тому змінює суму на 1, підписує знову,")
    print("перераховує корінь Меркла й заново майнить блок 3 (його Proof of Work цілком чесний).")
    new_tx = Transaction(old_tx.sender, old_tx.recipient, 1, old_tx.fee, old_tx.nonce)
    new_tx.sign(alice)
    old.transactions[1] = new_tx
    old.merkle_root = old.compute_merkle_root()
    old.mine()
    print(f"Новий хеш блоку 3: {old.hash()[:16]}…")
    ok_alone = Blockchain.from_blocks(blocks[:4]) is not None
    print(f"Ланцюг до блоку 3 включно сам по собі коректний: {ok_alone}")
    try:
        Blockchain.from_blocks(blocks)
        print("УВАГА: підміну не виявлено")
    except ChainError as e:
        print(f"Повний ланцюг: ВІДХИЛЕНО — {e}")
    print(f"Щоб це виправити, треба заново замайнити ще {len(blocks) - 4} наступних блок(ів) і обігнати решту мережі.")


def attack3(alice, bob, mallory):
    print("Атака 3. Підроблений підпис")
    print(f"Mallory хоче вкрасти кошти Alice (адреса {short(alice.address)}) на свою адресу.")
    tx = Transaction(alice.address, mallory.address, 30, 1, client.api(URL, "GET", f"/nonce/{alice.address}")["nonce"],
                     pubkey=alice.public_key_hex)
    tx.signature = mallory.sign(tx.signing_payload())          # підписує власним ключем
    r = client.api(URL, "POST", "/transactions", json=tx.to_dict())
    print(f"Варіант А: публічний ключ Alice, підпис Mallory → {'прийнято' if r['ok'] else 'ВІДХИЛЕНО: ' + r['reason']}")
    tx2 = Transaction(alice.address, mallory.address, 30, 1, tx.nonce, pubkey=mallory.public_key_hex)
    tx2.sign(mallory)                                           # чесно підписує своїм ключем, але видає себе за Alice
    r = client.api(URL, "POST", "/transactions", json=tx2.to_dict())
    print(f"Варіант Б: ключ і підпис Mallory, поле sender = адреса Alice → {'прийнято' if r['ok'] else 'ВІДХИЛЕНО: ' + r['reason']}")
    good = Transaction(alice.address, bob.address, 3, 1, tx.nonce)
    good.sign(alice)
    tampered = Transaction(**{**good.to_dict(), "amount": 3000})
    r = client.api(URL, "POST", "/transactions", json=tampered.to_dict())
    print(f"Варіант В: справжня транзакція Alice, але суму змінено з 3 на 3000 → {'прийнято' if r['ok'] else 'ВІДХИЛЕНО: ' + r['reason']}")


def attack4(node, alice, bob):
    print("Атака 4. Подвійна витрата")
    avail = client.api(URL, "GET", f"/balance/{alice.address}")["available"]
    print(f"У Alice доступно {avail}. Вона хоче двічі витратити майже весь баланс: Bob і Carol по {avail - 5}.")
    carol = Wallet.generate()
    r1 = client.send(URL, alice, bob.address, avail - 5, 1)
    print(f"Транзакція 1 (→ Bob): {'прийнято' if r1['ok'] else 'ВІДХИЛЕНО: ' + r1['reason']}")
    r2 = client.send(URL, alice, carol.address, avail - 5, 1)
    print(f"Транзакція 2 (→ Carol): {'прийнято' if r2['ok'] else 'ВІДХИЛЕНО: ' + r2['reason']}")
    nonce = client.api(URL, "GET", f"/nonce/{alice.address}")["nonce"] - 1
    t3 = Transaction(alice.address, carol.address, 1, 1, nonce)
    t3.sign(alice)
    r3 = client.api(URL, "POST", "/transactions", json=t3.to_dict())
    print(f"Транзакція 3 (той самий nonce {nonce}, інший отримувач): {'прийнято' if r3['ok'] else 'ВІДХИЛЕНО: ' + r3['reason']}")
    print("Нечесний майнер спробує вставити обидві великі транзакції в один блок:")
    base = Blockchain(list(node.chain.blocks))
    a = Transaction(alice.address, bob.address, avail - 5, 1, base.next_nonce(alice.address)); a.sign(alice)
    b = Transaction(alice.address, carol.address, avail - 5, 1, base.next_nonce(alice.address) + 1); b.sign(alice)
    blk = base.build_block(Wallet.generate().address, [a, b]); blk.mine()
    try:
        base.add_block(blk)
        print("УВАГА: блок прийнято")
    except ChainError as e:
        print(f"Перевірка блоку: ВІДХИЛЕНО — {e}")


def attack5(node, alice, bob):
    print("Атака 5. Повторне надсилання вже підтвердженої транзакції (replay)")
    old = node.chain.blocks[3].transactions[1]
    print(f"Береться транзакція з блоку 3: Alice → Bob {old.amount}, nonce {old.nonce}. Її надсилають ще раз.")
    r = client.api(URL, "POST", "/transactions", json=old.to_dict())
    print(f"Вузол: {'прийнято' if r['ok'] else 'ВІДХИЛЕНО: ' + r['reason']}")
    print("Припустимо, вузол не веде історії tx_id. Тоді працює nonce:")
    st = State()
    st.balances = dict(node.chain.state.balances)
    st.nonces = dict(node.chain.state.nonces)           # лічильники nonce лишаються, список tx_id порожній
    blk = node.chain.build_block(Wallet.generate().address, [old])
    try:
        apply_transactions(st, blk)
        print("УВАГА: повтор пройшов")
    except ChainError as e:
        print(f"Перевірка блоку з повтором: ВІДХИЛЕНО — {e}")


def main():
    node, srv, path, alice, bob, mallory = setup()
    os.makedirs("results", exist_ok=True)
    jobs = [("attack_1", lambda: attack1(node, path, alice, bob)),
            ("attack_2", lambda: attack2(node, alice, bob)),
            ("attack_3", lambda: attack3(alice, bob, mallory)),
            ("attack_4", lambda: attack4(node, alice, bob)),
            ("attack_5", lambda: attack5(node, alice, bob))]
    for name, fn in jobs:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fn()
        text = buf.getvalue()
        with open(f"results/{name}.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print(text)
    srv.shutdown()


if __name__ == "__main__":
    main()
