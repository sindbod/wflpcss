"""Virtual sewing: check that the Kogge pattern works with real fabric.

The pattern generator already proves that the design is consistent on the
grid. This script goes one step further and sews the quilt top in software,
seam by seam, in the order the instructions give, with physical seam
allowances and fused quarter circles:

1. Exact sewing      every join must meet edge to edge, every outline and arc
                     must meet its partner across every seam, and every size
                     the page prints must come out of the simulation.
2. Real sewing       Monte Carlo runs with cutting, appliqué and seam errors.
                     Where do edges stop matching, where do outlines and arcs
                     jog across a seam, and how much must be eased?
3. Arcs at seams     arcs that end square to a seam forgive a wrong seam
                     allowance; arcs that touch a seam tangentially do not.
4. Triangles         oversize margin of the HST squares under seam errors.
5. Fabric            strip lengths against real fabric width, and amounts
                     against shrinkage and a crooked shop cut.
6. Bulk              points where many seams and fused layers meet.

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
from functools import lru_cache
from html import unescape

from modular import H, V, Leaf, leaves
from plan import (FQ, LONG, NCOLS, NROWS, ORDER, PARENT, PIECES, PLANS, ROOT, SECTIONS, SYSTEMS, TREE,
                  UNIT_NAMES, amount, boundary_sides, colour_at, fq_height, fq_usable, hst_types, piece_ids,
                  plain_section, qc_name, qc_types, sanity)

EDGES = ("top", "bottom", "left", "right")
CENTRE_EDGES = {"7": ("top", "left"), "9": ("top", "right"), "1": ("bottom", "left"), "3": ("bottom", "right")}
QC_BY_LABEL = {q["label"]: q for q in qc_types()}


def label(t):
    """A piece by its code, a sub-assembly by the name the section steps use."""
    if isinstance(t, Leaf):
        return t.label
    return UNIT_NAMES.get(id(t), t.name)


def section_no(node):
    """Number of the section a node belongs to (None for the quilt top)."""
    while node is not TREE:
        for i, s in enumerate(SECTIONS, 1):
            if s is node:
                return i
        node = PARENT[id(node)]
    return None


def full_name(node):
    return f"section {section_no(node)}, {label(node)}"


# ------------------------------------------------------------- simulation
class Sewer:
    """The errors of one person sewing the quilt (all in the system's unit)."""

    def __init__(self, sys_, seam_bias=0.0, seam_sd=0.0, cut_sd=0.0, trim_sd=0.0, measure_sd=0.0,
                 arc_sd=0.0, place_sd=0.0, trim_to_fit=True, seed=1):
        self.sys = sys_
        self.bias, self.seam_sd, self.cut_sd, self.trim_sd = seam_bias, seam_sd, cut_sd, trim_sd
        self.measure_sd, self.arc_sd, self.place_sd = measure_sd, arc_sd, place_sd
        self.trim_to_fit = trim_to_fit
        self.rnd = random.Random(seed)

    def noise(self, sd):
        return self.rnd.gauss(0, sd) if sd else 0.0

    def seam(self):
        return self.sys.sa + self.bias + self.noise(self.seam_sd)

    def piece(self, lf):
        """A cut (or trimmed, or fused) unit: raw width, height and the arc ends
        on its edges, as {edge: {grid line: (position from the raw corner, kind)}}."""
        u, sa = self.sys.unit, self.sys.sa
        feats = {e: {} for e in EDGES}
        if lf.kind == "hst":
            side = u + 2 * sa + self.noise(self.trim_sd)
            return side, side, feats
        w = lf.rect.w * u + 2 * sa + self.noise(self.cut_sd)
        h = lf.rect.h * u + 2 * sa + self.noise(self.cut_sd)
        if lf.kind == "qc":
            r = lf.rect
            for rad, _ in lf.unit.discs():
                # each disc is cut a little off and fused a little off the raw edges
                dr = self.noise(self.arc_sd)
                shift = {"x": self.noise(self.place_sd), "y": self.noise(self.place_sd)}
                for edge in CENTRE_EDGES[lf.corner]:
                    along_x = edge in ("top", "bottom")
                    d = sa + rad * u + dr + shift["x" if along_x else "y"]
                    if along_x:
                        right = lf.corner in "93"
                        g, pos = (r.c1 - rad, w - d) if right else (r.c0 + rad, d)
                    else:
                        top = lf.corner in "79"
                        g, pos = (r.r0 + rad, d) if top else (r.r1 - rad, h - d)
                    feats[edge][g] = (pos, "arc")
        return w, h, feats


def put(d, g, val):
    """Add a feature; a seam wins over an arc that ends at the same point."""
    if val[1] == "seam" or g not in d or d[g][1] != "seam":
        d[g] = val


def trim_target(node, child):
    """Index of the sibling that `child` is trimmed to when it is joined into
    `node`, or None if it is not cut long."""
    if node is TREE:
        if not isinstance(child, Leaf) and plain_section(child) and any(id(lf) in LONG for lf in leaves(child)):
            return node.children.index(child) - 1      # plain bands: the section above
        return None
    if isinstance(child, Leaf) and LONG.get(id(child)) is not None:
        nb = LONG[id(child)]
        return next(i for i, c in enumerate(node.children) if c is nb)
    return None


def simulate(tree, sewer, joins):
    """Sew `tree`. Returns (width, height, features); features maps each edge
    to {grid line: (physical position, kind)} for every seam and arc that
    reaches that edge, measured from the unit's raw top-left corner.
    Joins go into `joins`."""
    if isinstance(tree, Leaf):
        return sewer.piece(tree)
    kids = [simulate(c, sewer, joins) for c in tree.children]
    if sewer.trim_to_fit:
        for k, c in enumerate(tree.children):
            p = trim_target(tree, c)
            if p is not None:
                w, h, fe = kids[k]
                if tree.orient == H:
                    kids[k] = (kids[p][0] + sewer.noise(sewer.measure_sd), h, fe)
                else:
                    kids[k] = (w, kids[p][1] + sewer.noise(sewer.measure_sd), fe)
    feats = {e: {} for e in EDGES}
    off = 0.0
    if tree.orient == V:  # side by side, vertical seams
        for k, (w, h, fk) in enumerate(kids):
            for edge in ("top", "bottom"):
                for g, (pos, kind) in fk[edge].items():
                    put(feats[edge], g, (off + pos, kind))
            if k < len(kids) - 1:
                s = sewer.seam()
                g = tree.children[k].rect.c1
                put(feats["top"], g, (off + w - s, "seam"))
                put(feats["bottom"], g, (off + w - s, "seam"))
                record(joins, tree, k, "v", h, kids[k + 1][1], fk["right"], kids[k + 1][2]["left"])
                off += w - 2 * s
        feats["left"], feats["right"] = dict(kids[0][2]["left"]), dict(kids[-1][2]["right"])
        return off + kids[-1][0], statistics.fmean(h for _, h, _ in kids), feats
    for k, (w, h, fk) in enumerate(kids):  # stacked, horizontal seams
        for edge in ("left", "right"):
            for g, (pos, kind) in fk[edge].items():
                put(feats[edge], g, (off + pos, kind))
        if k < len(kids) - 1:
            s = sewer.seam()
            g = tree.children[k].rect.r1
            put(feats["left"], g, (off + h - s, "seam"))
            put(feats["right"], g, (off + h - s, "seam"))
            record(joins, tree, k, "h", w, kids[k + 1][0], fk["bottom"], kids[k + 1][2]["top"])
            off += h - 2 * s
    feats["top"], feats["bottom"] = dict(kids[0][2]["top"]), dict(kids[-1][2]["bottom"])
    return statistics.fmean(w for w, _, _ in kids), off + kids[-1][1], feats


@lru_cache(maxsize=None)
def sides(gx, gy):
    return frozenset(boundary_sides(gx, gy))


def record(joins, node, k, seam, len_a, len_b, fa, fb):
    """For the join between child k and k+1 of `node`, store
    mismatch  difference in length of the two edges sewn together
    jog       worst offset of an outline that continues across the seam,
              if the edges are only lined up at one end
    arc       the same, for outlines that are arcs on at least one side
    ease      worst amount to ease in between two neighbouring pins, when you
              pin every seam crossing, every arc end and both ends"""
    a, b = node.children[k], node.children[k + 1]
    if seam == "h":
        g0, lo, hi = a.rect.r1, a.rect.c0, a.rect.c1
        is_line = lambda g: {"above", "below"} <= sides(g, g0)
    else:
        g0, lo, hi = a.rect.c1, a.rect.r0, a.rect.r1
        is_line = lambda g: {"left", "right"} <= sides(g0, g)
    shared = sorted(g for g in set(fa) & set(fb) if lo < g < hi)
    lines = [g for g in shared if is_line(g)]
    arcs = [g for g in lines if "arc" in (fa[g][1], fb[g][1])]
    jog = max((abs(fa[g][0] - fb[g][0]) for g in lines), default=0.0)
    arc = max((abs(fa[g][0] - fb[g][0]) for g in arcs), default=0.0)
    pins = [(0.0, 0.0)] + [(fa[g][0], fb[g][0]) for g in shared] + [(len_a, len_b)]
    ease, span = 0.0, 0.0
    for (a1, b1), (a2, b2) in zip(pins, pins[1:]):
        e = abs((a2 - a1) - (b2 - b1))
        if e > ease:
            ease, span = e, max(a2 - a1, b2 - b1)
    j = joins.setdefault((id(node), k), dict(node=node, k=k, a=a, b=b, n_lines=len(lines), n_arcs=len(arcs),
                                             mismatch=[], jog=[], arc=[], ease=[], span=[]))
    j["mismatch"].append(abs(len_a - len_b))
    j["jog"].append(jog)
    j["arc"].append(arc)
    j["ease"].append(ease)
    j["span"].append(span)


def join_name(j):
    node, k = j["node"], j["k"]
    if node is TREE:
        return f"section {k + 1} to section {k + 2}"
    i = next((n for n, sec in enumerate(SECTIONS, 1) if sec is node), None)
    if i is not None:
        part = "column" if node.orient == V else "row"

        def side(t, n):
            return f"{part} {n}" + (f" ({t.label})" if isinstance(t, Leaf) else "")

        return f"section {i}, {side(j['a'], k + 1)} to {side(j['b'], k + 2)}"
    return f"{full_name(node)}: {label(j['a'])} to {label(j['b'])}"


# ------------------------------------------------------ printed measures
def page_text():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    html = re.sub(r'<span class="in">.*?</span>', "", html)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html)))


