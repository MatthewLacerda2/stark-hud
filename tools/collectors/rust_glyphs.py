"""Which glyph stands for a part of a Rust project, by its name.

A keyword table maps a part's name, or one `_`/`-` word of it, to a lucide
glyph vendored beside this file (ISC, see `rust_icons/LICENSE`). A name the
table does not know gets a plain box, and is reported so the table can grow.
"""

import re
from pathlib import Path

ICONS = Path(__file__).resolve().parent / "rust_icons"

# A part's name, or one `_`/`-` word of it, to the lucide glyph that says what
# it is. Whole names come first because some carry no meaning a word can find:
# `zimmer` is scorsese's synthesiser, `shadergen` is not two words.
GLYPHS = {
    "zimmer": "audio-waveform",
    "shadergen": "sparkles",
    "procgen": "dices",
    "ecs": "boxes",
    "mcp": "bot",
    "api": "plug",
    "app": "app-window",
    "asset": "package",
    "assets": "package",
    "audio": "volume-2",
    "sound": "volume-2",
    "cli": "terminal",
    "shell": "terminal",
    "components": "puzzle",
    "compositor": "layers",
    "config": "settings",
    "core": "atom",
    "db": "database",
    "storage": "database",
    "dev": "wrench",
    "util": "wrench",
    "utils": "wrench",
    "editor": "pen-tool",
    "input": "gamepad-2",
    "math": "sigma",
    "navigation": "compass",
    "net": "network",
    "network": "network",
    "physics": "orbit",
    "preview": "eye",
    "providers": "cloud",
    "render": "monitor",
    "gfx": "monitor",
    "scene": "mountain",
    "scripting": "code",
    "script": "code",
    "server": "server",
    "time": "clock",
    "ui": "layout-dashboard",
}
FALLBACK = "box"


def glyph(name: str, missed: list[str]) -> str:
    """The SVG for a part, by whole name, then by its first known word."""
    words = [name, *re.split(r"[_-]", name)]
    icon = next((GLYPHS[w] for w in words if w in GLYPHS), None)
    if icon is None:
        missed.append(name)
    return (ICONS / f"{icon or FALLBACK}.svg").read_text().strip()
