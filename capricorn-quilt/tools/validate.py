"""Virtual sewing: check that the Steinbock pattern works with real fabric.

The pattern generator already proves that the design is consistent on the
grid. This script goes one step further and sews the quilt in software,
seam by seam, in the order the instructions give, with physical seam
allowances:

1. Exact sewing      every join must meet edge to edge, and every size the
                     page prints must come out of the simulation.
2. Real sewing       Monte Carlo runs with cutting, trimming and seam errors.
                     Where do edges stop matching, where do the ibex's
                     outlines jog across a seam, and how much must be eased?
3. Triangles         oversize margin of the HST squares under seam errors.
4. Fabric            strip lengths against real fabric width, and amounts
                     against shrinkage and a crooked shop cut.
5. Bulk              points where many seams meet.

    python3 tools/validate.py              # prints the report
    python3 tools/validate.py --md FILE    # also writes it as Markdown

Exits with status 1 if the exact-sewing check fails.
"""
from __future__ import annotations

import math
import random
import re
import statistics
import sys
from collections import defaultdict
from html import unescape

from plan import (BAND_TREE, BLOCK_INFO, BLOCK_TREES, BLOCKS, FRAME_LEAVES, NCOLS, NROWS, PLANS, ROOT, SYSTEMS,
                  TRIM_LATER, WINDOW, WINDOW_TREE, all_leaves, crossing_kind, diag_ends, piece_ids, sanity)
from quilt import H, V, Leaf, Node, Rect

# ------------------------------------------------------------ sewing tree
def expand(t, name):
    """Copy a tree, replacing BLOCK leaves by their own sub-assemblies."""
    if isinstance(t, Leaf):
        if t.kind == "BLOCK":
            return expand(BLOCK_TREES[t.block], BLOCK_INFO[t.block]["title"] + " block")
        return t
    n = Node(t.rect, t.orient, [], name=name)
    for i, c in enumerate(t.children, 1):
        n.children.append(expand(c, f"{name}, part {i}"))
    return n


def sewing_tree():
    """The whole quilt top in the order of the instructions."""
    band = expand(BAND_TREE, "sky band")
    band.children[2].name = "sky band, right unit"
    band.children[2].children[1].name = "sky band, middle row"
    window = Node(WINDOW_TREE.rect, WINDOW_TREE.orient, [], name="night window")
    for i, c in enumerate(WINDOW_TREE.children, 1):
        window.children.append(expand(c, f"section {i}"))
    lower = Node(Rect(WINDOW.r0, WINDOW.c0, NROWS, WINDOW.c1), H, [window, FRAME_LEAVES["bottom"]],
                 name="window and L8")
    body = Node(Rect(WINDOW.r0, 0, NROWS, NCOLS), V, [FRAME_LEAVES["left"], lower, FRAME_LEAVES["right"]],
                name="framed window")
    return Node(Rect(0, 0, NROWS, NCOLS), H, [band, body], name="quilt top")


TOP = sewing_tree()
WIN = TOP.children[1].children[1].children[0]


def label(t):
    if isinstance(t, Leaf):
        return "a triangle unit" if t.kind == "HST" else t.label
    return t.name


# ------------------------------------------------------------- simulation
class Sewer:
    """The errors of one person sewing the quilt (all in the system's unit)."""

    def __init__(self, sys_, seam_bias=0.0, seam_sd=0.0, cut_sd=0.0, trim_sd=0.0, measure_sd=0.0,
                 trim_to_fit=True, seed=1):
        self.sys = sys_
        self.bias, self.seam_sd, self.cut_sd, self.trim_sd = seam_bias, seam_sd, cut_sd, trim_sd
        self.measure_sd, self.trim_to_fit = measure_sd, trim_to_fit
        self.rnd = random.Random(seed)

    def noise(self, sd):
        return self.rnd.gauss(0, sd) if sd else 0.0

    def seam(self):
        return self.sys.sa + self.bias + self.noise(self.seam_sd)

    def piece(self, lf):
        u, sa = self.sys.unit, self.sys.sa
        if lf.kind == "HST":
            side = u + 2 * sa + self.noise(self.trim_sd)
            return side, side
        return lf.rect.w * u + 2 * sa + self.noise(self.cut_sd), lf.rect.h * u + 2 * sa + self.noise(self.cut_sd)


