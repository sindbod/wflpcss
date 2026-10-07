"""Turn the design grid into a sewing plan: units, labelled pieces, sections,
cutting lists and fabric requirements, for metric and imperial rulers."""
from __future__ import annotations

import math
from collections import Counter, OrderedDict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from quilt import H, V, Leaf, Node, Rect, check_tree, decompose, leaves, load_grid, nodes

ROOT = Path(__file__).resolve().parent.parent
GRID = load_grid(ROOT / "design" / "steinbock.txt")
NROWS, NCOLS = len(GRID), len(GRID[0])

# ---------------------------------------------------------------- structure
BLOCKS = OrderedDict(
    deneb=Rect(0, 2, 4, 6),       # sawtooth star
    nashira=Rect(1, 7, 3, 9),     # pinwheels
    dabih=Rect(1, 13, 3, 15),
    algedi=Rect(1, 16, 3, 18),
    edelweiss=Rect(15, 15, 18, 18),  # friendship star
)
BLOCK_INFO = {
    "deneb": dict(title="Deneb Algedi", kind="Sawtooth star",
                  note="δ Capricorni, the brightest star of the constellation. The name means “tail of the goat”, so it sits above the ibex’s tail."),
    "nashira": dict(title="Nashira", kind="Pinwheel",
                    note="γ Capricorni, “the fortunate one”, the tail’s second star."),
    "dabih": dict(title="Dabih", kind="Pinwheel",
                  note="β Capricorni, one of the two stars that mark the goat’s horns."),
    "algedi": dict(title="Algedi", kind="Pinwheel",
                   note="α Capricorni, “the kid”, the other horn star."),
    "edelweiss": dict(title="Edelweiss", kind="Friendship star",
                      note="An alpine flower in the ibex’s meadow, reversed out in light on dark."),
}
BAND = Rect(0, 0, 4, 20)
WINDOW = Rect(4, 1, 19, 19)
FRAME = OrderedDict(
    bottom=Rect(19, 1, 20, 19),
    left=Rect(4, 0, 20, 1),
    right=Rect(4, 19, 20, 20),
)

# ------------------------------------------------------------------ systems
@dataclass
class System:
    key: str
    unit: float        # finished grid unit
    sa: float          # seam allowance
    hst_cut: float     # square size for two-at-a-time HSTs (oversized)
    hst8_cut: float    # square size for eight-at-a-time HSTs (oversized)
    wof: float         # usable width of fabric
    binding_w: float
    round_to: float    # yardage rounding step
    extra: float       # straightening / shrinkage allowance per fabric

    def cut(self, n):
        return n * self.unit + 2 * self.sa

    def fmt(self, x, unit=True):
        if self.key == "cm":
            s = f"{x:.1f}".rstrip("0").rstrip(".")
            return f"{s} cm" if unit else s
        return fmt_inch(x) + ("″" if unit else "")

    def dims(self, a, b, unit=True):
        if self.key == "cm":
            return f"{self.fmt(a, False)} × {self.fmt(b, False)} cm" if unit else f"{self.fmt(a, False)} × {self.fmt(b, False)}"
        return f"{self.fmt(a)} × {self.fmt(b)}" if unit else f"{self.fmt(a, False)} × {self.fmt(b, False)}"

    def length(self, x):
        """Fabric length to buy, rounded up."""
        steps = math.ceil(x / self.round_to - 1e-9)
        val = steps * self.round_to
        if self.key == "cm":
            return f"{val / 100:.2f}".rstrip("0").rstrip(".") + " m", val
        yd = Fraction(val / 36).limit_denominator(8)
        return fmt_yards(yd), val


def fmt_inch(x):
    whole = int(math.floor(x + 1e-9))
    frac = Fraction(x - whole).limit_denominator(8)
    glyph = {Fraction(1, 8): "⅛", Fraction(1, 4): "¼", Fraction(3, 8): "⅜", Fraction(1, 2): "½",
             Fraction(5, 8): "⅝", Fraction(3, 4): "¾", Fraction(7, 8): "⅞"}
    if frac == 0:
        return str(whole)
    return (str(whole) if whole else "") + glyph[frac]


def fmt_yards(yd: Fraction):
    whole = yd.numerator // yd.denominator
    frac = yd - whole
    glyph = {Fraction(1, 8): "⅛", Fraction(1, 4): "¼", Fraction(3, 8): "⅜", Fraction(1, 2): "½",
             Fraction(5, 8): "⅝", Fraction(3, 4): "¾", Fraction(7, 8): "⅞"}
    if frac == 0:
        return f"{whole} yd"
    return f"{whole if whole else ''}{glyph[frac]} yd"


