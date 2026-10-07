"""Core model for grid-based two-fabric patchwork designs.

A design is a grid of cells.  Every cell is one finished grid unit and is
either a solid square of fabric L ('#'), a solid square of fabric D ('.'),
or a half-square triangle (HST) whose light corner is given by the numpad
digit: 7 = top-left, 9 = top-right, 1 = bottom-left, 3 = bottom-right.

The quilt is pieced with straight seams only.  `decompose` finds a
guillotine decomposition (every seam runs the full length of the unit
being assembled) with the fewest pieces, and among those the fewest
sub-assemblies.  Leaves are solid rectangles, single HST units, or
pre-made blocks (e.g. a star) that are assembled separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import sys

SOLID = {"#": "L", ".": "D"}
HST = set("7913")
H, V = "H", "V"  # H: horizontal seams (parts stacked top to bottom); V: vertical seams (parts side by side)


def load_grid(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith(";"):
                continue
            rows.append(line.strip())
    width = len(rows[0])
    for i, r in enumerate(rows):
        if len(r) != width:
            raise ValueError(f"row {i} has {len(r)} cells, expected {width}")
        bad = set(r) - set(SOLID) - HST
        if bad:
            raise ValueError(f"row {i}: unknown cell codes {bad}")
    return rows


@dataclass(frozen=True)
class Rect:
    r0: int
    c0: int
    r1: int  # exclusive
    c1: int  # exclusive

    @property
    def h(self):
        return self.r1 - self.r0

    @property
    def w(self):
        return self.c1 - self.c0

    def cells(self):
        for r in range(self.r0, self.r1):
            for c in range(self.c0, self.c1):
                yield r, c

    def contains(self, o: "Rect"):
        return self.r0 <= o.r0 and o.r1 <= self.r1 and self.c0 <= o.c0 and o.c1 <= self.c1

    def overlaps(self, o: "Rect"):
        return max(self.r0, o.r0) < min(self.r1, o.r1) and max(self.c0, o.c0) < min(self.c1, o.c1)


@dataclass
class Leaf:
    rect: Rect
    kind: str            # 'L', 'D' (solid fabric), 'HST', or 'BLOCK'
    corner: str = ""     # numpad digit for HST
    block: str = ""      # block name for BLOCK leaves
    label: str = ""


@dataclass
class Node:
    rect: Rect
    orient: str                       # H or V
    children: list = field(default_factory=list)
    name: str = ""


def decompose(rows, region: Rect, blocks=None, max_depth=None, first=None, max_len=None):
    """Return (tree, (pieces, sub_assemblies)) for `region`.

    blocks     {name: Rect} pre-made units; they appear as opaque BLOCK leaves
               (no seam may cross them, no piece may straddle their edges)
    max_depth  maximum number of nested sub-assembly levels (None = unlimited)
    first      force the orientation of the top-level seams (H or V)
    max_len    longest allowed piece, in grid units
    """
    blocks = dict(blocks or {})
    brects = [(n, b) for n, b in blocks.items() if region.contains(b)]
    R, C = len(rows), len(rows[0])
    pl = [[0] * (C + 1) for _ in range(R + 1)]
    pd = [[0] * (C + 1) for _ in range(R + 1)]
    for r in range(R):
        for c in range(C):
            ch = rows[r][c]
            pl[r + 1][c + 1] = pl[r][c + 1] + pl[r + 1][c] - pl[r][c] + (ch == "#")
            pd[r + 1][c + 1] = pd[r][c + 1] + pd[r + 1][c] - pd[r][c] + (ch == ".")

    def count(p, r0, c0, r1, c1):
        return p[r1][c1] - p[r0][c1] - p[r1][c0] + p[r0][c0]

    def leaf_kind(r0, c0, r1, c1):
        here = Rect(r0, c0, r1, c1)
        for n, b in brects:
            if b == here:
                return ("BLOCK", n)
            if b.overlaps(here):
                return None
        area = here.h * here.w
        if max_len and max(here.h, here.w) > max_len:
            return None
        if count(pl, r0, c0, r1, c1) == area:
            return ("L", "")
        if count(pd, r0, c0, r1, c1) == area:
            return ("D", "")
        if area == 1 and rows[r0][c0] in HST:
            return ("HST", "")
        return None

    def cut_ok(r0, c0, r1, c1, orient, k):
        for _, b in brects:
            if orient == H:
                if b.r0 < k < b.r1 and max(c0, b.c0) < min(c1, b.c1):
                    return False
            else:
                if b.c0 < k < b.c1 and max(r0, b.r0) < min(r1, b.r1):
                    return False
        return True

    sys.setrecursionlimit(100000)
    INF = (10 ** 9, 10 ** 9)

    @lru_cache(maxsize=None)
    def best(r0, c0, r1, c1, parent, d):
        kind = leaf_kind(r0, c0, r1, c1)
        if kind:
            return (1, 0), ("leaf",) + kind
        choice = None
        bc = INF
        orients = (H, V) if (parent is not None or first is None) else (first,)
        for orient in orients:
            new_node = 0 if parent == orient else 1
            nd = d if parent == orient else (None if d is None else d - 1)
            if nd is not None and nd < 0:
                continue
            cuts = range(r0 + 1, r1) if orient == H else range(c0 + 1, c1)
            for k in cuts:
                if brects and not cut_ok(r0, c0, r1, c1, orient, k):
                    continue
                if orient == H:
                    a, _ = best(r0, c0, k, c1, H, nd)
                    b, _ = best(k, c0, r1, c1, H, nd)
                else:
                    a, _ = best(r0, c0, r1, k, V, nd)
                    b, _ = best(r0, k, r1, c1, V, nd)
                if a == INF or b == INF:
                    continue
                cost = (a[0] + b[0], a[1] + b[1] + new_node)
                if cost < bc:
                    bc, choice = cost, ("cut", orient, k, nd)
        return bc, choice

    def build(r0, c0, r1, c1, parent, d):
        _, dec = best(r0, c0, r1, c1, parent, d)
        if dec is None:
            raise ValueError(f"no valid decomposition for {Rect(r0, c0, r1, c1)} under the given constraints")
        rect = Rect(r0, c0, r1, c1)
        if dec[0] == "leaf":
            kind, extra = dec[1], dec[2]
            if kind == "HST":
                return Leaf(rect, kind, corner=rows[r0][c0])
            if kind == "BLOCK":
                return Leaf(rect, kind, block=extra)
            return Leaf(rect, kind)
        _, orient, k, nd = dec
        if orient == H:
            parts = [build(r0, c0, k, c1, H, nd), build(k, c0, r1, c1, H, nd)]
        else:
            parts = [build(r0, c0, r1, k, V, nd), build(r0, k, r1, c1, V, nd)]
        kids = []
        for p in parts:
            if isinstance(p, Node) and p.orient == orient and p._merge:
                kids.extend(p.children)
            else:
                kids.append(p)
        node = Node(rect, orient, kids)
        node._merge = parent == orient  # continuation of the parent's seam direction
        return node

    tree = build(region.r0, region.c0, region.r1, region.c1, None, max_depth)
    cost, _ = best(region.r0, region.c0, region.r1, region.c1, None, max_depth)
    return tree, cost


def leaves(tree):
    if isinstance(tree, Leaf):
        yield tree
    else:
        for ch in tree.children:
            yield from leaves(ch)


def nodes(tree):
    if isinstance(tree, Node):
        yield tree
        for ch in tree.children:
            yield from nodes(ch)


def depth(tree):
    if isinstance(tree, Leaf):
        return 0
    return 1 + max(depth(c) for c in tree.children)


def check_tree(tree, rows, blocks=None):
    """Verify that a tree tiles its rectangle exactly, uses straight full-length
    seams only, and reproduces the design cell by cell."""
    blocks = blocks or {}

    def rec(t):
        if isinstance(t, Leaf):
            if t.kind == "BLOCK":
                assert blocks[t.block] == t.rect, (t.block, t.rect)
                return
            for r, c in t.rect.cells():
                ch = rows[r][c]
                if t.kind == "HST":
                    assert t.rect.h == t.rect.w == 1 and ch == t.corner, (t, ch)
                else:
                    assert SOLID.get(ch) == t.kind, (t, ch)
            return
        assert len(t.children) >= 2, t.rect
        pos = t.rect.r0 if t.orient == H else t.rect.c0
        for ch in t.children:
            if t.orient == H:
                assert ch.rect.c0 == t.rect.c0 and ch.rect.c1 == t.rect.c1 and ch.rect.r0 == pos, (t.rect, ch.rect)
                pos = ch.rect.r1
            else:
                assert ch.rect.r0 == t.rect.r0 and ch.rect.r1 == t.rect.r1 and ch.rect.c0 == pos, (t.rect, ch.rect)
                pos = ch.rect.c1
            rec(ch)
        assert pos == (t.rect.r1 if t.orient == H else t.rect.c1)

    rec(tree)
    return True
