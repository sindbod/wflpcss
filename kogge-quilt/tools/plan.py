"""Turn the Kogge design into a sewing plan: sections, piece codes, units,
appliqué discs, cutting plans and fabric amounts, metric and imperial."""
from __future__ import annotations

import importlib.util
import math
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from modular import H, V, Design, Leaf, Node, Rect, check_tree, decompose, depth, leaves

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("kogge_design", ROOT / "design" / "kogge.py")
K = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(K)

FABRICS = K.FABRICS
ORDER = list(FABRICS)            # fabric keys in the order the design lists them
NROWS, NCOLS = K.H, K.W


def make_design():
    d = Design(K.W, K.H, "S")
    K.build(d)
    d.check()
    return d


DESIGN = make_design()
MAX_LEN = 19  # longest piece in grid units: 19 x 5 cm + 1.5 = 96.5 cm, 19 x 2" + 1/2" = 38 1/2"


# ------------------------------------------------------------------ systems
@dataclass
class System:
    key: str
    unit: float
    sa: float
    hst_cut: float
    wof: float
    binding_w: float
    round_to: float
    extra: float
    long_extra: float
    margin: float      # spare around an appliqué disc when cutting its fabric square

    def cut(self, n):
        return n * self.unit + 2 * self.sa

    def fmt(self, x, unit=True):
        if self.key == "cm":
            s = f"{x:.1f}".rstrip("0").rstrip(".")
            return f"{s} cm" if unit else s
        return fmt_inch(x) + ("″" if unit else "")

    def dims(self, a, b, unit=True):
        if self.key == "cm":
            return f"{self.fmt(a, False)} × {self.fmt(b, False)}" + (" cm" if unit else "")
        return f"{self.fmt(a, False)} × {self.fmt(b)}" if unit else f"{self.fmt(a, False)} × {self.fmt(b, False)}"

    def length(self, x):
        steps = math.ceil(x / self.round_to - 1e-9)
        val = steps * self.round_to
        if self.key == "cm":
            return f"{val / 100:.2f}".rstrip("0").rstrip(".") + " m", val
        return fmt_yards(Fraction(val / 36).limit_denominator(8)), val


GLYPH = {Fraction(1, 8): "⅛", Fraction(1, 4): "¼", Fraction(3, 8): "⅜", Fraction(1, 2): "½",
         Fraction(5, 8): "⅝", Fraction(3, 4): "¾", Fraction(7, 8): "⅞"}


def fmt_inch(x):
    whole = int(math.floor(x + 1e-9))
    frac = Fraction(x - whole).limit_denominator(8)
    if frac == 1:
        whole, frac = whole + 1, Fraction(0)
    if frac == 0:
        return str(whole)
    return (str(whole) if whole else "") + GLYPH[frac]


def fmt_yards(yd: Fraction):
    whole = yd.numerator // yd.denominator
    frac = yd - whole
    if frac == 0:
        return f"{whole} yd"
    return f"{whole if whole else ''}{GLYPH[frac]} yd"


SYSTEMS = {
    "cm": System("cm", unit=5.0, sa=0.75, hst_cut=8.0, wof=105.0, binding_w=6.0, round_to=10.0,
                 extra=10.0, long_extra=2.0, margin=1.0),
    "in": System("in", unit=2.0, sa=0.25, hst_cut=3.0, wof=40.0, binding_w=2.5, round_to=4.5,
                 extra=4.5, long_extra=0.75, margin=0.5),
}


# ------------------------------------------------------------- the tree
def rebalance(t):
    """Where a long run had to be split for the fabric width, put the seam in the middle."""
    if isinstance(t, Leaf):
        return t
    kids = [rebalance(c) for c in t.children]
    i = 0
    while i < len(kids) - 1:
        a, b = kids[i], kids[i + 1]
        if (isinstance(a, Leaf) and isinstance(b, Leaf) and a.kind == b.kind == "solid" and a.fabric == b.fabric):
            if t.orient == V and a.rect.r0 == b.rect.r0 and a.rect.r1 == b.rect.r1:
                total = b.rect.c1 - a.rect.c0
                mid = a.rect.c0 + total // 2
                kids[i] = Leaf(Rect(a.rect.r0, a.rect.c0, a.rect.r1, mid), "solid", fabric=a.fabric)
                kids[i + 1] = Leaf(Rect(a.rect.r0, mid, a.rect.r1, b.rect.c1), "solid", fabric=a.fabric)
            elif t.orient == H and a.rect.c0 == b.rect.c0 and a.rect.c1 == b.rect.c1:
                total = b.rect.r1 - a.rect.r0
                mid = a.rect.r0 + total // 2
                kids[i] = Leaf(Rect(a.rect.r0, a.rect.c0, mid, a.rect.c1), "solid", fabric=a.fabric)
                kids[i + 1] = Leaf(Rect(mid, a.rect.c0, b.rect.r1, a.rect.c1), "solid", fabric=a.fabric)
        i += 1
    n = Node(t.rect, t.orient, kids, t.name)
    return n