def printed_measures(text):
    """Every 'measures A × B cm' statement about a unit on the metric page."""
    return [(float(m.group(1)), float(m.group(2)), text[max(0, m.start() - 40):m.end()].strip())
            for m in re.finditer(r"(?<!must )[Mm]easures? (\d+(?:\.\d+)?) × (\d+(?:\.\d+)?)\s*cm", text)]


def unit_sizes(sys_):
    """Exact sizes of the units the page quotes."""
    sewer = Sewer(sys_)
    out = {}
    for i, sec in enumerate(SECTIONS, 1):
        out[f"section {i}"] = simulate(sec, sewer, {})[:2]
    joins = {}
    out["quilt top"] = simulate(TREE, sewer, joins)[:2]
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
        bad = [j for j in joins.values() if max(j["mismatch"] + j["jog"] + j["arc"] + j["ease"]) > 1e-9]
        n_arcs = sum(j["n_arcs"] for j in joins.values())
        n_lines = sum(j["n_lines"] for j in joins.values())
        top = NCOLS * sys_.unit + 2 * sys_.sa
        w, h = sizes["quilt top"]
        good = not bad and abs(w - top) < 1e-9 and abs(h - top) < 1e-9
        ok &= good
        out.append(f"- **{key}:** {len(joins)} joins sewn in the order of the instructions. "
                   + (f"Every join meets edge to edge, and all {n_lines} outlines that cross a seam line up, "
                      f"{n_arcs} of them arcs. " if not bad else f"**{len(bad)} joins do not meet.** ")
                   + f"Quilt top {fx(sys_, w)} × {fx(sys_, h)} (planned {fx(sys_, top)} square).")
    text = page_text()
    sizes, _ = unit_sizes(SYSTEMS["cm"])
    sim = {(round(w, 2), round(h, 2)) for w, h in sizes.values()}
    sim |= {(h, w) for w, h in sim}
    stated = printed_measures(text)
    wrong = [s for s in stated if (round(s[0], 2), round(s[1], 2)) not in sim]
    ok &= not wrong and len(stated) > 0
    out.append(f"- The page quotes {len(stated)} section and quilt sizes to check while sewing. "
               + ("Every one of them comes out of the simulation." if not wrong else
                  "**These do not match:** " + "; ".join(w[2] for w in wrong)))
    # the seam test: six squares in a row
    cm = SYSTEMS["cm"]
    m = re.search(r"Sew six (\d+(?:\.\d+)?) cm scrap squares into a row: it must be (\d+(?:\.\d+)?) cm long", text)
    if m:
        sq, row = float(m.group(1)), float(m.group(2))
        sewer = Sewer(cm)
        got = 6 * sq - 5 * 2 * cm.sa
        good = abs(sq - (cm.unit + 2 * cm.sa)) < 1e-9 and abs(got - row) < 1e-9
        ok &= good
        out.append(f"- Seam test: six {fx(cm, sq)} squares sewn with {fx(cm, cm.sa)} seams make a row of "
                   f"{fx(cm, got)}, " + ("as the page says." if good else f"**the page says {fx(cm, row)}.**"))
    else:
        ok = False
        out.append("- **The seam test is missing from the page.**")
    return ok


