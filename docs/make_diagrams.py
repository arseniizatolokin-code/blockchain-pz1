import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def box(ax, x, y, w, h, text, fc="#ecf0f1", ec="#2c3e50", fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)


def arrow(ax, a, b, text="", dy=0.12):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1.3, color="#34495e"))
    if text:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + dy, text, ha="center", fontsize=8, color="#555")


# 1. архітектура
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 5.2); ax.axis("off")
box(ax, 0.2, 3.7, 2.2, 1.1, "cli.py + client.py\nгаманець, підпис,\nвиклики API", "#d6eaf8")
box(ax, 3.4, 3.7, 3.0, 1.1, "node.py (Flask API)\n/transactions /mine /blocks\n/chain /sync /peers", "#fdebd0")
box(ax, 7.4, 3.7, 2.4, 1.1, "інші вузли мережі\n(сусіди, розсилка,\nсинхронізація)", "#d5f5e3")
box(ax, 0.2, 1.7, 2.6, 1.2, "mempool.py\nчерга транзакцій,\nперевірки підпису/nonce/балансу", "#f9e79f")
box(ax, 3.4, 1.7, 3.0, 1.2, "blockchain.py\nланцюг, стан рахунків,\nповна перевірка правил, складність", "#f9e79f")
box(ax, 7.2, 1.7, 2.6, 1.2, "block.py + merkle.py\nзаголовок, PoW,\nдерево Меркла", "#f9e79f")
box(ax, 0.2, 0.15, 2.6, 0.95, "transaction.py + wallet.py\nEd25519, nonce", "#fadbd8")
box(ax, 3.4, 0.15, 3.0, 0.95, "crypto.py + config.py\nSHA-256, параметри мережі", "#fadbd8")
box(ax, 7.2, 0.15, 2.6, 0.95, "data/node_PORT.json\nзбереження ланцюга", "#e8daef")
arrow(ax, (2.4, 4.25), (3.4, 4.25), "HTTP")
arrow(ax, (6.4, 4.25), (7.4, 4.25), "HTTP")
arrow(ax, (4.9, 3.7), (4.9, 2.9)); arrow(ax, (3.9, 3.7), (2.2, 2.9))
arrow(ax, (6.4, 2.3), (7.2, 2.3)); arrow(ax, (3.4, 2.3), (2.8, 2.3))
arrow(ax, (4.9, 1.7), (4.9, 1.1)); arrow(ax, (1.5, 1.7), (1.5, 1.1)); arrow(ax, (6.4, 1.7), (7.6, 1.1))
ax.set_title("Структура проєкту", fontsize=11)
fig.tight_layout(); fig.savefig("docs/img/architecture.png", dpi=150)

# 2. структура ланцюга та блоку
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.set_xlim(0, 10); ax.set_ylim(0, 4); ax.axis("off")
for i, x in enumerate((0.2, 3.5, 6.8)):
    box(ax, x, 0.4, 3.0, 3.1, "", "#fdfefe")
    ax.text(x + 1.5, 3.2, f"Блок {i + 1}", ha="center", fontsize=10, weight="bold")
    ax.text(x + 0.15, 2.75, "index, timestamp, difficulty", fontsize=8)
    ax.text(x + 0.15, 2.3, f"prev_hash = H(блок {i})", fontsize=8, color="#c0392b")
    ax.text(x + 0.15, 1.85, "merkle_root", fontsize=8, color="#2471a3")
    ax.text(x + 0.15, 1.4, "nonce  (Proof of Work)", fontsize=8)
    ax.text(x + 0.15, 0.85, "транзакції: coinbase, tx1, tx2…", fontsize=8)
    ax.text(x + 0.15, 0.55, "hash = SHA-256(заголовок)", fontsize=8, style="italic")
arrow(ax, (3.5, 2.35), (3.2, 2.35)); arrow(ax, (6.8, 2.35), (6.5, 2.35))
ax.set_title("Блоки зв'язані через prev_hash; транзакції закріплені в заголовку коренем Меркла", fontsize=10)
fig.tight_layout(); fig.savefig("docs/img/blocks.png", dpi=150)
print("ok")