def build_tree():
    tree, cost = decompose(DESIGN, Rect(0, 0, NROWS, NCOLS), max_depth=4, first=H, max_len=MAX_LEN)
    tree = rebalance(tree)
    check_tree(tree, DESIGN)
    for i, s in enumerate(tree.children, 1):
        s.name = f"section {i}"
    return tree


TREE = build_tree()
SECTIONS = TREE.children
PIECES = list(leaves(TREE))


# ------------------------------------------------------------ labelling
def solid_key(lf):
    a, b = sorted((lf.rect.w, lf.rect.h))
    return (lf.fabric, a, b)


def hst_key(lf):
    return tuple(sorted((lf.a, lf.b), key=ORDER.index))


def qc_key(lf):
    u = lf.unit
    return (u.n, u.bg, u.discs())


def assign_labels():
    solids = Counter(solid_key(p) for p in PIECES if p.kind == "solid")
    hsts = Counter(hst_key(p) for p in PIECES if p.kind == "hst")
    qcs = Counter(qc_key(p) for p in PIECES if p.kind == "qc")
    labels = {}
    for fab in ORDER:
        keys = sorted((k for k in solids if k[0] == fab), key=lambda k: (k[1], k[2]))
        for i, k in enumerate(keys, 1):
            labels[("solid",) + k] = f"{fab}{i}"
    for i, k in enumerate(sorted(hsts, key=lambda k: (-hsts[k], [ORDER.index(f) for f in k])), 1):
        labels[("hst",) + k] = f"H{i}"
    qorder = sorted(qcs, key=lambda k: (k[0], -qcs[k], ORDER.index(k[1]), [ORDER.index(f) for _, f in k[2]]))
    for i, k in enumerate(qorder, 1):
        labels[("qc",) + k] = f"Q{i}"
    for p in PIECES:
        if p.kind == "solid":
            p.label = labels[("solid",) + solid_key(p)]
        elif p.kind == "hst":
            p.label = labels[("hst",) + hst_key(p)]
        else:
            p.label = labels[("qc",) + qc_key(p)]
    return labels, solids, hsts, qcs


LABELS, SOLIDS, HSTS, QCS = assign_labels()


def solid_table():
    """One row per piece code (pieces cut long have their own code)."""
    groups = {}
    for p in PIECES:
        if p.kind != "solid":
            continue
        a, b = sorted((p.rect.w, p.rect.h))
        g = groups.setdefault(p.label, dict(label=p.label, fabric=p.fabric, a=a, b=b, count=0,
                                            long=id(p) in globals().get("LONG", {}), piece=p))
        g["count"] += 1
    rows = list(groups.values())
    rows.sort(key=lambda r: (ORDER.index(r["fabric"]), r["a"], r["b"], r["long"]))
    return rows


def hst_types():
    out = []
    for (kind, *key), lab in LABELS.items():
        if kind == "hst":
            out.append(dict(label=lab, pair=tuple(key), count=HSTS[tuple(key)]))
    out.sort(key=lambda r: int(r["label"][1:]))
    return out


def qc_types():
    out = []
    for (kind, *key), lab in LABELS.items():
        if kind == "qc":
            n, bg, discs = key
            out.append(dict(label=lab, n=n, bg=bg, discs=discs, count=QCS[(n, bg, discs)]))
    out.sort(key=lambda r: int(r["label"][1:]))
    return out


def disc_radii():
    """Every appliqué radius used, in grid units."""
    return sorted({r for q in qc_types() for r, _ in q["discs"]})


QC_NAMES = {}