SYSTEMS = {
    "cm": System("cm", unit=5.0, sa=0.75, hst_cut=8.0, hst8_cut=16.0, wof=105.0, binding_w=6.0,
                 round_to=10.0, extra=15.0),
    "in": System("in", unit=2.0, sa=0.25, hst_cut=3.0, hst8_cut=6.0, wof=40.0, binding_w=2.5,
                 round_to=4.5, extra=6.0),
}

# ------------------------------------------------------------------- build
@dataclass
class Section:
    key: str
    title: str
    tree: object
    rect: Rect


def build():
    band, band_cost = decompose(GRID, BAND, blocks=BLOCKS, max_depth=3)
    window, win_cost = decompose(GRID, WINDOW, blocks=BLOCKS, max_depth=3, first=H)
    check_tree(band, GRID, BLOCKS)
    check_tree(window, GRID, BLOCKS)
    block_trees = OrderedDict()
    for name, rect in BLOCKS.items():
        t, _ = decompose(GRID, rect)
        check_tree(t, GRID)
        block_trees[name] = t
    frame = OrderedDict((k, Leaf(r, "L")) for k, r in FRAME.items())
    return band, window, block_trees, frame


BAND_TREE, WINDOW_TREE, BLOCK_TREES, FRAME_LEAVES = build()


def all_leaves():
    """Every cut piece / HST unit in the quilt, blocks expanded."""
    out = []
    for t in (BAND_TREE, WINDOW_TREE):
        for lf in leaves(t):
            if lf.kind == "BLOCK":
                out.extend(leaves(BLOCK_TREES[lf.block]))
            else:
                out.append(lf)
    out.extend(FRAME_LEAVES.values())
    return out


# --------------------------------------------------------------- labelling
def piece_key(lf):
    if lf.kind == "HST":
        return ("HST",)
    a, b = sorted((lf.rect.w, lf.rect.h))
    return (lf.kind, a, b)


def assign_labels():
    keys = Counter(piece_key(lf) for lf in all_leaves())
    labels = {}
    for fab in ("L", "D"):
        ks = sorted(k for k in keys if k[0] == fab)
        ks.sort(key=lambda k: (k[1], k[2]))
        for i, k in enumerate(ks, 1):
            labels[k] = f"{fab}{i}"
    labels[("HST",)] = "HST"
    for lf in all_leaves():
        lf.label = labels[piece_key(lf)]
    return labels, keys


LABELS, COUNTS = assign_labels()


def piece_table():
    """Rows for the piece list: label, fabric, grid size, count."""
    rows = []
    for key, label in LABELS.items():
        if key[0] == "HST":
            continue
        rows.append(dict(label=label, fabric=key[0], a=key[1], b=key[2], count=COUNTS[key]))
    rows.sort(key=lambda r: (r["fabric"] != "L", r["a"], r["b"]))
    return rows


HST_COUNT = COUNTS[("HST",)]

# ---------------------------------------------------------------- cutting
@dataclass
class Cut:
    label: str
    a: float      # across the strip (= strip width, or less when trimmed)
    b: float      # along the strip
    rotated: bool = False
    trimmed: bool = False  # cut from a wider strip, extra width trimmed off


