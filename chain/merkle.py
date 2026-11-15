"""Дерево Меркла, написане власноруч. Листки — це tx_id (вони вже є SHA-256 хешами)."""
import hashlib


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def merkle_root(leaves: list) -> str:
    """Корінь Меркла. Якщо на рівні непарна кількість вузлів, останній дублюється."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [bytes.fromhex(x) for x in leaves]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        level = [_h(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()


def merkle_proof(leaves: list, index: int) -> list:
    """Доказ входження листка: список пар (хеш сусіда, 'L'|'R') від листка до кореня."""
    level = [bytes.fromhex(x) for x in leaves]
    proof = []
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        sibling = index ^ 1
        proof.append((level[sibling].hex(), "L" if sibling < index else "R"))
        level = [_h(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
        index //= 2
    return proof


def verify_proof(leaf: str, proof: list, root: str) -> bool:
    cur = bytes.fromhex(leaf)
    for sibling_hex, side in proof:
        sib = bytes.fromhex(sibling_hex)
        cur = _h(sib + cur) if side == "L" else _h(cur + sib)
    return cur.hex() == root