def qc_name(q):
    """Name of a quarter-circle unit type, after its place in the picture."""
    if q["label"] in QC_NAMES:
        return QC_NAMES[q["label"]]
    fabs = [f for _, f in q["discs"]]
    if q["n"] >= 4:
        name = "Rising sun"
    elif q["n"] == 3:
        name = "Bow and stern"
    elif q["n"] == 2:
        name = "Wave"
    elif q["bg"] == "N":
        name = "Herring head"
    elif fabs == ["N"]:
        name = "Gull wing"
    else:
        name = "Sail corner"
    QC_NAMES[q["label"]] = name
    return name


# --------------------------------------------------- trim-to-fit strips
def plain_section(sec):
    return all(isinstance(p, Leaf) and p.kind == "solid" for p in leaves(sec))


def seams_w(t):
    """Seams a horizontal line through the busiest part of t crosses (they shorten its width)."""
    if isinstance(t, Leaf):
        return 0
    if t.orient == V:
        return len(t.children) - 1 + sum(seams_w(c) for c in t.children)
    return max(seams_w(c) for c in t.children)


def seams_h(t):
    """Seams a vertical line through the busiest part of t crosses (they shorten its height)."""
    if isinstance(t, Leaf):
        return 0
    if t.orient == H:
        return len(t.children) - 1 + sum(seams_h(c) for c in t.children)
    return max(seams_h(c) for c in t.children)


def unit_names():
    """Names of the sub-assemblies as the section steps call them: "column k"
    (or "row k") for the parts of a section, "segment ka", "segment kb", ...
    for the segments inside part k, in the order they are made."""
    names = {}
    for sec in SECTIONS:
        if isinstance(sec, Leaf):
            continue
        part = "column" if sec.orient == V else "row"
        for k, child in enumerate(sec.children, 1):
            if isinstance(child, Leaf):
                continue
            names[id(child)] = f"{part} {k}"
            count = 0

            def visit(n, top):
                nonlocal count
                for c in n.children:
                    if isinstance(c, Node):
                        visit(c, False)
                if not top:
                    count += 1
                    names[id(n)] = f"segment {k}{chr(96 + count)}"

            visit(child, True)
    return names


UNIT_NAMES = unit_names()


def parents():
    out = {}

    def walk(n):
        for c in n.children:
            out[id(c)] = n
            if isinstance(c, Node):
                walk(c)

    walk(TREE)
    return out


PARENT = parents()


def long_strips():
    """Pieces cut a little long and trimmed to the measured neighbour.
    Returns {id(piece): neighbour}; the neighbour is None where the whole
    section is trimmed to the width of the section above.

    - the last strip of each plain section (the section is trimmed);
    - solid pieces that run the full height or width of their section and are
      at least 10 units long;
    - single pieces at least 4 units long stacked against a unit with three or
      more seams across, which comes out shorter if the seams are a little wide."""
    out = {}
    for sec in SECTIONS:
        if isinstance(sec, Leaf):
            out[id(sec)] = None
            continue
        if plain_section(sec):
            out[id(list(leaves(sec))[-1])] = None
            continue
        for k, c in enumerate(sec.children):
            if isinstance(c, Leaf) and c.kind == "solid":
                along = c.rect.h if sec.orient == V else c.rect.w
                full = sec.rect.h if sec.orient == V else sec.rect.w
                if along == full and along >= 10:
                    out[id(c)] = sec.children[k + 1] if k + 1 < len(sec.children) else sec.children[k - 1]
        nodes = [n for n in [sec] if isinstance(n, Node)]
        while nodes:
            n = nodes.pop()
            nodes += [c for c in n.children if isinstance(c, Node)]
            for k, c in enumerate(n.children):
                if not (isinstance(c, Leaf) and c.kind == "solid") or id(c) in out:
                    continue
                along = c.rect.w if n.orient == H else c.rect.h
                if along < 4:
                    continue
                count = seams_w if n.orient == H else seams_h
                near = [n.children[j] for j in (k - 1, k + 1) if 0 <= j < len(n.children)]
                best = max(near, key=count, default=None)
                if best is not None and count(best) >= 3:
                    out[id(c)] = best
    return out


LONG = long_strips()


def long_dim(p):
    """Which side of a piece cut long is trimmed later: "w" (width) or "h"."""
    if LONG[id(p)] is None:
        return "w"                       # plain bands: trimmed to the width of the section above
    return "h" if PARENT[id(p)].orient == V else "w"


for _p in PIECES:                        # a piece cut long gets its own code: S6+ next to S6
    if id(_p) in LONG and not _p.label.endswith("+"):
        _p.label += "+"