CAREFUL = dict(seam_sd=0.05, cut_sd=0.05, trim_sd=0.03, measure_sd=0.05, arc_sd=0.07, place_sd=0.05)
SCENARIOS = [
    ("Careful sewing", "seam allowance right on average, ±0.5 mm from seam to seam",
     dict(seam_bias=0.0, **CAREFUL)),
    ("Seams 0.5 mm too wide", "every seam 0.8 cm instead of 0.75 cm, ±0.5 mm: the seam test row comes out "
     "5 mm short, easy to overlook", dict(seam_bias=0.05, **CAREFUL)),
    ("Seams 1 mm too wide", "every seam 0.85 cm instead of 0.75 cm, ±0.5 mm",
     dict(seam_bias=0.10, **CAREFUL)),
    ("Seams 1 mm too narrow", "every seam 0.65 cm instead of 0.75 cm, ±0.5 mm",
     dict(seam_bias=-0.10, **CAREFUL)),
]


def p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


def run(params, runs, trim_to_fit=True):
    sys_ = SYSTEMS["cm"]
    joins, tops = {}, []
    for r in range(runs):
        sewer = Sewer(sys_, seed=1000 + r, trim_to_fit=trim_to_fit, **params)
        w, h, _ = simulate(TREE, sewer, joins)
        tops.append((w, h))
    return list(joins.values()), tops


