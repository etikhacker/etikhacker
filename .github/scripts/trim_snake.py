#!/usr/bin/env python3
"""Crop generated Platane/snk SVGs to the contribution grid.

The stock generator includes a progress bar and an oversized viewBox. Here we
remove the bar, trim empty space and clip animated snake segments to the grid.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

GRID_WIDTH, GRID_HEIGHT = 848, 112
SNAKE_RE = re.compile(r'<rect class="s s\d+"[^>]*/>')
PROGRESS_RE = re.compile(r'<rect class="u u\d+"[^>]*/>')


def trim_svg(svg: str) -> str:
    root_match = re.match(r"<svg\b[^>]*>", svg)
    if root_match is None:
        raise ValueError("Expected an SVG root element")
    root = root_match.group(0)
    replacements = {
        "viewBox": f"0 0 {GRID_WIDTH} {GRID_HEIGHT}",
        "width": str(GRID_WIDTH),
        "height": str(GRID_HEIGHT),
    }
    for attribute, value in replacements.items():
        if not re.search(rf'\b{attribute}="[^"]*"', root):
            raise ValueError(f"Missing root SVG attribute: {attribute}")
        root = re.sub(rf'\b{attribute}="[^"]*"', f'{attribute}="{value}"', root, count=1)
    svg = root + svg[root_match.end():]
    svg = PROGRESS_RE.sub("", svg)

    matches = list(SNAKE_RE.finditer(svg))
    if not matches:
        raise ValueError("Cannot find animated snake rectangles")
    first, last = matches[0], matches[-1]
    elements = svg[first.start():last.end()]
    if SNAKE_RE.sub("", elements).strip():
        raise ValueError("Unexpected SVG nodes interleaved with snake rectangles")

    svg = (
        svg[:first.start()]
        + '<g clip-path="url(#snake-grid-clip)">'
        + elements
        + "</g>"
        + svg[last.end():]
    )
    defs = (
        '<defs><clipPath id="snake-grid-clip" clipPathUnits="userSpaceOnUse">'
        f'<rect x="0" y="0" width="{GRID_WIDTH}" height="{GRID_HEIGHT}"/>'
        "</clipPath></defs>"
    )
    svg = svg.replace(root, root + defs, 1)
    ET.fromstring(svg)
    return svg


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: trim_snake.py <generated-snake.svg> [...]")
    for name in sys.argv[1:]:
        path = Path(name)
        updated = trim_svg(path.read_text(encoding="utf-8"))
        path.write_text(updated, encoding="utf-8")
        print(f"Trimmed animated snake: {path}")


if __name__ == "__main__":
    main()