def cutting_plan(sys_: System):
    """Strip-based cutting plan per fabric: list of strips with the pieces cut from them."""
    plan = {}
    hst_pairs = math.ceil(HST_COUNT / 2)
    for fab in ("L", "D"):
        items = []
        for row in piece_table():
            if row["fabric"] != fab:
                continue
            for _ in range(row["count"]):
                items.append((sys_.cut(row["a"]), sys_.cut(row["b"]), row["label"]))
        for _ in range(hst_pairs):
            items.append((sys_.hst_cut, sys_.hst_cut, "□"))
        items.sort(key=lambda t: (-t[0], -t[1], t[2]))
        strips = []
        for a, b, label in items:
            # Candidate strips: same width (piece runs along the strip) or as wide as the
            # piece is long (piece turned across the strip).  Fill the leftovers of the
            # widest strips first, best fit within the same width.
            options = []
            for s in strips:
                if abs(s["width"] - a) < 1e-9 and s["free"] >= b - 1e-9:
                    options.append((-s["width"], s["free"] - b, id(s), s, False))
                if abs(s["width"] - b) < 1e-9 and abs(a - b) > 1e-9 and s["free"] >= a - 1e-9:
                    options.append((-s["width"], s["free"] - a, id(s), s, True))
            if options:
                _, _, _, s, rot = min(options)
                if rot:
                    s["cuts"].append(Cut(label, b, a, True)); s["free"] -= a
                else:
                    s["cuts"].append(Cut(label, a, b)); s["free"] -= b
                continue
            # Last resort before a new strip: cut the piece from the leftover of a
            # wider strip and trim away the extra width.
            wider = [s for s in strips if s["width"] > a + 1e-9 and s["free"] >= b - 1e-9 and s["cuts"][0].label != "□"]
            if wider and label != "□":
                s = min(wider, key=lambda s: (s["width"], s["free"]))
                s["cuts"].append(Cut(label, a, b, trimmed=True)); s["free"] -= b
                continue
            if b > sys_.wof:
                raise ValueError(f"{label} is longer than the usable fabric width")
            strips.append(dict(width=a, free=sys_.wof - b, cuts=[Cut(label, a, b)]))
        if fab == "D":
            n_bind = math.ceil((4 * NCOLS * sys_.unit + (25 if sys_.key == "cm" else 10)) / sys_.wof)
            for _ in range(n_bind):
                strips.append(dict(width=sys_.binding_w, free=0, cuts=[Cut("binding", sys_.binding_w, sys_.wof)]))
        total = sum(s["width"] for s in strips)
        buy_txt, buy_val = sys_.length(total + sys_.extra)
        plan[fab] = dict(strips=strips, total=total, buy=buy_txt, buy_val=buy_val)
    return plan


PLANS = {k: cutting_plan(s) for k, s in SYSTEMS.items()}


def sanity():
    """Independent checks on the plan."""
    # 1. every cell of the quilt is covered exactly once, with the right fabric
    cover = [[0] * NCOLS for _ in range(NROWS)]
    for lf in all_leaves():
        for r, c in lf.rect.cells():
            cover[r][c] += 1
            ch = GRID[r][c]
            if lf.kind == "HST":
                assert ch == lf.corner
            else:
                assert {"#": "L", ".": "D"}[ch] == lf.kind, (lf, ch)
    assert all(v == 1 for row in cover for v in row), "coverage"
    # 2. HST count matches the design
    assert HST_COUNT == sum(ch in "7913" for row in GRID for ch in row)
    # 3. area per fabric adds up (each HST is half L, half D)
    area = Counter()
    for lf in all_leaves():
        if lf.kind == "HST":
            area["L"] += 0.5; area["D"] += 0.5
        else:
            area[lf.kind] += lf.rect.w * lf.rect.h
    exp_L = sum(row.count("#") for row in GRID) + HST_COUNT / 2
    exp_D = sum(row.count(".") for row in GRID) + HST_COUNT / 2
    assert area["L"] == exp_L and area["D"] == exp_D, (area, exp_L, exp_D)
    # 4. every planned cut matches the piece list
    for key, sys_ in SYSTEMS.items():
        for fab in ("L", "D"):
            got = Counter(c.label for s in PLANS[key][fab]["strips"] for c in s["cuts"])
            for row in piece_table():
                if row["fabric"] == fab:
                    assert got[row["label"]] == row["count"], (key, fab, row, got[row["label"]])
            assert got["□"] == math.ceil(HST_COUNT / 2)
            for s in PLANS[key][fab]["strips"]:
                used = sum(c.b for c in s["cuts"])
                assert used <= sys_.wof + 1e-9, (key, fab, s)
                for c in s["cuts"]:
                    assert abs(c.a - s["width"]) < 1e-9 or (c.trimmed and c.a < s["width"])
    return True


if __name__ == "__main__":
    sanity()
    print("pieces:", len(all_leaves()), "HST:", HST_COUNT)
    for r in piece_table():
        print(r["label"], r["fabric"], f'{r["a"]}x{r["b"]}', "x", r["count"],
              "|", SYSTEMS["cm"].dims(SYSTEMS["cm"].cut(r["a"]), SYSTEMS["cm"].cut(r["b"])),
              "|", SYSTEMS["in"].dims(SYSTEMS["in"].cut(r["a"]), SYSTEMS["in"].cut(r["b"])))
    for key in SYSTEMS:
        for fab in ("L", "D"):
            p = PLANS[key][fab]
            widths = Counter(s["width"] for s in p["strips"])
            print(key, fab, "strips:", dict(widths), "total", p["total"], "buy", p["buy"])
