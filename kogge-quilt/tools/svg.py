"""SVG drawing for modular designs. Fabric colours come from CSS custom
properties (--fS, --fU, ...) so one drawing serves every colourway."""
from __future__ import annotations

import math

from modular import H, Leaf, leaves

TRI = {  # the corner triangle of an HST, unit-cell coordinates
    "7": [(0, 0), (1, 0), (0, 1)],
    "9": [(0, 0), (1, 0), (1, 1)],
    "1": [(0, 0), (0, 1), (1, 1)],
    "3": [(1, 0), (0, 1), (1, 1)],
}
OPP = {  # the other half
    "7": [(1, 0), (1, 1), (0, 1)],
    "9": [(0, 0), (0, 1), (1, 1)],
    "1": [(0, 0), (1, 0), (1, 1)],
    "3": [(0, 0), (1, 0), (0, 1)],
}
CORNER_WORDS = {"7": "top left", "9": "top right", "1": "bottom left", "3": "bottom right"}


def f(x):
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def corner_point(corner, x, y, size):
    return (x + (size if corner in "93" else 0), y + (size if corner in "13" else 0))


def arc_ends(corner, cx, cy, R):
    """Ends of the quarter arc of radius R round (cx, cy), opening into the
    unit, in the order the arc runs (clockwise on screen)."""
    if corner == "7":
        return (cx + R, cy), (cx, cy + R)
    if corner == "9":
        return (cx, cy + R), (cx - R, cy)
    if corner == "3":
        return (cx - R, cy), (cx, cy - R)
    return (cx, cy - R), (cx + R, cy)


def quarter_path(corner, cx, cy, R):
    """Quarter disc of radius R centred at (cx, cy), opening into the unit."""
    p1, p2 = arc_ends(corner, cx, cy, R)
    return (f"M{f(cx)},{f(cy)} L{f(p1[0])},{f(p1[1])} "
            f"A{f(R)},{f(R)} 0 0 1 {f(p2[0])},{f(p2[1])} Z")


def quarter_arc(corner, cx, cy, R):
    """Just the arc of a quarter disc, as an open path."""
    p1, p2 = arc_ends(corner, cx, cy, R)
    return f"M{f(p1[0])},{f(p1[1])} A{f(R)},{f(R)} 0 0 1 {f(p2[0])},{f(p2[1])}"


def qc_shapes(unit, corner, x, y, s):
    S = unit.n * s
    out = [f'<rect class="f{unit.bg}" x="{f(x)}" y="{f(y)}" width="{f(S)}" height="{f(S)}"/>']
    cx, cy = corner_point(corner, x, y, S)
    for r, fab in unit.discs():
        out.append(f'<path class="f{fab}" d="{quarter_path(corner, cx, cy, r * s)}"/>')
    return "".join(out)


def hst_shapes(corner, a, b, x, y, s):
    pa = " ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in TRI[corner])
    pb = " ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in OPP[corner])
    return f'<polygon class="f{b}" points="{pb}"/><polygon class="f{a}" points="{pa}"/>'


def leaf_shapes(lf, x, y, s):
    if lf.kind == "solid":
        return f'<rect class="f{lf.fabric}" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>'
    if lf.kind == "hst":
        return hst_shapes(lf.corner, lf.a, lf.b, x, y, s)
    return qc_shapes(lf.unit, lf.corner, x, y, s)


def label_text(lf, x, y, s, fs=None):
    if lf.kind != "solid" or not lf.label:
        return ""
    pw, ph = lf.rect.w * s, lf.rect.h * s
    size = fs or max(8.5, min(13, s * 0.36))
    cx, cy = x + pw / 2, y + ph / 2
    rot = ""
    if ph > pw * 1.6 and pw < size * 2.6:
        rot = f' transform="rotate(-90 {f(cx)} {f(cy)})"'
    return f'<text class="lb lb{lf.fabric}" x="{f(cx)}" y="{f(cy)}" font-size="{f(size)}"{rot}>{lf.label}</text>'


def hst_icon(corner, a, b, size=15):
    return (f'<svg class="ico" viewBox="0 0 {size} {size}" width="{size}" height="{size}" aria-hidden="true">'
            f'{hst_shapes(corner, a, b, 0, 0, size)}</svg>')


def qc_icon(unit, corner, size=15):
    s = size / unit.n
    return (f'<svg class="ico" viewBox="0 0 {size} {size}" width="{size}" height="{size}" aria-hidden="true">'
            f'{qc_shapes(unit, corner, 0, 0, s)}</svg>')


def svg_wrap(body, w, h, cls="dia", title=None, extra_defs=""):
    t = f"<title>{title}</title>" if title else ""
    defs = f"<defs>{extra_defs}</defs>" if extra_defs else ""
    return (f'<svg class="{cls}" viewBox="0 0 {f(w)} {f(h)}" width="{f(w)}" height="{f(h)}" '
            f'role="img" xmlns="http://www.w3.org/2000/svg">{t}{defs}{body}</svg>')


def explode(tree, s, gap=7.0):
    """Lay out a tree with gaps between siblings; deeper levels get smaller gaps.
    Returns (items, w, h); items are (leaf, x, y)."""
    def depth(t):
        return 0 if isinstance(t, Leaf) else 1 + max(depth(c) for c in t.children)

    D = depth(tree)
    items = []

    def lay(t, x, y, lvl):
        if isinstance(t, Leaf):
            items.append((t, x, y))
            return t.rect.w * s, t.rect.h * s
        g = gap * max(1, D - lvl)
        cx, cy, W, Hh = x, y, 0, 0
        for i, ch in enumerate(t.children):
            w, h = lay(ch, cx, cy, lvl + 1)
            last = i == len(t.children) - 1
            if t.orient == H:
                cy += h + (0 if last else g)
                W = max(W, w)
            else:
                cx += w + (0 if last else g)
                Hh = max(Hh, h)
        return (W, cy - y) if t.orient == H else (cx - x, Hh)

    w, h = lay(tree, 0, 0, 0)
    return items, w, h


def draw_exploded(tree, s, gap=7.0, labels=True, pad=2):
    items, w, h = explode(tree, s, gap)
    parts, labs = [], []
    for lf, x, y in items:
        x += pad
        y += pad
        parts.append(leaf_shapes(lf, x, y, s))
        parts.append(f'<rect class="edge" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
        if labels:
            labs.append(label_text(lf, x, y, s))
    return "".join(parts) + "".join(labs), w + 2 * pad, h + 2 * pad, items


def wave_lines(x0, y0, w, h, gap, amp, wl):
    d = []
    y = y0 + gap / 2
    n = int(math.ceil(w / wl)) * 2 + 2
    while y < y0 + h:
        d.append(f"M{f(x0 - wl)},{f(y)} q{f(wl / 4)},{f(-amp)} {f(wl / 2)},0" + f" t{f(wl / 2)},0" * n)
        y += gap
    return " ".join(d)


def hlines(x0, y0, w, h, gap):
    out, y = [], y0 + gap / 2
    while y < y0 + h:
        out.append(f"M{f(x0)},{f(y)} h{f(w)}")
        y += gap
    return " ".join(out)