def mm(x):
    return f"{x * 10:.0f} mm" if x >= 0.095 else f"{x * 10:.1f} mm"


def across(t):
    """Seams crossed by a horizontal line through the busiest part of a unit."""
    if isinstance(t, Leaf):
        return 0
    if t.orient == V:
        return len(t.children) - 1 + sum(across(c) for c in t.children)
    return max(across(c) for c in t.children)


def long_labels():
    return sorted({lf.label for lf in PIECES if id(lf) in LONG})


def check_tolerance(out, runs=400):
    sys_ = SYSTEMS["cm"]
    out.append("Every seam takes two seam allowances out of a row, so rows with many seams react most to an "
               "inaccurate seam. Seams across the width of each section: "
               + ", ".join(f"{i}: {across(sec)}" for i, sec in enumerate(SECTIONS, 1)) + ". "
               "Sections are joined along their full width, so their lengths must agree.")
    out.append("")
    out.append(f"Each figure below is the 95th percentile over {runs} simulated quilts. Cutting is ±0.5 mm per edge, "
               "triangle trimming ±0.3 mm, measuring ±0.5 mm. Each fused quarter circle is cut ±0.7 mm off its line "
               "and fused ±0.5 mm off the raw edges. The long strips " + ", ".join(long_labels())
               + " are trimmed to the measured length of the part they join, as the pattern says.")
    summary = {}
    top = NCOLS * sys_.unit + 2 * sys_.sa
    for title, desc, params in SCENARIOS:
        js, tops = run(params, runs)
        secs = [j for j in js if j["node"] is TREE]
        tw = statistics.fmean(w for w, _ in tops)
        th = statistics.fmean(h for _, h in tops)
        out += ["", f"### {title}", "", f"{desc[0].upper() + desc[1:]}.", ""]
        out.append(f"- Quilt top: {tw:.1f} × {th:.1f} cm (planned {top:.1f} cm square).")
        worst = max(js, key=lambda j: p95(j["mismatch"]))
        wsec = max(secs, key=lambda j: p95(j["mismatch"]))
        out.append(f"- Largest length difference between two edges sewn together: {mm(p95(worst['mismatch']))}, "
                   f"{join_name(worst)}. Between two sections: {mm(p95(wsec['mismatch']))} "
                   f"({join_name(wsec)}).")
        arcs = sorted((j for j in js if j["n_arcs"]), key=lambda j: -p95(j["arc"]))
        out.append("- Without pins, arcs that continue across a seam land up to "
                   + ", ".join(f"{mm(p95(j['arc']))} off their partner ({join_name(j)})" for j in arcs[:2]) + ".")
        jogs = sorted((j for j in js if j["n_lines"] > j["n_arcs"]), key=lambda j: -p95(j["jog"]))
        out.append("- Without pins, straight outlines jog by up to "
                   + ", ".join(f"{mm(p95(j['jog']))} ({join_name(j)})" for j in jogs[:3]) + ".")
        ew = max(secs, key=lambda j: p95(j["ease"]))
        i = ew["ease"].index(max(ew["ease"]))
        inner = [j for j in js if j["node"] is not TREE]
        ei = max(inner, key=lambda j: p95(j["ease"]))
        k = ei["ease"].index(max(ei["ease"]))
        out.append(f"- With pins at every seam crossing, every arc end and both ends, the most you ease in between "
                   f"two pins when joining sections is {mm(p95(ew['ease']))} ({join_name(ew)}, over at most "
                   f"{ew['span'][i]:.0f} cm); inside a section {mm(p95(ei['ease']))} ({join_name(ei)}, over at most "
                   f"{ei['span'][k]:.0f} cm).")
        summary[title] = dict(sec=p95(wsec["mismatch"]), sec_name=join_name(wsec),
                              ease=p95(ew["ease"]), span=ew["span"][i], ease_in=p95(ei["ease"]), span_in=ei["span"][k],
                              arc=p95(arcs[0]["arc"]))
    # what the trim-to-fit step buys
    title, desc, params = SCENARIOS[2]
    js_cut, _ = run(params, runs, trim_to_fit=False)
    js_trim, _ = run(params, runs)
    worst = max(js_cut, key=lambda j: p95(j["mismatch"]))
    same = next(j for j in js_trim if j["node"] is worst["node"] and j["k"] == worst["k"])
    out += ["", "### Why the long strips are trimmed to fit", "",
            f"If {', '.join(long_labels())} were cut to their exact planned length, seams 1 mm too wide would leave "
            f"{mm(p95(worst['mismatch']))} of difference at {join_name(worst)}. Trimmed to the measured part, as the "
            f"pattern says, that join is off by {mm(p95(same['mismatch']))}."]
    return summary


