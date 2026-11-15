#!/bin/bash
# Сеанс роботи з CLI: три вузли, два гаманці, транзакція, майнінг, перевірка
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
rm -rf wallets data_cli
python3 -c "
import run_network
run_network.start_nodes(data_dir='data_cli')
import time; time.sleep(100000)" > /dev/null 2>&1 &
RUN=$!
sleep 2
run() { echo "\$ python cli.py $*"; python3 cli.py "$@"; }
run wallet new alice
run wallet new bob
run --node http://127.0.0.1:5001 mine --wallet alice
run --node http://127.0.0.1:5001 balance alice
run --node http://127.0.0.1:5001 send --wallet alice --to bob --amount 20 --fee 2
run --node http://127.0.0.1:5002 mempool
run --node http://127.0.0.1:5003 mine --wallet bob
sleep 1
run --node http://127.0.0.1:5001 chain
run --node http://127.0.0.1:5002 balance bob
run --node http://127.0.0.1:5003 validate
pkill -P $RUN 2>/dev/null; pkill -f "node.py --port 500" 2>/dev/null; kill $RUN 2>/dev/null
rm -rf wallets data_cli
