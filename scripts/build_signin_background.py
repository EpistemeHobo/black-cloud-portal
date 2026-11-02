"""Draws the twinkling dots for Cognito's sign-in page, and puts them in the stack template.

The same look as the portal's own sign-in page (AuthBackground.tsx), but as one SVG file
that animates itself, since Cognito's page runs no code of ours. Cognito takes it as text
inside the template, so it has to be small: a template sent directly may be 51,200 bytes.
That's why it's one small tile repeated, with waves that join up at its edges. The tile is
an SVG pattern, since Cognito refuses <use>, and each twinkle group fades as one rectangle.

Run: python scripts/build_signin_background.py
"""
import base64
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG_FILE = ROOT / "infra" / "signin-background.svg"
TEMPLATE = ROOT / "infra" / "full-stack.yaml"

PITCH = 6
CELL_W, CELL_H = 3 * PITCH, 4 * PITCH
# Each twinkle group's tile, in Braille cells, so the edges line up. The sizes differ so
# that the groups' repeats drift apart and the eye can't find a grid.
TILE_CELLS = [(26, 14), (25, 15), (27, 13), (23, 16), (29, 12), (24, 15), (28, 13), (22, 17)]
VIEW_W, VIEW_H = 1600, 1000
# (cycles across, cycles down, phase, strength): whole cycles, so the waves join up.
WAVES = [(1, 1, 0.0, 1.0), (2, -1, 1.0, 0.5), (3, 2, 2.0, 0.25), (1, 3, 3.0, 0.125)]
PEAK = sum(w[3] for w in WAVES)
TWINKLE_SECONDS = [1.05, 1.7, 0.85, 1.4, 1.85, 0.98, 1.53, 1.2]
# (opacity, colour, width, halo width)
LEVELS = [(0.3, "#8f9cff", 2.2, 0), (0.5, "#a9b4ff", 2.2, 0), (0.75, "#cdd3ff", 2.2, 0), (1, "#fff", 2.4, 7)]


def rhythm(x: int, y: int, width: int, height: int, shift: float) -> float:
    """Roughly 0..1: where the dot cells are dense and where they thin out, in a tile of this size."""
    total = sum(strength * math.sin(2 * math.pi * (a * x / width + b * y / height) + phase + shift)
                for a, b, phase, strength in WAVES)
    return (total / PEAK + 1) / 2


def noise(x: int, y: int, salt: int = 0) -> float:
    """A fixed pseudo-random number in 0..1 for a position: the same dots on every build."""
    n = math.sin(x * 12.9898 + y * 78.233 + salt * 37.719) * 43758.5453
    return n - math.floor(n)


def build_svg() -> str:
    patterns, layers = "", ""
    for g, (cols, rows) in enumerate(TILE_CELLS):
        tile_w, tile_h = cols * CELL_W, rows * CELL_H
        levels = [[] for _ in LEVELS]
        for top in range(PITCH, tile_h, CELL_H):
            for left in range(PITCH, tile_w, CELL_W):
                # A different start for each group, so their dense patches don't line up.
                t = rhythm(left + CELL_W // 2, top + CELL_H // 2, tile_w, tile_h, g * 2.4)
                density = min(0.95, max(0.04, (t - 0.25) * 1.6))
                for row in range(3):
                    for col in range(2):
                        x, y = left + col * PITCH, top + row * PITCH
                        if noise(x, y) > density or int(noise(x, y, 3) * len(TILE_CELLS)) != g:
                            continue
                        glow = min(0.999, max(0, t * 0.9 + (noise(x, y, 1) - 0.5) * 0.35))
                        levels[int(glow * len(LEVELS))].append(f"M{x} {y}h0")
        body = ""
        for (opacity, color, width, halo), dots in zip(LEVELS, levels):
            d = "".join(dots)
            if d and halo:
                body += f'<path d="{d}" stroke="#d9ccff" stroke-opacity=".22" stroke-width="{halo}"/>'
            if d:
                body += f'<path d="{d}" stroke="{color}" stroke-opacity="{opacity}" stroke-width="{width}"/>'
        patterns += f'<pattern id="p{g}" width="{tile_w}" height="{tile_h}" patternUnits="userSpaceOnUse">{body}</pattern>'
        layers += (f'<rect class="t" width="{VIEW_W}" height="{VIEW_H}" fill="url(#p{g})" '
                   f'style="animation-duration:{TWINKLE_SECONDS[g]}s;animation-delay:-{g * 0.85 % TWINKLE_SECONDS[g]:.2f}s"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEW_W} {VIEW_H}" preserveAspectRatio="xMidYMid slice">'
        "<style>.t{animation:w ease-in-out infinite alternate}path{fill:none;stroke-linecap:round}"
        "@keyframes w{0%{opacity:1}45%{opacity:.55}100%{opacity:.22}}"
        "@media(prefers-reduced-motion:reduce){.t{animation:none}}</style><defs>"
        '<linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#090a11"/>'
        '<stop offset=".55" stop-color="#0f0f19"/><stop offset="1" stop-color="#130f1c"/></linearGradient>'
        '<radialGradient id="l" cx=".05" cy=".75" r=".5"><stop offset="0" stop-color="#2f3055" stop-opacity=".55"/>'
        '<stop offset="1" stop-color="#2f3055" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="r" cx=".95" cy=".45" r=".45"><stop offset="0" stop-color="#3b3056" stop-opacity=".5"/>'
        f'<stop offset="1" stop-color="#3b3056" stop-opacity="0"/></radialGradient>{patterns}</defs>'
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#b)"/><rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#l)"/>'
        f'<rect width="{VIEW_W}" height="{VIEW_H}" fill="url(#r)"/>{layers}</svg>'
    )


def main() -> None:
    svg = build_svg()
    SVG_FILE.write_text(svg, encoding="utf-8", newline="\n")
    encoded = base64.b64encode(svg.encode()).decode()
    # newline="": the template keeps whichever line endings it has.
    with TEMPLATE.open(encoding="utf-8", newline="") as f:
        template = f.read()
    template, replaced = re.subn(r"(?m)^( *Bytes: )[^\r\n]*", lambda m: m.group(1) + encoded, template)
    if replaced != 1:
        raise SystemExit("Expected exactly one Bytes: line in the template.")
    with TEMPLATE.open("w", encoding="utf-8", newline="") as f:
        f.write(template)
    print(f"{len(svg)} bytes of SVG; the template is now {len(template.encode())} bytes (limit 51200).")


if __name__ == "__main__":
    main()