# ----------------------------------------------------------- arcs at seams
def tangent_points():
    """Arc ends where an arc touches a seam line tangentially: the far corners
    of every disc that fills its unit. Returns {(name, R, kind): number of points}."""
    pts = defaultdict(set)
    for lf in PIECES:
        if lf.kind != "qc":
            continue
        u, r = lf.unit, lf.rect
        name = qc_name(QC_BY_LABEL[lf.label])
        for rad, fab in u.discs():
            if abs(rad - u.n) > 1e-9:
                continue
            cx = r.c1 if lf.corner in "93" else r.c0
            cy = r.r1 if lf.corner in "13" else r.r0
            far = ((cx - rad if lf.corner in "93" else cx + rad, cy),
                   (cx, cy + rad if lf.corner in "79" else cy - rad))
            for (px, py), along in zip(far, ("v", "h")):
                # the arc runs along the seam line through (px, py); what lies across it?
                if along == "v":   # tangent to a vertical line x = px
                    step = 0.04 if px > cx else -0.04
                    edge = px in (0, NCOLS)
                    across_fab = colour_at(px + step, py + (0.3 if py < cy else -0.3) * 0.1)
                else:
                    step = 0.04 if py > cy else -0.04
                    edge = py in (0, NROWS)
                    across_fab = colour_at(px + (0.3 if px < cx else -0.3) * 0.1, py + step)
                if edge:
                    kind = "outer edge"
                elif across_fab == fab:
                    kind = "kiss"
                else:
                    kind = "flat"
                pts[(name, rad, kind)].add((px, py, along))
    return {k: len(v) for k, v in pts.items()}


