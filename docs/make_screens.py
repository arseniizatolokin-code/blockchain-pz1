"""Перетворює збережений консольний вивід (results/*.txt) на зображення у стилі термінала для звіту.
Текст у зображеннях — справжній вивід програм, нічого не домальовується."""
import os
import sys
import textwrap

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BG, FG, PROMPT = (30, 30, 30), (220, 220, 220), (120, 200, 120)


def render(text: str, out: str, title: str, size: int = 16, width_chars: int = 88):
    font = ImageFont.truetype(FONT, size)
    lines = []
    for raw in text.rstrip("\n").split("\n"):
        wrapped = textwrap.wrap(raw, width_chars, subsequent_indent="    ") or [""]
        lines.extend(wrapped)
    cw = font.getlength("M")
    lh = size + 6
    w = int(cw * min(max(len(l) for l in lines), width_chars) + 40)
    h = lh * len(lines) + 62
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 30], fill=(55, 55, 55))
    for i, c in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        d.ellipse([12 + i * 20, 9, 24 + i * 20, 21], fill=c)
    d.text((90, 7), title, font=ImageFont.truetype(FONT, 13), fill=(190, 190, 190))
    y = 44
    for l in lines:
        d.text((20, y), l, font=font, fill=PROMPT if l.startswith("$ ") else FG)
        y += lh
    img.save(out)


def read(name):
    return open(f"results/{name}.txt", encoding="utf-8").read()


def strip_logs(t):
    """З виводу демо прибираємо лише службові рядки Flask, решту лишаємо як є."""
    return "\n".join(l for l in t.split("\n") if "Serving Flask" not in l and "Debug mode" not in l)


if __name__ == "__main__":
    os.makedirs("docs/img", exist_ok=True)
    for i in range(1, 6):
        render(read(f"attack_{i}"), f"docs/img/attack_{i}.png", f"python attacks.py  (атака {i})")
    demo = strip_logs(read("demo_fork"))
    parts = demo.split("== Крок 3.")
    p1 = parts[0]
    rest = "== Крок 3." + parts[1]
    p2, p3 = rest.split("== Крок 4.")
    render(p1.rstrip(), "docs/img/demo_1.png", "python demo_fork.py  (кроки 1-2: запуск і синхронізація)")
    render("== Крок 3." + p2.rstrip(), "docs/img/demo_2.png", "python demo_fork.py  (крок 3: розрив мережі і форк)")
    render("== Крок 4." + p3.rstrip(), "docs/img/demo_3.png", "python demo_fork.py  (кроки 4-5: вирішення форку)")
    render(read("cli_session"), "docs/img/cli.png", "консольний клієнт cli.py")
    render(read("attack51"), "docs/img/attack51.png", "python attack51.py")
    render(read("experiment"), "docs/img/experiment_console.png", "python experiment.py")
    t = read("tests").split("\n")
    head = [l for l in t if "::" not in l]
    body = [l.replace("tests/", "") for l in t if "::" in l]
    render("\n".join(head[:6] + body + head[6:]), "docs/img/tests.png", "python -m pytest -v", size=15, width_chars=90)
    print("ok")