# ---------------------------------------------------- templates, finishing
def templates():
    """One template per disc radius, numbered from the smallest:
    [{"no", "r", "uses": [(unit label, fabric, count)], "total"}]."""
    out = []
    for k, r in enumerate(disc_radii(), 1):
        uses = [(q["label"], f, q["count"]) for q in qc_types() for rr, f in q["discs"] if rr == r]
        out.append(dict(no=k, r=r, uses=uses, total=sum(c for _, _, c in uses)))
    return out


TEMPLATES = templates()
TEMPLATE_NO = {t["r"]: t["no"] for t in TEMPLATES}
BINDING_FABRIC = "N"


def binding_need(sys_):
    """Binding length: the perimeter plus enough to join the ends and turn corners."""
    return 4 * NCOLS * sys_.unit + (25 if sys_.key == "cm" else 10)


def binding_strips(sys_):
    """Strips across the fabric for the binding. Every diagonal join uses up
    one strip width of length."""
    n = 1
    while n * sys_.wof - (n - 1) * sys_.binding_w < binding_need(sys_):
        n += 1
    return n


def backing(sys_):
    """Backing and batting square, and the fabric to buy for it: two widths of
    ordinary fabric joined side by side, or one length of wide backing."""
    beyond = 7.5 if sys_.key == "cm" else 3.0     # on every side of the top
    side = NCOLS * sys_.unit + 2 * beyond
    piece = side + (5.0 if sys_.key == "cm" else 2.0)
    return dict(side=side, piece=piece, two=sys_.length(2 * piece)[0], wide=sys_.length(piece)[0])


# -------------------------------------------------------------- cutting
@dataclass
class Cut:
    label: str
    a: float
    b: float
    rotated: bool = False
    trimmed: bool = False
    extra: float = 0.0
    kind: str = "piece"   # piece, hst, qcbg, disc
    r: float = 0.0        # disc: radius in grid units (which template)
    extra_on: str = "b"   # piece cut long: the side that carries the extra, "a" (across) or "b" (along)


def appliqué_items(sys_):
    """(fabric, side, label, kind) squares of fabric for every appliqué disc."""
    items = []
    for q in qc_types():
        for r, fab in q["discs"]:
            side = r * sys_.unit + sys_.sa + sys_.margin
            for _ in range(q["count"]):
                items.append((fab, round(side * 8) / 8 if sys_.key == "in" else math.ceil(side), f"{q['label']}", "disc", r))
    return items


def piece_cut(sys_, p):
    """Cut size of a solid piece, (width, height), with any extra length on
    the side that is trimmed to fit later."""
    extra = sys_.long_extra if id(p) in LONG else 0.0
    w = sys_.cut(p.rect.w) + (extra if extra and long_dim(p) == "w" else 0.0)
    h = sys_.cut(p.rect.h) + (extra if extra and long_dim(p) == "h" else 0.0)
    return w, h, extra


def cutting_plan(sys_: System):
    return {fab: plan_fabric(sys_, fab, sys_.wof) for fab in ORDER}