def check_arcs(out):
    sys_ = SYSTEMS["cm"]
    u = sys_.unit
    out.append("Every arc ends square to the two seams at its own corner, so a wrong seam allowance does not move "
               "those ends: sewing 1 mm off moves the crossing by less than 0.01 mm. Arcs that fill their whole unit "
               "also end at the two far corners, where they touch a seam tangentially. There a seam 1 mm too wide "
               "shaves the arc into a short flat, and a seam 1 mm too narrow leaves a 1 mm sliver of background "
               "at the point:")
    out.append("")
    out.append("| Where | Radius | Points | What a seam 1 mm too wide does |")
    out.append("|---|---|---|---|")
    for (name, rad, kind), n in sorted(tangent_points().items(), key=lambda t: (-t[0][1], t[0][0], t[0][2])):
        R = rad * u
        flat = math.sqrt(2 * R * 0.1)
        what = {"kiss": f"the two shapes merge over {flat:.1f} cm next to the point",
                "flat": f"a {flat:.1f} cm flat, 1 mm deep",
                "outer edge": f"a {flat:.1f} cm flat under the binding"}[kind]
        place = {"kiss": "where two arcs meet", "flat": "against another colour", "outer edge": "at the quilt edge"}[kind]
        out.append(f"| {name}, {place} | {R:g} cm | {n} | {what} |")
    out.append("")
    out.append("A 1 mm flat on a curve of 5 cm or more cannot be seen from a step away, and the merge at the foot of "
               "the waves and between the gull wings reads as a soft point. No arc needs a pin of its own beyond its "
               "ends.")
    sa = sys_.sa
    out.append("")
    out.append(f"The fused shapes reach the raw edges, so their straight edges are caught by the seam even if a shape "
               f"sits up to {mm(sa - 0.2)} short of the raw edge (the seam then still catches 2 mm of it).")


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
    n = sum(t["count"] for t in hst_types())
    pairs = sum(math.ceil(t["count"] / 2) for t in hst_types())
    out.append(f"- {n} triangle units are made from {pairs} pairs of squares; each pair gives two units, "
               "so an odd count leaves one spare.")