def is_trim_strip(t):
    return isinstance(t, Leaf) and t.kind in ("L", "D") and t.label in TRIM_LATER


def simulate(tree, sewer, joins):
    """Sew `tree`. Returns (width, height, features); features maps each edge
    to {grid line: physical position of the seam that reaches that edge},
    measured from the unit's raw top-left corner. Joins go into `joins`."""
    if isinstance(tree, Leaf):
        w, h = sewer.piece(tree)
        return w, h, {"top": {}, "bottom": {}, "left": {}, "right": {}}
    kids = [simulate(c, sewer, joins) for c in tree.children]
    if sewer.trim_to_fit:
        # long strips are cut long and trimmed to the measured length of their neighbour
        for k, c in enumerate(tree.children):
            if is_trim_strip(c):
                p = k + 1 if k + 1 < len(kids) and not is_trim_strip(tree.children[k + 1]) else k - 1
                w, h, fe = kids[k]
                if tree.orient == H:
                    kids[k] = (kids[p][0] + sewer.noise(sewer.measure_sd), h, fe)
                else:
                    kids[k] = (w, kids[p][1] + sewer.noise(sewer.measure_sd), fe)
    feats = {"top": {}, "bottom": {}, "left": {}, "right": {}}
    off = 0.0
    if tree.orient == V:  # side by side, vertical seams
        for k, (w, h, fk) in enumerate(kids):
            for edge in ("top", "bottom"):
                for g, pos in fk[edge].items():
                    feats[edge][g] = off + pos
            if k < len(kids) - 1:
                s = sewer.seam()
                g = tree.children[k].rect.c1
                feats["top"][g] = feats["bottom"][g] = off + w - s
                record(joins, tree, k, "v", h, kids[k + 1][1], fk["right"], kids[k + 1][2]["left"])
                off += w - 2 * s
        feats["left"], feats["right"] = dict(kids[0][2]["left"]), dict(kids[-1][2]["right"])
        return off + kids[-1][0], statistics.fmean(h for _, h, _ in kids), feats
    for k, (w, h, fk) in enumerate(kids):  # stacked, horizontal seams
        for edge in ("left", "right"):
            for g, pos in fk[edge].items():
                feats[edge][g] = off + pos
        if k < len(kids) - 1:
            s = sewer.seam()
            g = tree.children[k].rect.r1
            feats["left"][g] = feats["right"][g] = off + h - s
            record(joins, tree, k, "h", w, kids[k + 1][0], fk["bottom"], kids[k + 1][2]["top"])
            off += h - 2 * s
    feats["top"], feats["bottom"] = dict(kids[0][2]["top"]), dict(kids[-1][2]["bottom"])
    return statistics.fmean(w for w, _, _ in kids), off + kids[-1][1], feats


def record(joins, node, k, seam, len_a, len_b, fa, fb):
    """For the join between child k and k+1 of `node`, store
    mismatch  difference in length of the two edges sewn together
    jog       worst offset of an outline that continues across the seam,
              if the edges are only lined up at one end
    ease      worst amount to ease in between two neighbouring pins, when you
              pin every seam crossing and both ends"""
    a, b = node.children[k], node.children[k + 1]
    if seam == "h":
        g0, lo, hi = a.rect.r1, a.rect.c0, a.rect.c1
        kind = lambda g: crossing_kind(g0, g, "h")
    else:
        g0, lo, hi = a.rect.c1, a.rect.r0, a.rect.r1
        kind = lambda g: crossing_kind(g, g0, "v")
    shared = sorted(g for g in set(fa) & set(fb) if lo < g < hi)
    lines = [g for g in shared if kind(g) == "line"]
    jog = max((abs(fa[g] - fb[g]) for g in lines), default=0.0)
    pins = [(0.0, 0.0)] + [(fa[g], fb[g]) for g in shared] + [(len_a, len_b)]
    ease, span = 0.0, 0.0
    for (a1, b1), (a2, b2) in zip(pins, pins[1:]):
        e = abs((a2 - a1) - (b2 - b1))
        if e > ease:
            ease, span = e, max(a2 - a1, b2 - b1)
    j = joins.setdefault((id(node), k), dict(node=node, k=k, a=a, b=b, n_lines=len(lines),
                                             mismatch=[], jog=[], ease=[], span=[]))
    j["mismatch"].append(abs(len_a - len_b))
    j["jog"].append(jog)
    j["ease"].append(ease)
    j["span"].append(span)


