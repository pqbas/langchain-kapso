"""Generates docs/architecture.svg and docs/architecture.png, the diagram in the README.

    python3 docs/architecture.py

Needs Google Chrome to render the PNG. Icons: LangChain and WhatsApp from Simple Icons,
Kapso from kapso.com; they identify the products this project integrates with.
"""

import base64
import re
import shutil
import subprocess
from pathlib import Path

DOCS = Path(__file__).resolve().parent
ASSETS = DOCS / "assets"
W, H = 1400, 540
FONT = "Helvetica, Arial, sans-serif"
INK, MUTED, LINE = "#1f2328", "#59636e", "#1f2328"
out: list[str] = []


def icon_path(name: str) -> str:
    return re.search(r'<path d="([^"]+)"', (ASSETS / f"{name}.svg").read_text()).group(1)


def simple_icon(name: str, x: float, y: float, size: float, color: str) -> None:
    out.append(f'<path d="{icon_path(name)}" fill="{color}" transform="translate({x},{y}) scale({size / 24})"/>')


def kapso_icon(x: float, y: float, size: float) -> None:
    data = base64.b64encode((ASSETS / "kapso.png").read_bytes()).decode()
    out.append(f'<image href="data:image/png;base64,{data}" x="{x}" y="{y}" width="{size}" height="{size}"/>')


def text(x, y, s, size=15, color=INK, anchor="middle", weight="normal"):
    for i, line in enumerate(s.split("\n")):
        out.append(
            f'<text x="{x}" y="{y + i * size * 1.35}" font-family="{FONT}" font-size="{size}" '
            f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{line}</text>'
        )


def box(x, y, w, h, fill="#ffffff", stroke="#d0d7de", dashed=False, radius=12):
    dash = ' stroke-dasharray="7 6"' if dashed else ""
    out.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.5"{dash}/>'
    )


def arrow(x1, y1, x2, y2, label="", lx=None, ly=None, color=LINE):
    out.append(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.6" marker-end="url(#a)"/>'
    )
    if label:
        text(lx if lx is not None else (x1 + x2) / 2, ly if ly is not None else (y1 + y2) / 2 - 8, label, 12.5, MUTED)


# Customer
simple_icon("whatsapp", 67, 115, 110, "#25D366")
text(122, 255, "Customer\non WhatsApp", 17)

# Kapso
box(270, 40, 330, 450, fill="#f6f8fa")
kapso_icon(361, 63, 44)
text(415, 96, "Kapso", 28, anchor="start", weight="bold")
box(300, 125, 270, 90)
text(435, 165, "WhatsApp API", 16, weight="bold")
text(435, 190, "delivers and sends messages", 13, MUTED)
box(300, 345, 270, 90)
text(435, 385, "Inbox", 16, weight="bold")
text(435, 410, "your team answers here", 13, MUTED)

# Your server
box(680, 40, 700, 450, fill="#f6f8fa")
text(1030, 96, "Your server", 28, weight="bold")
box(705, 125, 300, 125, fill="#fff8e1", stroke="#e3b341")
text(855, 194, "langchain-kapso", 20, weight="bold")
box(1075, 125, 280, 125, fill="#eef7ee", stroke="#57ab5a")
simple_icon("langchain", 1098, 159, 56, "#1C3C3C")
text(1164, 194, "LangGraph Agent", 20, anchor="start", weight="bold")
box(1075, 345, 280, 90, fill="#ffffff")
text(1215, 385, "kapso_human_handoff", 15, weight="bold")
text(1215, 410, "one of the agent's tools", 13, MUTED)

# Flow
arrow(190, 150, 296, 150, "message")
arrow(300, 195, 194, 195, "reply", ly=213)
arrow(570, 150, 701, 150, "webhook")
arrow(705, 195, 574, 195, "reply", ly=213)
arrow(1005, 165, 1071, 165, "runs", ly=155)
arrow(1075, 215, 1009, 215, "answer", ly=233)
arrow(1215, 250, 1215, 341)
arrow(1075, 390, 574, 390, "assigns the chat with a summary", ly=380)
arrow(300, 385, 150, 300, "a person\nanswers", lx=185, ly=385)

svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n'
    '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
    f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>\n'
    f'<rect width="{W}" height="{H}" fill="#ffffff"/>\n' + "\n".join(out) + "\n</svg>\n"
)
(DOCS / "architecture.svg").write_text(svg)

chrome = shutil.which("google-chrome") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
subprocess.run(
    [chrome, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
     f"--screenshot={DOCS / 'architecture.png'}", f"--window-size={W},{H}", (DOCS / "architecture.svg").as_uri()],
    check=True, capture_output=True,
)