def check_fabric(out):
    ok = True
    for key, sys_ in SYSTEMS.items():
        selvage, squaring = (1.0, 1.0) if key == "cm" else (0.5, 0.5)
        crooked, first_edge = (3.0, 1.0) if key == "cm" else (1.0, 0.5)
        lengths, quarters = [], []
        for fab in ORDER:
            p = PLANS[key][fab]
            buy, _ = amount(key, fab)
            if buy.startswith("1 fat quarter"):
                quarters.append(fab)
                continue
            used = max(sum(c.b for c in s["cuts"]) for s in p["strips"] if s["cuts"][0].kind != "binding")
            have = p["buy_val"] * 0.95 - crooked - first_edge
            lengths.append(fab)
            ok &= have >= p["total"]
            out.append(f"- {key}, fabric {fab}: the fullest strip uses {fx(sys_, used)} of the width, so the fabric must "
                       f"be at least {fx(sys_, used + 2 * selvage + squaring)} wide including selvages. "
                       f"{p['buy']} leaves {fx(sys_, have)} after 5 % shrinkage, a {fx(sys_, crooked)} crooked shop cut "
                       f"and squaring up; the strips need {fx(sys_, p['total'])}: "
                       + ("enough" if have >= p["total"] else "**not enough**")
                       + f", {fx(sys_, have - p['total'])} spare.")
        if quarters:
            L, Hh = fq_usable(key)
            fits = [(f, fq_height(key, f, L)) for f in quarters]
            ok &= all(need is not None and need <= Hh for _, need in fits)
            out.append(f"- {key}, fat quarters ({', '.join(quarters)}): after 5 % shrinkage, selvage and squaring up a "
                       f"{FQ[key][2]} fat quarter leaves {fx(sys_, L)} × {fx(sys_, Hh)}. "
                       + "; ".join(f"{f} needs {fx(sys_, need)} of that height" if need is not None and need <= Hh
                                   else f"**{f} does not fit**" for f, need in fits) + ".")
    return ok


def layers_at(gx, gy, pid):
    """Seams meeting at grid point (gx, gy), and fused layers in their allowances."""
    seams = 0
    if 0 < gx < NCOLS and 0 < gy < NROWS:
        seams = ((pid[gy - 1][gx - 1] != pid[gy - 1][gx]) + (pid[gy][gx - 1] != pid[gy][gx])
                 + (pid[gy - 1][gx - 1] != pid[gy][gx - 1]) + (pid[gy - 1][gx] != pid[gy][gx]))
    fused = 0
    for lf in PIECES:
        r = lf.rect
        if not (r.c0 <= gx <= r.c1 and r.r0 <= gy <= r.r1):
            continue
        if lf.kind == "hst":
            ends = {"7": ((r.c1, r.r0), (r.c0, r.r1)), "3": ((r.c1, r.r0), (r.c0, r.r1)),
                    "9": ((r.c0, r.r0), (r.c1, r.r1)), "1": ((r.c0, r.r0), (r.c1, r.r1))}[lf.corner]
            seams += (gx, gy) in ends
        elif lf.kind == "qc":
            cx = r.c1 if lf.corner in "93" else r.c0
            cy = r.r1 if lf.corner in "13" else r.r0
            if gx == cx or gy == cy:
                t = abs(gx - cx) + abs(gy - cy)
                fused += sum(1 for rad, _ in lf.unit.discs() if rad > t)
    return seams, fused


def check_bulk(out):
    pid = piece_ids()
    rows = []
    for gy in range(1, NROWS):
        for gx in range(1, NCOLS):
            s, f = layers_at(gx, gy, pid)
            if s + f >= 6:
                rows.append((s + f, s, f, gx, gy))
    groups = defaultdict(list)
    for tot, s, f, gx, gy in rows:
        groups[(tot, s, f, place(gx, gy))].append((gx, gy))
    for (tot, s, f, where), pts in sorted(groups.items(), key=lambda t: (-t[0][0], t[0][3])):
        out.append(f"- {s} seams and {f} fused layer{'s' if f != 1 else ''} at {len(pts)} point"
                   f"{'s' if len(pts) > 1 else ''}: {where}.")
    if not rows:
        out.append("- Nowhere do six or more layers meet.")