def join_name(j):
    node, k = j["node"], j["k"]
    if node is WIN:
        return f"section {k + 1} to section {k + 2}"
    if node.name in ("quilt top", "framed window", "window and L8", "sky band, right unit"):
        return f"{label(j['a'])} to {label(j['b'])}"
    return f"inside {node.name}: {label(j['a'])} to {label(j['b'])}"


# ------------------------------------------------------ printed measures
def printed_measures():
    """Every 'measures A × B cm' statement on the metric page."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<span class="in">.*?</span>', "", html)
    text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))
    return [(float(m.group(1)), float(m.group(2)), text[max(0, m.start() - 60):m.end()].strip())
            for m in re.finditer(r"[Mm]easures? (\d+(?:\.\d+)?) × (\d+(?:\.\d+)?)\s*cm", text)]


def unit_sizes(sys_):
    """Exact sizes of the units the page quotes."""
    sewer = Sewer(sys_)
    out = {BLOCK_INFO[n]["title"]: simulate(t, sewer, {})[:2] for n, t in BLOCK_TREES.items()}
    band = TOP.children[0]
    out["sky band"] = simulate(band, sewer, {})[:2]
    out["band right unit"] = simulate(band.children[2], sewer, {})[:2]
    out["band middle row"] = simulate(band.children[2].children[1], sewer, {})[:2]
    out["night window"] = simulate(WIN, sewer, {})[:2]
    for i, sec in enumerate(WIN.children, 1):
        out[f"section {i}"] = simulate(sec, sewer, {})[:2]
    joins = {}
    out["quilt top"] = simulate(TOP, sewer, joins)[:2]
    return out, joins


# ------------------------------------------------------------ the checks
def fx(sys_, x):
    if sys_.key == "cm":
        return f"{x:.1f} cm" if abs(x * 10 - round(x * 10)) < 1e-9 else f"{x:.2f} cm"
    return f"{x:.2f}″"


def check_exact(out):
    ok = True
    for key, sys_ in SYSTEMS.items():
        sizes, joins = unit_sizes(sys_)
        bad = [j for j in joins.values() if max(j["mismatch"] + j["jog"] + j["ease"]) > 1e-9]
        top = NCOLS * sys_.unit + 2 * sys_.sa
        w, h = sizes["quilt top"]
        good = not bad and abs(w - top) < 1e-9 and abs(h - top) < 1e-9
        ok &= good
        out.append(f"- **{key}:** {len(joins)} joins sewn in the order of the instructions. "
                   + ("Every join meets edge to edge and every outline lines up across every seam. "
                      if not bad else f"**{len(bad)} joins do not meet.** ")
                   + f"Quilt top {fx(sys_, w)} × {fx(sys_, h)} (planned {fx(sys_, top)} square).")
    sizes, _ = unit_sizes(SYSTEMS["cm"])
    sim = {(round(w, 2), round(h, 2)) for w, h in sizes.values()}
    sim |= {(h, w) for w, h in sim}
    stated = printed_measures()
    wrong = [s for s in stated if (round(s[0], 2), round(s[1], 2)) not in sim]
    ok &= not wrong and len(stated) > 0
    out.append(f"- The page quotes {len(stated)} unit sizes to check while sewing. "
               + ("Every one of them comes out of the simulation." if not wrong else
                  "**These do not match:** " + "; ".join(w[2] for w in wrong)))
    return ok


SCENARIOS = [
    ("Careful sewing", "seam allowance right on average, ±0.5 mm from seam to seam",
     dict(seam_bias=0.0, seam_sd=0.05, cut_sd=0.05, trim_sd=0.03, measure_sd=0.05)),
    ("Seams 1 mm too wide", "every seam 0.85 cm instead of 0.75 cm, ±0.5 mm",
     dict(seam_bias=0.10, seam_sd=0.05, cut_sd=0.05, trim_sd=0.03, measure_sd=0.05)),
    ("Seams 1 mm too narrow", "every seam 0.65 cm instead of 0.75 cm, ±0.5 mm",
     dict(seam_bias=-0.10, seam_sd=0.05, cut_sd=0.05, trim_sd=0.03, measure_sd=0.05)),
]


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def run(params, runs, trim_to_fit=True):
    sys_ = SYSTEMS["cm"]
    joins, tops = {}, []
    for r in range(runs):
        sewer = Sewer(sys_, seed=1000 + r, trim_to_fit=trim_to_fit, **params)
        w, h, _ = simulate(TOP, sewer, joins)
        tops.append((w, h))
    return list(joins.values()), tops


def mm(x):
    return f"{x * 10:.0f} mm" if x >= 0.095 else f"{x * 10:.1f} mm"


def check_tolerance(out, runs=400):
    out.append("Every seam takes two seam allowances out of a row, so rows with many seams react most to an "
               "inaccurate seam. Seams across the width of each window section: "
               + ", ".join(f"{i}: {across(sec)}" for i, sec in enumerate(WIN.children, 1)) + ". "
               "Sections are joined along their full width, so their lengths must agree.")
    out.append("")
    out.append(f"Each figure below is the 95th percentile over {runs} simulated quilts. Cutting is ±0.5 mm per edge, "
               "triangle trimming ±0.3 mm, measuring ±0.5 mm. The long strips D10, L6, L7 and L8 are trimmed "
               "to the measured length of the part they join, as the pattern says.")
    summary = {}
    for title, desc, params in SCENARIOS:
        js, tops = run(params, runs)
        win = [j for j in js if j["node"] is WIN]
        tw = statistics.fmean(w for w, _ in tops)
        th = statistics.fmean(h for _, h in tops)
        out += ["", f"### {title}", "", f"{desc[0].upper() + desc[1:]}.", ""]
        out.append(f"- Quilt top: {tw:.1f} × {th:.1f} cm (planned 101.5 cm square).")
        worst = max(js, key=lambda j: p95(j["mismatch"]))
        wsec = max(win, key=lambda j: p95(j["mismatch"]))
        out.append(f"- Largest length difference between two edges sewn together: {mm(p95(worst['mismatch']))}, "
                   f"{join_name(worst)}. Between two window sections: {mm(p95(wsec['mismatch']))} "
                   f"({join_name(wsec)}).")
        jogs = sorted((j for j in js if j["n_lines"]), key=lambda j: -p95(j["jog"]))
        out.append("- Without pins, the ibex’s outline jogs by up to "
                   + ", ".join(f"{mm(p95(j['jog']))} ({join_name(j)})" for j in jogs[:3]) + ".")
        ew = max(win, key=lambda j: p95(j["ease"]))
        i = ew["ease"].index(max(ew["ease"]))
        out.append(f"- With pins at every seam crossing and both ends, the most you ease in between two window "
                   f"pins is {mm(p95(ew['ease']))} ({join_name(ew)}, over at most {ew['span'][i]:.0f} cm).")
        summary[title] = (p95(worst["mismatch"]), p95(wsec["mismatch"]), p95(ew["ease"]))
    # what the trim-to-fit step buys
    title, desc, params = SCENARIOS[1]
    js_cut, _ = run(params, runs, trim_to_fit=False)
    worst = max(js_cut, key=lambda j: p95(j["mismatch"]))
    out += ["", "### Why the long strips are trimmed to fit", "",
            f"If D10, L6, L7 and L8 were cut to their exact planned length, seams 1 mm too wide would leave "
            f"{label(worst['a'])} and {label(worst['b'])} {mm(p95(worst['mismatch']))} apart in length "
            f"({join_name(worst)}). Trimming them to the measured part removes that difference."]
    return summary


def across(t):
    """Seams crossed by a horizontal line through the busiest part of a unit."""
    if isinstance(t, Leaf):
        return 0
    if t.orient == V:
        return len(t.children) - 1 + sum(across(c) for c in t.children)
    return max(across(c) for c in t.children)


def check_triangles(out):
    for key, sys_ in SYSTEMS.items():
        need = sys_.unit + 2 * sys_.sa
        step = 0.1 if key == "cm" else 1 / 32
        for n in (0, 1, 2):
            s = sys_.sa + n * step
            got = sys_.hst_cut - s * math.sqrt(2)
            out.append(f"- {key}: {fx(sys_, sys_.hst_cut)} squares sewn {fx(sys_, s)} from the line give "
                       f"{fx(sys_, got)} units, to be trimmed to {fx(sys_, need)}: "
                       + ("enough" if got >= need else "**too small**") + f", {fx(sys_, max(0.0, got - need))} to spare.")


def check_fabric(out):
    for key, sys_ in SYSTEMS.items():
        selvage, squaring = (1.0, 1.0) if key == "cm" else (0.5, 0.5)
        crooked, first_edge = (3.0, 1.0) if key == "cm" else (1.0, 0.5)
        for fab in ("L", "D"):
            p = PLANS[key][fab]
            used = max(sum(c.b for c in s["cuts"]) for s in p["strips"] if s["cuts"][0].label != "binding")
            have = p["buy_val"] * 0.95 - crooked - first_edge
            out.append(f"- {key}, fabric {fab}: the fullest strip uses {fx(sys_, used)} of the width, so the fabric must "
                       f"be at least {fx(sys_, used + 2 * selvage + squaring)} wide including selvages. "
                       f"{p['buy']} leaves {fx(sys_, have)} after 5 % shrinkage, a {fx(sys_, crooked)} crooked shop cut "
                       f"and squaring up; the strips need {fx(sys_, p['total'])}: "
                       + ("enough" if have >= p["total"] else "**not enough**")
                       + f", {fx(sys_, have - p['total'])} spare.")


def check_bulk(out):
    pid = piece_ids()
    hst = {(lf.rect.r0, lf.rect.c0): lf.corner for lf in all_leaves() if lf.kind == "HST"}
    hot = defaultdict(lambda: defaultdict(int))
    for gy in range(1, NROWS):
        for gx in range(1, NCOLS):
            n = ((pid[gy - 1][gx - 1] != pid[gy - 1][gx]) + (pid[gy][gx - 1] != pid[gy][gx])
                 + (pid[gy - 1][gx - 1] != pid[gy][gx - 1]) + (pid[gy - 1][gx] != pid[gy][gx]))
            for (r, c), corner in (((gy - 1, gx - 1), "br"), ((gy - 1, gx), "bl"), ((gy, gx - 1), "tr"), ((gy, gx), "tl")):
                n += (r, c) in hst and corner in diag_ends(hst[(r, c)])
            if n >= 6:
                hot[n][place(gy, gx)] += 1
    for n in sorted(hot, reverse=True):
        total = sum(hot[n].values())
        out.append(f"- {n} seams meet at {total} point{'s' if total > 1 else ''}: "
                   + ", ".join(f"{p} ({k})" if k > 1 else p for p, k in hot[n].items()) + ".")


def place(gy, gx):
    for name, r in BLOCKS.items():
        if r.r0 <= gy <= r.r1 and r.c0 <= gx <= r.c1:
            return BLOCK_INFO[name]["title"]
    if gy <= WINDOW.r0:
        return "sky band"
    for i, sec in enumerate(WIN.children, 1):
        if sec.rect.r0 < gy < sec.rect.r1:
            return f"inside section {i}"
        if gy == sec.rect.r1:
            return f"seam between sections {i} and {i + 1}"
    return "night window"


def main():
    sanity()
    out = ["# Steinbock: can it be sewn?", "",
           "Generated by `tools/validate.py`. The quilt is sewn in software, seam by seam, in the order the "
           "instructions give, with physical seam allowances. Real sewing errors are then added at random.", "",
           "## 1. Exact sewing", ""]
    ok = check_exact(out)
    out += ["", "## 2. Real sewing (metric version)", ""]
    check_tolerance(out)
    out += ["", "## 3. Triangle squares", ""]
    check_triangles(out)
    out += ["", "## 4. Fabric", ""]
    check_fabric(out)
    out += ["", "## 5. Bulky points", "", "Points where 6 or more seams meet need seams pressed open, "
            "or the centre “spun” on the pinwheels:", ""]
    check_bulk(out)
    text = "\n".join(out) + "\n"
    print(text)
    if "--md" in sys.argv:
        with open(sys.argv[sys.argv.index("--md") + 1], "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
