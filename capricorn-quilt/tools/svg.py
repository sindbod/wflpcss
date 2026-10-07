"""SVG drawing helpers. Fabric colours come from CSS custom properties
(--fabL, --fabD, --onL, --onD) so one drawing serves every colourway."""
from __future__ import annotations

import math
import random

from quilt import H, Leaf, Node, leaves

TRI = {  # light triangle for each HST code, in unit-cell coordinates
    "7": [(0, 0), (1, 0), (0, 1)],
    "9": [(0, 0), (1, 0), (1, 1)],
    "1": [(0, 0), (0, 1), (1, 1)],
    "3": [(1, 0), (0, 1), (1, 1)],
}


DTRI = {  # dark half of each HST
    "7": [(1, 0), (1, 1), (0, 1)],
    "9": [(0, 0), (0, 1), (1, 1)],
    "1": [(0, 0), (1, 0), (1, 1)],
    "3": [(0, 0), (1, 0), (0, 1)],
}


def f(x):
    """Compact number formatting for SVG coordinates."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def cell_shapes(kind, corner, x, y, w, h, s):
    """SVG for one leaf drawn at pixel (x, y), w x h grid units, s px per unit."""
    if kind in ("L", "D"):
        return f'<rect class="f{kind}" x="{f(x)}" y="{f(y)}" width="{f(w * s)}" height="{f(h * s)}"/>'
    pts = " ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in TRI[corner])
    dpts = " ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in DTRI[corner])
    return f'<polygon class="fD" points="{dpts}"/><polygon class="fL" points="{pts}"/>'


def hst_icon(corner, size=15):
    pts = " ".join(f"{f(u * size)},{f(v * size)}" for u, v in TRI[corner])
    return (f'<svg class="hst-ico" viewBox="0 0 {size} {size}" width="{size}" height="{size}" aria-hidden="true">'
            f'<rect class="fD" width="{size}" height="{size}"/><polygon class="fL" points="{pts}"/></svg>')


CORNER_WORDS = {"7": "light top left", "9": "light top right", "1": "light bottom left", "3": "light bottom right"}


def label_text(lf, x, y, w, h, s, fs=None):
    if lf.kind not in ("L", "D") or not lf.label:
        return ""
    pw, ph = w * s, h * s
    size = fs or max(8.5, min(13, s * 0.36))
    cls = "lbL" if lf.kind == "L" else "lbD"
    cx, cy = x + pw / 2, y + ph / 2
    rot = ""
    if ph > pw * 1.6 and pw < size * 2.4:
        rot = f' transform="rotate(-90 {f(cx)} {f(cy)})"'
    return f'<text class="{cls}" x="{f(cx)}" y="{f(cy)}" font-size="{f(size)}"{rot}>{lf.label}</text>'


# ------------------------------------------------------------ flat drawing
def draw_flat(tree, s, origin=None, labels=False, seams=False, block_trees=None, expand_blocks=True,
              seam_cls="seam"):
    """Leaves of `tree` in their true positions. Returns svg fragment."""
    r0, c0 = origin if origin else (tree.rect.r0, tree.rect.c0)
    out, lab, outl = [], [], []
    for lf in leaves(tree):
        if lf.kind == "BLOCK" and block_trees is not None:
            if expand_blocks:
                for l2 in leaves(block_trees[lf.block]):
                    x, y = (l2.rect.c0 - c0) * s, (l2.rect.r0 - r0) * s
                    out.append(cell_shapes(l2.kind, l2.corner, x, y, l2.rect.w, l2.rect.h, s))
                    if labels:
                        lab.append(label_text(l2, x, y, l2.rect.w, l2.rect.h, s))
                    if seams:
                        outl.append(f'<rect class="{seam_cls}" x="{f(x)}" y="{f(y)}" width="{f(l2.rect.w * s)}" height="{f(l2.rect.h * s)}"/>')
            continue
        x, y = (lf.rect.c0 - c0) * s, (lf.rect.r0 - r0) * s
        out.append(cell_shapes(lf.kind, lf.corner, x, y, lf.rect.w, lf.rect.h, s))
        if labels:
            lab.append(label_text(lf, x, y, lf.rect.w, lf.rect.h, s))
        if seams:
            outl.append(f'<rect class="{seam_cls}" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
    return "".join(out) + "".join(outl) + "".join(lab)


# -------------------------------------------------------- exploded drawing
def explode(tree, s, gap=7.0, block_trees=None, expand_blocks=False, block_gap=None):
    """Lay out a tree with gaps between siblings; deeper levels get smaller gaps.

    Returns (items, w, h) where items are (leaf, x, y, in_block) tuples."""
    def depth(t):
        if isinstance(t, Leaf):
            if t.kind == "BLOCK" and expand_blocks and block_trees is not None:
                return depth(block_trees[t.block])
            return 0
        return 1 + max(depth(c) for c in t.children)

    D = depth(tree)
    items = []

    def lay(t, x, y, lvl, in_block=None):
        if isinstance(t, Leaf):
            if t.kind == "BLOCK" and block_trees is not None:
                if expand_blocks:
                    return lay(block_trees[t.block], x, y, lvl, in_block=t.block)
                bt = block_trees[t.block]
                for l2 in leaves(bt):
                    items.append((l2, x + (l2.rect.c0 - t.rect.c0) * s, y + (l2.rect.r0 - t.rect.r0) * s, t.block))
                items.append((t, x, y, "frame"))
                return t.rect.w * s, t.rect.h * s
            items.append((t, x, y, in_block))
            return t.rect.w * s, t.rect.h * s
        g = gap * max(1, D - lvl) if block_gap is None or in_block is None else block_gap
        cx, cy = x, y
        W = Hh = 0
        for i, ch in enumerate(t.children):
            w, h = lay(ch, cx, cy, lvl + 1, in_block)
            if t.orient == H:
                cy += h + (g if i < len(t.children) - 1 else 0)
                W = max(W, w)
            else:
                cx += w + (g if i < len(t.children) - 1 else 0)
                Hh = max(Hh, h)
        if t.orient == H:
            return W, cy - y
        return cx - x, Hh

    w, h = lay(tree, 0, 0, 0)
    return items, w, h


def draw_exploded(tree, s, gap=7.0, block_trees=None, expand_blocks=False, labels=True, pad=2):
    items, w, h = explode(tree, s, gap, block_trees, expand_blocks)
    parts, labs, frames = [], [], []
    for lf, x, y, tag in items:
        x += pad
        y += pad
        if tag == "frame":
            frames.append(f'<rect class="blockframe" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
            continue
        parts.append(cell_shapes(lf.kind, lf.corner, x, y, lf.rect.w, lf.rect.h, s))
        parts.append(f'<rect class="edge" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
        if labels and tag is None:
            labs.append(label_text(lf, x, y, lf.rect.w, lf.rect.h, s))
    return "".join(parts) + "".join(frames) + "".join(labs), w + 2 * pad, h + 2 * pad


def svg_wrap(body, w, h, cls="dia", title=None, extra_defs=""):
    t = f"<title>{title}</title>" if title else ""
    defs = f"<defs>{extra_defs}</defs>" if extra_defs else ""
    return (f'<svg class="{cls}" viewBox="0 0 {f(w)} {f(h)}" width="{f(w)}" height="{f(h)}" '
            f'role="img" xmlns="http://www.w3.org/2000/svg">{t}{defs}{body}</svg>')


# ------------------------------------------------------- quilting preview
def meander_path(x0, y0, w, h, step, seed=4):
    """A free-motion style meander: wavy horizontal passes with loops."""
    rnd = random.Random(seed)
    d = []
    y = y0 + step / 2
    direction = 1
    while y < y0 + h:
        xs = [x0 - step, x0 + w + step] if direction > 0 else [x0 + w + step, x0 - step]
        n = int(w / (step * 1.1)) + 2
        pts = []
        for i in range(n + 1):
            t = i / n
            x = xs[0] + (xs[1] - xs[0]) * t
            yy = y + math.sin(t * math.pi * n / 1.3 + rnd.random()) * step * 0.28
            pts.append((x, yy))
        d.append(f"M{f(pts[0][0])},{f(pts[0][1])}")
        for i in range(1, len(pts)):
            px, py = pts[i - 1]
            qx, qy = pts[i]
            cx = (px + qx) / 2
            cy = py + (rnd.random() - 0.5) * step * 0.9
            d.append(f"Q{f(cx)},{f(cy)} {f(qx)},{f(qy)}")
        y += step
        direction *= -1
    return " ".join(d)
