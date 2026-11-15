"""Запускає три вузли на портах 5001-5003 і з'єднує їх між собою: python run_network.py"""
import subprocess
import sys
import time

PORTS = [5001, 5002, 5003]


def start_nodes(ports=PORTS, data_dir="data", env=None):
    procs = []
    for p in ports:
        peers = ",".join(f"http://127.0.0.1:{q}" for q in ports if q != p)
        procs.append(subprocess.Popen(
            [sys.executable, "node.py", "--port", str(p), "--peers", peers, "--data", f"{data_dir}/node_{p}.json"],
            env=env))
    return procs


if __name__ == "__main__":
    procs = start_nodes()
    print("вузли запущено:", ", ".join(f"http://127.0.0.1:{p}" for p in PORTS), "(Ctrl+C — зупинити)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for pr in procs:
            pr.terminate()
