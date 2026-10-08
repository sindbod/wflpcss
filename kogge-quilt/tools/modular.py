"""Model and piecing solver for multi-fabric modular patchwork.

A design is a grid of cells. Every cell belongs to one module:

    solid   a square of one fabric (neighbouring solid squares of the same
            fabric can be cut as one rectangle)
    hst     a half-square triangle unit made of two fabrics
    qc      a quarter-circle unit of n x n cells: a background square with a
            quarter disc (and optional smaller discs on top) appliquéd on it,
            centred on one corner

The quilt top is pieced with straight seams only. `decompose` finds a
guillotine decomposition (every seam runs the full length of the unit being
assembled) with the fewest pieces, then the fewest sub-assemblies. Solid
rectangles, single HST cells and whole quarter-circle units are the leaves.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import lru_cache

H, V = "H", "V"   # H: parts stacked top to bottom; V: parts side by side
CORNERS = "7913"  # numpad corners: 7 top-left, 9 top-right, 1 bottom-left, 3 bottom-right


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

    def contains(self, o):
        return self.r0 <= o.r0 and o.r1 <= self.r1 and self.c0 <= o.c0 and o.c1 <= self.c1

    def overlaps(self, o):
        return max(self.r0, o.r0) < min(self.r1, o.r1) and max(self.c0, o.c0) < min(self.c1, o.c1)


@dataclass
class QCUnit:
    uid: int
    rect: Rect
    corner: str
    fabric: str
    bg: str
    rings: tuple = ()  # ((radius in cells, fabric), ...) largest first

    @property
    def n(self):
        return self.rect.w

    def discs(self):
        """All appliqué discs, largest first: (radius in cells, fabric)."""
        return ((float(self.n), self.fabric),) + tuple(self.rings)


class Design:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.cells = [[("S", bg) for _ in range(w)] for _ in range(h)]
        self.units = {}
        self._uid = 0

    # ------------------------------------------------------------ drawing
    def _free(self, x, y):
        c = self.cells[y][x]
        if c[0] == "Q":
            u = self.units.pop(c[1])
            for r, cc in u.rect.cells():
                self.cells[r][cc] = ("S", u.bg)

    def base(self, x, y):
        c = self.cells[y][x]
        if c[0] == "S":
            return c[1]
        if c[0] == "H":
            return c[3]
        return self.units[c[1]].bg

    def fill(self, x, y, w, h, fabric):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= xx < self.w and 0 <= yy < self.h:
                    self._free(xx, yy)
                    self.cells[yy][xx] = ("S", fabric)

    def hst(self, x, y, corner, a, b=None):
        assert corner in CORNERS
        b = b or self.base(x, y)
        self._free(x, y)
        self.cells[y][x] = ("H", corner, a, b)

    def qc(self, x, y, n, corner, a, b=None, rings=None):
        assert corner in CORNERS
        b = b or self.base(x, y)
        for yy in range(y, y + n):
            for xx in range(x, x + n):
                self._free(xx, yy)
        self._uid += 1
        rings = tuple(sorted(((float(r), f) for r, f in (rings or [])), reverse=True))
        assert all(0 < r < n for r, _ in rings), "rings must be smaller than the unit"
        self.units[self._uid] = QCUnit(self._uid, Rect(y, x, y + n, x + n), corner, a, b, rings)
        for yy in range(y, y + n):
            for xx in range(x, x + n):
                self.cells[yy][xx] = ("Q", self._uid)

    # ------------------------------------------------------------ queries
    def fabrics(self):
        out = set()
        for row in self.cells:
            for c in row:
                if c[0] == "S":
                    out.add(c[1])
                elif c[0] == "H":
                    out |= {c[2], c[3]}
        for u in self.units.values():
            out |= {u.fabric, u.bg} | {f for _, f in u.rings}
        return out

    def check(self):
        """Every cell belongs to exactly one module; units are intact."""
        seen = {}
        for r in range(self.h):
            for c in range(self.w):
                cell = self.cells[r][c]
                if cell[0] == "Q":
                    u = self.units[cell[1]]
                    assert u.rect.r0 <= r < u.rect.r1 and u.rect.c0 <= c < u.rect.c1
                    seen[cell[1]] = seen.get(cell[1], 0) + 1
        for uid, u in self.units.items():
            assert seen.get(uid) == u.rect.w * u.rect.h, f"unit {uid} is broken"
        return True


# --------------------------------------------------------------- the tree
@dataclass
class Leaf:
    rect: Rect
    kind: str               # "solid", "hst", "qc"
    fabric: str = ""        # solid fabric
    corner: str = ""        # hst / qc corner
    a: str = ""             # hst: fabric of the corner triangle
    b: str = ""             # hst: other fabric
    unit: QCUnit = None     # qc unit
    label: str = ""


@dataclass
class Node:
    rect: Rect
    orient: str
    children: list = field(default_factory=list)
    name: str = ""


def leaves(t):
    if isinstance(t, Leaf):
        yield t
    else:
        for c in t.children:
            yield from leaves(c)


def depth(t):
    return 0 if isinstance(t, Leaf) else 1 + max(depth(c) for c in t.children)


def decompose(d: Design, region: Rect, max_depth=None, first=None, max_len=None, blocks=()):
    """Fewest pieces, then fewest sub-assemblies, straight seams only.

    blocks  extra rectangles that must stay whole (pieced as their own unit)."""
    R, C = d.h, d.w
    fab_ids = {f: i for i, f in enumerate(sorted(d.fabrics()))}
    # prefix sums of "solid cell of fabric f"
    pref = {f: [[0] * (C + 1) for _ in range(R + 1)] for f in fab_ids}
    for r in range(R):
        for c in range(C):
            cell = d.cells[r][c]
            for f, p in pref.items():
                p[r + 1][c + 1] = p[r][c + 1] + p[r + 1][c] - p[r][c] + (cell[0] == "S" and cell[1] == f)
    opaque = [u.rect for u in d.units.values() if region.contains(u.rect)] + [b for b in blocks if region.contains(b)]

    def count(p, r0, c0, r1, c1):
        return p[r1][c1] - p[r0][c1] - p[r1][c0] + p[r0][c0]

    def leaf_kind(r0, c0, r1, c1):
        here = Rect(r0, c0, r1, c1)
        for b in opaque:
            if b == here:
                cell = d.cells[r0][c0]
                if cell[0] == "Q" and d.units[cell[1]].rect == here:
                    return ("qc", cell[1])
                return ("block", here)
            if b.overlaps(here):
                return None
        if max_len and max(here.h, here.w) > max_len:
            return None
        area = here.h * here.w
        cell = d.cells[r0][c0]
        if cell[0] == "S" and count(pref[cell[1]], r0, c0, r1, c1) == area:
            return ("solid", cell[1])
        if area == 1 and cell[0] == "H":
            return ("hst", None)
        return None

    def cut_ok(r0, c0, r1, c1, orient, k):
        for b in opaque:
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
    def best(r0, c0, r1, c1, parent, dl):
        kind = leaf_kind(r0, c0, r1, c1)
        if kind:
            return (1, 0), ("leaf",) + kind
        choice, bc = None, INF
        orients = (H, V) if (parent is not None or first is None) else (first,)
        for orient in orients:
            new_node = 0 if parent == orient else 1
            nd = dl if parent == orient else (None if dl is None else dl - 1)
            if nd is not None and nd < 0:
                continue
            cuts = range(r0 + 1, r1) if orient == H else range(c0 + 1, c1)
            for k in cuts:
                if not cut_ok(r0, c0, r1, c1, orient, k):
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

    def build(r0, c0, r1, c1, parent, dl):
        _, dec = best(r0, c0, r1, c1, parent, dl)
        if dec is None:
            raise ValueError(f"no straight-seam decomposition for {Rect(r0, c0, r1, c1)}")
        rect = Rect(r0, c0, r1, c1)
        if dec[0] == "leaf":
            kind, extra = dec[1], dec[2]
            if kind == "solid":
                return Leaf(rect, "solid", fabric=extra)
            if kind == "hst":
                _, corner, a, b = d.cells[r0][c0]
                return Leaf(rect, "hst", corner=corner, a=a, b=b)
            if kind == "qc":
                u = d.units[extra]
                return Leaf(rect, "qc", corner=u.corner, unit=u)
            return Leaf(rect, "block")
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
        node._merge = parent == orient
        return node

    tree = build(region.r0, region.c0, region.r1, region.c1, None, max_depth)
    cost, _ = best(region.r0, region.c0, region.r1, region.c1, None, max_depth)
    return tree, cost


def check_tree(tree, d: Design):
    """The tree tiles its rectangle with straight full-length seams and reproduces the design."""
    def rec(t):
        if isinstance(t, Leaf):
            for r, c in t.rect.cells():
                cell = d.cells[r][c]
                if t.kind == "solid":
                    assert cell == ("S", t.fabric), (t.rect, cell)
                elif t.kind == "hst":
                    assert t.rect.w == t.rect.h == 1 and cell == ("H", t.corner, t.a, t.b), (t.rect, cell)
                elif t.kind == "qc":
                    assert cell == ("Q", t.unit.uid) and t.unit.rect == t.rect, (t.rect, cell)
            return
        assert len(t.children) >= 2
        pos = t.rect.r0 if t.orient == H else t.rect.c0
        for ch in t.children:
            if t.orient == H:
                assert ch.rect.c0 == t.rect.c0 and ch.rect.c1 == t.rect.c1 and ch.rect.r0 == pos
                pos = ch.rect.r1
            else:
                assert ch.rect.r0 == t.rect.r0 and ch.rect.r1 == t.rect.r1 and ch.rect.c0 == pos
                pos = ch.rect.c1
            rec(ch)
        assert pos == (t.rect.r1 if t.orient == H else t.rect.c1)
    rec(tree)
    covered = [[0] * d.w for _ in range(d.h)]
    for lf in leaves(tree):
        for r, c in lf.rect.cells():
            covered[r][c] += 1
    for r, c in tree.rect.cells():
        assert covered[r][c] == 1, ("coverage", r, c)
    return True
