"""Консольний клієнт. Приклади:
  python cli.py wallet new alice
  python cli.py mine --wallet alice
  python cli.py send --wallet alice --to <адреса> --amount 10
"""
import argparse
import json

import client


def main():
    ap = argparse.ArgumentParser(description="Клієнт блокчейну")
    ap.add_argument("--node", default="http://127.0.0.1:5001", help="адреса вузла")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("wallet", help="створити гаманець або показати адресу")
    w.add_argument("action", choices=["new", "show"])
    w.add_argument("name")

    s = sub.add_parser("send", help="надіслати монети")
    s.add_argument("--wallet", required=True)
    s.add_argument("--to", required=True, help="адреса або ім'я локального гаманця")
    s.add_argument("--amount", type=int, required=True)
    s.add_argument("--fee", type=int, default=1)

    m = sub.add_parser("mine", help="замайнити блок")
    m.add_argument("--wallet", required=True)

    b = sub.add_parser("balance", help="баланс адреси або гаманця")
    b.add_argument("who")

    sub.add_parser("chain", help="показати ланцюг")
    sub.add_parser("mempool", help="показати чергу транзакцій")
    sub.add_parser("status", help="стан вузла")
    sub.add_parser("validate", help="повна перевірка ланцюга")
    sub.add_parser("sync", help="синхронізація із сусідами")

    p = sub.add_parser("peer", help="додати сусіда")
    p.add_argument("url")

    n = sub.add_parser("network", help="відключити/підключити вузол до мережі")
    n.add_argument("state", choices=["on", "off"])

    a = ap.parse_args()

    def resolve(who):
        try:
            return client.load_wallet(who).address
        except FileNotFoundError:
            return who

    if a.cmd == "wallet":
        if a.action == "new":
            wl = client.create_wallet(a.name)
        else:
            wl = client.load_wallet(a.name)
        print("адреса:", wl.address)
    elif a.cmd == "send":
        r = client.send(a.node, client.load_wallet(a.wallet), resolve(a.to), a.amount, a.fee)
        print("прийнято, tx_id:" if r.get("ok") else "ВІДХИЛЕНО:", r.get("tx_id")[:16] if r.get("ok") else r.get("reason"))
    elif a.cmd == "mine":
        r = client.mine(a.node, resolve(a.wallet))
        if r.get("ok"):
            blk = r["block"]
            print(f"замайнено блок {blk['index']}  хеш {blk['hash'][:16]}…  nonce {blk['nonce']}  транзакцій {len(blk['transactions']) - 1}")
        else:
            print("помилка:", r.get("reason"))
    elif a.cmd == "balance":
        r = client.api(a.node, "GET", f"/balance/{resolve(a.who)}")
        print(f"баланс {r['balance']}, доступно з урахуванням черги {r['available']}")
    elif a.cmd == "chain":
        for blk in client.api(a.node, "GET", "/chain")["blocks"]:
            print(f"#{blk['index']:<3} {blk['hash'][:16]}…  prev {blk['prev_hash'][:8]}…  складність {blk['difficulty']:<3} транзакцій {max(len(blk['transactions']) - 1, 0)}")
    elif a.cmd == "mempool":
        txs = client.api(a.node, "GET", "/mempool")["transactions"]
        for t in txs:
            print(f"{t['tx_id'][:8]}  {t['sender'][:8]}… → {t['recipient'][:8]}…  сума {t['amount']} комісія {t['fee']} nonce {t['nonce']}")
        print(f"всього: {len(txs)}")
    elif a.cmd == "status":
        print(json.dumps(client.api(a.node, "GET", "/status"), indent=2, ensure_ascii=False))
    elif a.cmd == "validate":
        r = client.api(a.node, "GET", "/validate")
        print("ланцюг коректний" if r["valid"] else f"ланцюг НЕКОРЕКТНИЙ: {r['reason']}")
    elif a.cmd == "sync":
        print(client.api(a.node, "POST", "/sync"))
    elif a.cmd == "peer":
        print(client.api(a.node, "POST", "/peers", json={"url": a.url}))
    elif a.cmd == "network":
        print(client.api(a.node, "POST", "/network", json={"online": a.state == "on"}))


if __name__ == "__main__":
    main()