def plan_fabric(sys_: System, fab, length, squeeze=False):
    """Strips for one fabric, each `length` long (the usable width of fabric,
    or the long side of a fat quarter). squeeze: also cut triangle squares
    from wider strips, to save fabric on a fat quarter."""
    items = []
    for p in PIECES:
        if p.kind == "solid" and p.fabric == fab:
            w, h, extra = piece_cut(sys_, p)
            a, b = sorted((w, h))
            grown = w if extra and long_dim(p) == "w" else h
            on = "a" if extra and abs(grown - a) < 1e-9 and abs(a - b) > 1e-9 else "b"
            items.append((a, b, p.label, extra, "piece", 0.0, on))
    for t in hst_types():
        if fab in t["pair"]:
            for _ in range(math.ceil(t["count"] / 2)):
                items.append((sys_.hst_cut, sys_.hst_cut, t["label"], 0.0, "hst", 0.0, "b"))
    for q in qc_types():
        if q["bg"] == fab:
            side = sys_.cut(q["n"])
            for _ in range(q["count"]):
                items.append((side, side, q["label"], 0.0, "qcbg", 0.0, "b"))
    for f2, side, lab, kind, r in appliqué_items(sys_):
        if f2 == fab:
            items.append((side, side, lab, 0.0, "disc", r, "b"))
    items.sort(key=lambda t: (-t[0], -t[1], t[2]))
    strips = []
    for a, b, label, extra, kind, r, on in items:
        options = []
        for s in strips:
            if abs(s["width"] - a) < 1e-9 and s["free"] >= b - 1e-9:
                options.append((-s["width"], s["free"] - b, id(s), s, False))
            if abs(s["width"] - b) < 1e-9 and abs(a - b) > 1e-9 and s["free"] >= a - 1e-9:
                options.append((-s["width"], s["free"] - a, id(s), s, True))
        if options:
            _, _, _, s, rot = min(options)
            if rot:
                s["cuts"].append(Cut(label, b, a, True, extra=extra, kind=kind, r=r, extra_on="a" if on == "b" else "b")); s["free"] -= a
            else:
                s["cuts"].append(Cut(label, a, b, extra=extra, kind=kind, r=r, extra_on=on)); s["free"] -= b
            continue
        wider = [s for s in strips if s["width"] > a + 1e-9 and s["free"] >= b - 1e-9]
        if wider and (kind != "hst" or squeeze):
            s = min(wider, key=lambda s: (s["width"], s["free"]))
            s["cuts"].append(Cut(label, a, b, trimmed=True, extra=extra, kind=kind, r=r, extra_on=on)); s["free"] -= b
            continue
        if b > length:
            raise ValueError(f"{label} ({b}) is longer than the strip length {length}")
        strips.append(dict(width=a, free=length - b, cuts=[Cut(label, a, b, extra=extra, kind=kind, r=r, extra_on=on)]))
    if fab == BINDING_FABRIC:
        for _ in range(binding_strips(sys_)):
            strips.append(dict(width=sys_.binding_w, free=0, cuts=[Cut("binding", sys_.binding_w, sys_.wof, kind="binding")]))
    total = sum(s["width"] for s in strips)
    buy_txt, buy_val = sys_.length(total + sys_.extra)
    longest = max((sum(c.b for c in s["cuts"]) for s in strips if s["cuts"][0].kind != "binding"), default=0)
    widest = max((s["width"] for s in strips), default=0)
    return dict(strips=strips, total=total, buy=buy_txt, buy_val=buy_val, longest=longest, widest=widest,
                length=length, fq=False)


PLANS = {k: cutting_plan(s) for k, s in SYSTEMS.items()}


def fusible_area(sys_):
    """Fusible web needed: one square per appliqué disc."""
    return sum(side * side for _, side, _, _, _ in appliqué_items(sys_))


WEB_WIDTH = {"cm": 45.0, "in": 17.0}      # common paper-backed fusible web


def template_side(sys_, r):
    """Length of the straight edges of the template for radius r."""
    R, a = r * sys_.unit, sys_.sa
    return a + math.sqrt(R * R - a * a)


def fusible_layout(sys_):
    """Lay every tracing out on a roll of fusible web, as a quilter would:
    tracings 1 cm (3/8") apart, the largest first, in rows, smaller ones
    stacked beside the larger ones of a row. Returns the length of web used."""
    gap = 1.0 if sys_.key == "cm" else 0.375
    width = WEB_WIDTH[sys_.key]
    sizes = sorted((template_side(sys_, t["r"]) + gap for t in TEMPLATES for _ in range(t["total"])), reverse=True)
    rows = []
    for sz in sizes:
        for row in rows:
            col = next((c for c in row["cols"] if c[0] >= sz - 1e-9 and c[1] + sz <= row["h"] + 1e-9), None)
            if col:
                col[1] += sz
                break
            if row["w"] + sz <= width + 1e-9:
                row["cols"].append([sz, sz])
                row["w"] += sz
                break
        else:
            rows.append(dict(h=sz, w=sz, cols=[[sz, sz]]))
    return sum(row["h"] for row in rows)


def fusible_buy(sys_):
    """Fusible web to buy: the laid-out length plus 10 %, as text and value."""
    return sys_.length(fusible_layout(sys_) * 1.1)