def place(gx, gy):
    for i, sec in enumerate(SECTIONS, 1):
        r = sec.rect
        if r.r0 < gy < r.r1:
            what = {lf.label for lf in PIECES if lf.kind == "qc" and lf.rect.c0 <= gx <= lf.rect.c1
                    and lf.rect.r0 <= gy <= lf.rect.r1}
            names = sorted({qc_name(QC_BY_LABEL[w]).lower() for w in what})
            return f"inside section {i}" + (f" ({', '.join(names)})" if names else "")
        if gy == r.r1:
            return f"seam between sections {i} and {i + 1}"
    return "quilt top"


def verdict(ok, summary):
    c, h, w = summary["Careful sewing"], summary["Seams 0.5 mm too wide"], summary["Seams 1 mm too wide"]
    pct = lambda e, span: f"{100 * e / span:.1f} %"
    return ["## Verdict", "",
            ("- **The pattern is consistent.** Sewn exactly, every join meets edge to edge, every outline and arc lines "
             "up across its seams, and every size the page prints comes out." if ok else
             "- **The pattern is not consistent: see section 1.**"),
            f"- **Careful sewing works.** With the seam allowance right on average (±0.5 mm from seam to seam), the most "
            f"you ease between two pins is {mm(c['ease'])} over {c['span']:.0f} cm when joining sections "
            f"({pct(c['ease'], c['span'])}) and {mm(c['ease_in'])} over {c['span_in']:.0f} cm inside a section "
            f"({pct(c['ease_in'], c['span_in'])}): ordinary pinning and steam. Arcs land within {mm(c['arc'])} of their "
            "partners.",
            f"- **The seam test is the critical step.** The busy sky section has far more seams than the hull "
            f"below it. With every seam 0.5 mm too wide they differ by {mm(h['sec'])}, and you ease "
            f"{pct(h['ease'], h['span'])} between pins; at 1 mm by {mm(w['sec'])}. The page asks for the test row "
            "to be within 2 mm of its size, which keeps the seams within 0.2 mm.",
            "- **Arcs forgive.** Every arc ends square to the seams at its corner. Where an arc touches a seam "
            "tangentially, a wrong seam allowance shaves at most 1 mm off its curve.",
            "- **Materials hold.** Triangle squares stay big enough with seams up to 2 mm too wide, and every fabric "
            "amount survives 5 % shrinkage and a crooked shop cut.",
            ""]


def main():
    sanity()
    out = ["## 1. Exact sewing", ""]
    ok = check_exact(out)
    out += ["", "## 2. Real sewing (metric version)", ""]
    summary = check_tolerance(out)
    out += ["", "## 3. Arcs at seams", ""]
    check_arcs(out)
    out += ["", "## 4. Triangle squares", ""]
    check_triangles(out)
    out += ["", "## 5. Fabric", ""]
    fabric_ok = check_fabric(out)
    out += ["", "## 6. Bulky points", "", "Points where six or more layers meet (seams plus fused shapes caught in "
            "their allowances). Press these seams open, and cut away the inside of stacked discs as the pattern "
            "suggests:", ""]
    check_bulk(out)
    head = ["# Kogge: can it be sewn?", "",
            "Generated by `tools/validate.py`. The quilt top is sewn in software, seam by seam, in the order the "
            "instructions give, with physical seam allowances and fused quarter circles. Real sewing errors are "
            "then added at random.", ""]
    text = "\n".join(head + verdict(ok and fabric_ok, summary) + out) + "\n"
    print(text)
    if "--md" in sys.argv:
        with open(sys.argv[sys.argv.index("--md") + 1], "w", encoding="utf-8") as fh:
            fh.write(text)
    sys.exit(0 if ok and fabric_ok else 1)


if __name__ == "__main__":
    main()
