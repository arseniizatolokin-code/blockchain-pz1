"""Експеримент: як складність впливає на час майнінгу одного блоку.
Для кожного рівня (2..6 шістнадцяткових нулів = 8..24 біти) робимо 10 запусків на різних блоках."""
import csv
import statistics
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from chain.block import Block
from chain.merkle import merkle_root
from chain.crypto import sha256_hex

HEX_ZEROS = [2, 3, 4, 5, 6]
RUNS = 10


def run_once(bits: int, seed: int) -> tuple:
    """Майнить блок із унікальним вмістом (щоб кожен запуск шукав свій nonce)."""
    leaves = [sha256_hex(f"tx-{seed}-{i}".encode()) for i in range(3)]
    b = Block(seed, 1_700_000_000_000 + seed, sha256_hex(f"prev-{seed}".encode()), merkle_root(leaves), bits, 0)
    t = time.perf_counter()
    b.mine()
    return time.perf_counter() - t, b.nonce + 1


def main():
    rows = []
    for z in HEX_ZEROS:
        bits = 4 * z
        for r in range(RUNS):
            sec, tries = run_once(bits, seed=1000 * z + r)
            rows.append((z, bits, r + 1, tries, sec))
        times = [x[4] for x in rows if x[0] == z]
        print(f"{z} hex-нулів ({bits} біт): середній час {statistics.mean(times):8.3f} с, "
              f"мін {min(times):.3f}, макс {max(times):.3f}, очікувано спроб {2 ** bits}")
    with open("results/experiment.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hex_zeros", "bits", "run", "attempts", "seconds"])
        w.writerows(rows)

    total_tries = sum(r[3] for r in rows)
    total_time = sum(r[4] for r in rows)
    rate = total_tries / total_time
    print(f"\nШвидкість: {rate:,.0f} хешів/с")
    means = [statistics.mean([x[4] for x in rows if x[0] == z]) for z in HEX_ZEROS]
    print("Відношення середніх часів між сусідніми рівнями:", ", ".join(f"{means[i + 1] / means[i]:.1f}" for i in range(len(means) - 1)), "(теорія: 16)")

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for z in HEX_ZEROS:
        ts = [x[4] for x in rows if x[0] == z]
        ax.scatter([z] * len(ts), ts, color="#7f8c8d", s=14, alpha=.6, label="окремі запуски" if z == HEX_ZEROS[0] else None)
    ax.plot(HEX_ZEROS, means, "o-", color="#c0392b", label="середнє за 10 запусків")
    ax.plot(HEX_ZEROS, [2 ** (4 * z) / rate for z in HEX_ZEROS], "--", color="#2980b9", label=f"теорія 2^біти / {rate / 1e6:.2f} МГх/с")
    ax.set_yscale("log")
    ax.set_xticks(HEX_ZEROS)
    ax.set_xlabel("кількість початкових нулів у хеші (hex)")
    ax.set_ylabel("час майнінгу блоку, с (логарифмічна шкала)")
    ax.set_title("Залежність часу майнінгу від складності")
    ax.grid(alpha=.3, which="both"); ax.legend(); fig.tight_layout()
    fig.savefig("results/experiment.png", dpi=140)


if __name__ == "__main__":
    main()