# ---------------------------------------------------------------- checks
def sanity():
    d = DESIGN
    cover = [[0] * NCOLS for _ in range(NROWS)]
    for p in PIECES:
        for r, c in p.rect.cells():
            cover[r][c] += 1
    assert all(v == 1 for row in cover for v in row), "coverage"
    assert sum(t["count"] for t in hst_types()) == sum(1 for row in d.cells for c in row if c[0] == "H")
    assert sum(q["count"] for q in qc_types()) == len(d.units)
    # every unit and piece appears in the cutting plan exactly as often as needed
    for key, sys_ in SYSTEMS.items():
        for fab in ORDER:
            got = Counter((c.kind, c.label) for s in PLANS[key][fab]["strips"] for c in s["cuts"])
            for r in solid_table():
                if r["fabric"] == fab:
                    assert got[("piece", r["label"])] == r["count"], (key, fab, r)
            for t in hst_types():
                if fab in t["pair"]:
                    assert got[("hst", t["label"])] == math.ceil(t["count"] / 2), (key, fab, t)
            for q in qc_types():
                if q["bg"] == fab:
                    assert got[("qcbg", q["label"])] == q["count"], (key, fab, q)
                need = sum(q["count"] for r_, f in q["discs"] if f == fab)
                assert got[("disc", q["label"])] == need, (key, fab, q)
            for s in PLANS[key][fab]["strips"]:
                assert sum(c.b for c in s["cuts"]) <= max(PLANS[key][fab]["length"], sys_.wof) + 1e-9
            # no piece longer than the fabric is wide
            for p in PIECES:
                if p.kind == "solid":
                    assert sys_.cut(max(p.rect.w, p.rect.h)) + sys_.long_extra <= sys_.wof
    return True


if __name__ == "__main__":
    sanity()
    print("pieces:", len(PIECES), "solid:", sum(p.kind == "solid" for p in PIECES),
          "hst:", sum(p.kind == "hst" for p in PIECES), "qc:", sum(p.kind == "qc" for p in PIECES),
          "depth:", depth(TREE), "sections:", [(s.rect.r0, s.rect.r1 - 1) for s in SECTIONS])
    for t in hst_types():
        print(t)
    for q in qc_types():
        print(q)
    print("radii:", disc_radii())
    for key, sys_ in SYSTEMS.items():
        for fab in ORDER:
            p = PLANS[key][fab]
            print(key, fab, FABRICS[fab][0], "strips", Counter(s["width"] for s in p["strips"]), "total",
                  round(p["total"], 2), "buy", p["buy"], "longest", round(p["longest"], 2))
        print(key, "fusible", round(fusible_area(sys_)), "sq")


# ------------------------------------------------------- seam crossings
def colour_at(x, y):
    """Fabric of the quilt top at grid point (x, y) (x to the right, y down)."""
    c, r = int(math.floor(x)), int(math.floor(y))
    if not (0 <= r < NROWS and 0 <= c < NCOLS):
        return None
    cell = DESIGN.cells[r][c]
    if cell[0] == "S":
        return cell[1]
    if cell[0] == "H":
        _, corner, a, b = cell
        u, v = x - c, y - r
        inside = {"7": u + v < 1, "3": u + v > 1, "9": u > v, "1": u < v}[corner]
        return a if inside else b
    unit = DESIGN.units[cell[1]]
    R = unit.rect
    cx = R.c1 if unit.corner in "93" else R.c0
    cy = R.r1 if unit.corner in "13" else R.r0
    dist = math.hypot(x - cx, y - cy)
    fab = unit.bg
    for rad, f_ in unit.discs():
        if dist < rad:
            fab = f_
    return fab


def boundary_sides(gx, gy, n=48, eps=0.06):
    """Which half planes (above / below, left / right) have a colour boundary
    reaching grid point (gx, gy)."""
    out = set()
    pts = []
    for i in range(n):
        ang = 2 * math.pi * (i + 0.5) / n
        pts.append((ang, colour_at(gx + eps * math.cos(ang), gy + eps * math.sin(ang))))
    for i in range(n):
        (a1, c1), (a2, c2) = pts[i], pts[(i + 1) % n]
        if c1 is None or c2 is None or c1 == c2:
            continue
        mid = (a1 + a2) / 2 if i < n - 1 else (a1 + a2 + 2 * math.pi) / 2
        dy, dx = math.sin(mid), math.cos(mid)
        if dy < -1e-6:
            out.add("above")
        if dy > 1e-6:
            out.add("below")
        if dx < -1e-6:
            out.add("left")
        if dx > 1e-6:
            out.add("right")
    return out


def piece_ids():
    pid = [[None] * NCOLS for _ in range(NROWS)]
    for i, p in enumerate(PIECES):
        for r, c in p.rect.cells():
            pid[r][c] = i
    return pid


