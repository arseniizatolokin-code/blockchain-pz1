"""Демонстрація: три вузли, розрив мережі, форк, відновлення зв'язку й вибір найважчого ланцюга."""
import os
import shutil
import tempfile
import time

import client
import run_network

PORTS = [5101, 5102, 5103]
URL = {n: f"http://127.0.0.1:{p}" for n, p in zip("ABC", PORTS)}


def status(n):
    return client.api(URL[n], "GET", "/status")


def show(title):
    print(f"\n{title}")
    for n in "ABC":
        s = status(n)
        print(f"  вузол {n}: висота {s['height']}  вершина {s['tip'][:12]}…  мемпул {s['mempool']}  {'online' if s['online'] else 'ВІДКЛЮЧЕНО'}")


def wait(cond, what, timeout=15):
    t = time.time()
    while time.time() - t < timeout:
        if cond():
            return
        time.sleep(0.2)
    raise SystemExit(f"не дочекались: {what}")


def same(nodes, height=None):
    ss = [status(n) for n in nodes]
    return len({s["tip"] for s in ss}) == 1 and (height is None or ss[0]["height"] == height)


def main():
    tmp = tempfile.mkdtemp()
    os.makedirs("wallets", exist_ok=True)
    wallets = {}
    for name in ("alice", "bob", "carol"):
        path = client.wallet_path("demo_" + name)
        if os.path.exists(path):
            os.remove(path)
        wallets[name] = client.create_wallet("demo_" + name)
    procs = run_network.start_nodes(PORTS, tmp)
    try:
        wait(lambda: all(_up(n) for n in "ABC"), "запуск вузлів")
        time.sleep(0.5)
        print("== Крок 1. Три вузли запущено й з'єднано між собою ==")
        show("початковий стан")

        print("\n== Крок 2. Alice майнить блок 1 на вузлі A, Bob майнить блок 2 на вузлі B ==")
        client.mine(URL["A"], wallets["alice"].address)
        wait(lambda: same("ABC", 1), "поширення блоку 1")
        client.mine(URL["B"], wallets["bob"].address)
        wait(lambda: same("ABC", 2), "поширення блоку 2")
        show("після двох блоків (усі вузли збігаються)")

        print("\n== Крок 3. Розрив мережі: вузол C відключається ==")
        client.api(URL["C"], "POST", "/network", json={"online": False})
        r1 = client.send(URL["A"], wallets["alice"], wallets["carol"].address, 10)
        print(f"  на A: Alice → Carol 10 монет, {'прийнято' if r1['ok'] else r1['reason']}")
        client.mine(URL["A"], wallets["alice"].address)
        wait(lambda: same("AB", 3), "блок 3 на A і B")
        r2 = client.send(URL["C"], wallets["bob"], wallets["carol"].address, 5)
        print(f"  на C: Bob → Carol 5 монет, {'прийнято' if r2['ok'] else r2['reason']}")
        client.mine(URL["C"], wallets["bob"].address)
        client.mine(URL["C"], wallets["bob"].address)
        show("ФОРК: A і B мають гілку з 3 блоків, C — довшу гілку з 4 блоків")

        print("\n== Крок 4. Вузол C знову в мережі, A і B синхронізуються ==")
        client.api(URL["C"], "POST", "/network", json={"online": True})
        for n in "AB":
            info = client.api(URL[n], "POST", "/sync")
            print(f"  вузол {n}: {info}")
        wait(lambda: same("ABC", 4), "збіжність після форку")
        show("після вирішення форку (усі на одному ланцюгу)")
        print("  транзакція Alice → Carol з відкинутого блоку повернулась у мемпул A і B")

        print("\n== Крок 5. Транзакція підтверджується в новому блоці ==")
        client.mine(URL["A"], wallets["alice"].address)
        wait(lambda: same("ABC", 5), "блок 5")
        show("фінальний стан")
        for n in "ABC":
            v = client.api(URL[n], "GET", "/validate")
            print(f"  вузол {n}: перевірка ланцюга — {'коректний' if v['valid'] else v['reason']}")
        for name in ("alice", "bob", "carol"):
            print(f"  баланс {name}: {client.api(URL['A'], 'GET', '/balance/' + wallets[name].address)['balance']}")
    finally:
        for p in procs:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


def _up(n):
    try:
        status(n)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