def match_points(gy, c0, c1):
    """Grid points on the horizontal seam at row line gy where an outline of the
    design continues across the seam and a seam meets it from both sides."""
    pid = piece_ids()
    out = []
    for gx in range(c0 + 1, c1):
        above = pid[gy - 1][gx - 1] != pid[gy - 1][gx]
        below = pid[gy][gx - 1] != pid[gy][gx]
        sides = boundary_sides(gx, gy)
        if above and below and {"above", "below"} <= sides:
            out.append(gx)
    return out


def section_pins(i):
    sec = SECTIONS[i - 1]
    r = sec.rect
    top = match_points(r.r0, r.c0, r.c1) if i > 1 else []
    bottom = match_points(r.r1, r.c0, r.c1) if i < len(SECTIONS) else []
    return top, bottom


def arc_points(sec):
    """Points inside a section where the end of an arc meets a seam or another
    arc and the outline carries on across the seam: [(gx, gy, label)]."""
    r0, r1 = sec.rect.r0, sec.rect.r1
    out = {}
    for lf in leaves(sec):
        if lf.kind != "qc":
            continue
        r = lf.rect
        cx = r.c1 if lf.corner in "93" else r.c0
        cy = r.r1 if lf.corner in "13" else r.r0
        for rad, _ in lf.unit.discs():
            if rad >= lf.unit.n:
                continue
            pts = [(cx - rad if lf.corner in "93" else cx + rad, cy, "h"),
                   (cx, cy + rad if lf.corner in "79" else cy - rad, "v")]
            for gx, gy, along in pts:
                if along == "h" and gy in (r0, r1):
                    continue          # on the seam to the next section: a pin point there
                if along == "v" and gx in (0, NCOLS):
                    continue          # on the quilt edge
                need = {"above", "below"} if along == "h" else {"left", "right"}
                if need <= boundary_sides(gx, gy):
                    out.setdefault((gx, gy), lf.label)
    return [(gx, gy, lab) for (gx, gy), lab in sorted(out.items())]


# ---------------------------------------------------------- fat quarters
# nominal size: strip length along the long side, height across, label
FQ = {"cm": (55.0, 50.0, "50 × 55 cm"), "in": (21.0, 18.0, "18 × 21″")}
FQ_LOSS = {"cm": 2.0, "in": 1.0}   # selvage and squaring up, in each direction


def fq_usable(sys_key, shrink=0.05):
    """Usable strip length and height of a fat quarter, after prewashing."""
    length, height, _ = FQ[sys_key]
    loss = FQ_LOSS[sys_key]
    return length * (1 - shrink) - loss, height * (1 - shrink) - loss


def fq_height(sys_key, fab, length):
    """Height of fat quarter the pieces of `fab` need, cut in strips of
    `length` along its long side; None if a piece is longer than that."""
    items = []
    for s in PLANS[sys_key][fab]["strips"]:
        if s["cuts"][0].kind == "binding":
            return None
        for c in s["cuts"]:
            items.append((c.a, c.b))
    items.sort(key=lambda t: (-t[0], -t[1]))
    strips = []
    for a, b in items:
        if b > length:
            return None
        for st in strips:
            if st[0] >= a - 1e-9 and st[1] >= b - 1e-9:
                st[1] -= b
                break
        else:
            strips.append([a, length - b])
    return sum(st[0] for st in strips)


def fits_fat_quarter(sys_key, fab, shrink=0.05):
    """Do all pieces of `fab` fit on one fat quarter, even after prewashing?"""
    length, height = fq_usable(sys_key, shrink)
    need = fq_height(sys_key, fab, length)
    return need is not None and need <= height


def replan_fat_quarters():
    """Fabrics that fit a fat quarter are cut from one: strips along its long side."""
    for key, sys_ in SYSTEMS.items():
        for fab in ORDER:
            if fits_fat_quarter(key, fab):
                length, height = fq_usable(key)
                plan = plan_fabric(sys_, fab, length, squeeze=True)
                if plan["total"] <= height + 1e-9:      # the real plan must fit too
                    plan["fq"] = True
                    PLANS[key][fab] = plan


def amount(sys_key, fab):
    """What to buy: a fat quarter if everything fits on one, else a length."""
    if PLANS[sys_key][fab]["fq"]:
        return "1 fat quarter", FQ[sys_key][2]
    return PLANS[sys_key][fab]["buy"], "× width of fabric"



replan_fat_quarters()
