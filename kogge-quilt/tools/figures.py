"""All figures of the Kogge pattern, as inline SVG strings."""
from __future__ import annotations

import math

from modular import H, V, Leaf, Node, Rect, leaves
from plan import (DESIGN, FABRICS, NCOLS, NROWS, ORDER, PIECES, PLANS, SECTIONS, SYSTEMS, TEMPLATE_NO, TREE,
                  arc_points, colour_at, disc_radii, qc_types, section_pins)
from svg import (OPP, TRI, draw_exploded, explode, f, hlines, hst_shapes, label_text, leaf_shapes,
                 qc_shapes, quarter_arc, quarter_path, svg_wrap, wave_lines)


def whole(s, ox=0.0, oy=0.0, labels=False, seams=False, pieces=None):
    parts, labs, edges = [], [], []
    for p in (pieces or PIECES):
        x, y = ox + p.rect.c0 * s, oy + p.rect.r0 * s
        parts.append(leaf_shapes(p, x, y, s))
        if seams:
            edges.append(f'<rect class="seam" x="{f(x)}" y="{f(y)}" width="{f(p.rect.w * s)}" height="{f(p.rect.h * s)}"/>')
        if labels:
            labs.append(label_text(p, x, y, s))
    return "".join(parts) + "".join(edges) + "".join(labs)


# ------------------------------------------------------------------ hero
def region_shapes(s, ox, oy, fabrics, pick=None):
    """Mask shapes covering every part of the top cut from `fabrics`: white
    where the fabric shows, black over the discs fused onto it.
    pick: optional test that a solid piece must pass as well.

    (A mask, not a clip path: Chrome unites the shapes of a clip path with
    path operations, and when those fail on shared edges it quietly keeps
    only the first shape.)"""
    out = []
    for p in PIECES:
        x, y = ox + p.rect.c0 * s, oy + p.rect.r0 * s
        if p.kind == "solid" and p.fabric in fabrics and (pick is None or pick(p)):
            out.append(f'<rect fill="#fff" x="{f(x)}" y="{f(y)}" width="{f(p.rect.w * s)}" height="{f(p.rect.h * s)}"/>')
        elif p.kind == "hst" and pick is None:
            if p.a in fabrics:
                out.append(f'<polygon fill="#fff" points="{" ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in TRI[p.corner])}"/>')
            if p.b in fabrics:
                out.append(f'<polygon fill="#fff" points="{" ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in OPP[p.corner])}"/>')
        elif p.kind == "qc" and p.unit.bg in fabrics and pick is None:
            S = p.unit.n * s
            out.append(f'<rect fill="#fff" x="{f(x)}" y="{f(y)}" width="{f(S)}" height="{f(S)}"/>'
                       f'<path fill="#000" d="{quarter_path(p.corner, *corner_xy(p, x, y, S), S)}"/>')
    return "".join(out)


def region_mask(mid, w, h, *shapes):
    return (f'<mask id="{mid}" maskUnits="userSpaceOnUse" x="0" y="0" width="{f(w)}" height="{f(h)}">'
            + "".join(shapes) + "</mask>")


def corner_xy(p, x, y, S):
    return (x + (S if p.corner in "93" else 0), y + (S if p.corner in "13" else 0))


def hero_svg(s=22):
    uid = "hero"
    m = s * 0.22
    pad = s * 0.6
    W = NCOLS * s + 2 * (m + pad)
    ox = oy = m + pad
    defs = (region_mask(f"{uid}-sky", W, W, region_shapes(s, ox, oy, {"S"}))
            + region_mask(f"{uid}-sea", W, W, region_shapes(s, ox, oy, {"N"}))
            + f'<filter id="{uid}-mottle" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="4" seed="23"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.25 -0.52"/></filter>'
            f'<filter id="{uid}-grain" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="5"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 -0.42"/></filter>'
            f'<filter id="{uid}-soft" x="-10%" y="-10%" width="120%" height="125%">'
            f'<feGaussianBlur stdDeviation="{f(s * 0.35)}"/></filter>')
    q0x, q0y, qw = ox - m, oy - m, NCOLS * s + 2 * m
    quilt = (f'<g mask="url(#{uid}-sky)"><path class="q-light" d="{hlines(ox, oy, NCOLS * s, NROWS * s, s * 0.5)}"/></g>'
             f'<g mask="url(#{uid}-sea)"><path class="q-dark" d="{wave_lines(ox, oy, NCOLS * s, NROWS * s, s * 0.34, s * 0.07, s * 1.2)}"/></g>')
    body = (f'<rect x="{f(q0x + s * 0.15)}" y="{f(q0y + s * 0.35)}" width="{f(qw)}" height="{f(qw)}" class="shadow" filter="url(#{uid}-soft)"/>'
            f'<rect class="fN" x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}"/>'
            f'{whole(s, ox, oy)}{quilt}'
            f'<rect x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}" filter="url(#{uid}-mottle)" opacity=".18"/>'
            f'<rect x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}" filter="url(#{uid}-grain)" opacity=".2"/>')
    return svg_wrap(body, W, W, cls="hero-svg",
                    title="Kogge quilt: a medieval cog with a red and white striped sail on teal waves, a rising sun and herring below",
                    extra_defs=defs)


# ---------------------------------------------------------- module key
def module_key_svg(s=56):
    from modular import QCUnit
    gap = 40
    big = s * 1.5
    base = 14 + big          # common bottom line
    x = 10
    out, caps = [], []

    def frame(x0, size):
        return f'<rect class="edge" x="{f(x0)}" y="{f(base - size)}" width="{f(size)}" height="{f(size)}"/>'

    out.append(f'<rect class="fS" x="{x}" y="{f(base - s)}" width="{s}" height="{s}"/>' + frame(x, s))
    caps.append((x + s / 2, "Square"))
    x += s + gap
    out.append(hst_shapes("9", "R", "S", x, base - s, s) + frame(x, s))
    caps.append((x + s / 2, "Triangle"))
    x += s + gap
    u = QCUnit(0, Rect(0, 0, 1, 1), "1", "N", "S")
    out.append(qc_shapes(u, "1", x, base - s, s) + frame(x, s))
    caps.append((x + s / 2, "Quarter circle"))
    x += s + gap
    u2 = QCUnit(0, Rect(0, 0, 2, 2), "3", "T", "S", ((1.0, "A"),))
    out.append(qc_shapes(u2, "3", x, base - big, big / 2) + frame(x, big))
    caps.append((x + big / 2, "Rings"))
    x += big + 10
    for cx, t in caps:
        out.append(f'<text class="cap" x="{f(cx)}" y="{f(base + 24)}">{t}</text>')
    return svg_wrap("".join(out), x, base + 34, cls="dia modkey", title="The four modules of the design")


# --------------------------------------------------------- layout chart
def unit_labels(s, ox, oy, fs=8.5):
    """Codes of the triangle and quarter-circle units, for the layout chart."""
    out = []
    for p in PIECES:
        x, y = ox + p.rect.c0 * s, oy + p.rect.r0 * s
        if p.kind == "hst":          # in the middle of the other half
            (u, v) = [sum(c) / 3 for c in zip(*OPP[p.corner])]
            out.append(f'<text class="lb lb{p.b}" x="{f(x + u * s)}" y="{f(y + v * s)}" font-size="{fs}">{p.label}</text>')
        elif p.kind == "qc":         # in the outermost ring, on the diagonal
            radii = [r for r, _ in p.unit.discs()] + [0.0]
            mid = (radii[0] + radii[1]) / 2
            fab = p.unit.discs()[0][1]
            S = p.unit.n * s
            cx, cy = corner_xy(p, x, y, S)
            dx = -1 if p.corner in "93" else 1
            dy = -1 if p.corner in "13" else 1
            d = mid * s / math.sqrt(2)
            out.append(f'<text class="lb lb{fab}" x="{f(cx + dx * d)}" y="{f(cy + dy * d)}" font-size="{fs}">{p.label}</text>')
    return "".join(out)


def chart_svg(s=30):
    left = 84
    W = left + NCOLS * s + 12
    Hh = 10 + NROWS * s + 12
    ox, oy = left, 10
    body = [whole(s, ox, oy, labels=True, seams=True), unit_labels(s, ox, oy)]
    for i, sec in enumerate(SECTIONS, 1):
        y0, y1 = oy + sec.rect.r0 * s + 3, oy + sec.rect.r1 * s - 3
        body.append(f'<path class="bracket" d="M{left - 8},{f(y0)} h-6 V{f(y1)} h6"/>')
        body.append(f'<text class="mark end" x="{left - 20}" y="{f((y0 + y1) / 2)}">{i}</text>')
    body.append(f'<rect class="outline" x="{ox}" y="{oy}" width="{NCOLS * s}" height="{NROWS * s}"/>')
    return svg_wrap("".join(body), W, Hh, cls="dia chart", title="Layout chart with every piece code")


def map_svg(s=18):
    left = 30
    W = left + NCOLS * s + 6
    Hh = NROWS * s + 6
    parts = [whole(s, left, 3, seams=True)]
    for i, sec in enumerate(SECTIONS, 1):
        y0, y1 = 3 + sec.rect.r0 * s, 3 + sec.rect.r1 * s
        parts.append(f'<rect class="secline" x="{left}" y="{f(y0)}" width="{NCOLS * s}" height="{f(y1 - y0)}"/>')
        parts.append(f'<text class="mark" x="{left - 13}" y="{f((y0 + y1) / 2)}">{i}</text>')
    return svg_wrap("".join(parts), W, Hh, cls="dia map", title="The quilt divided into its sections")


def thumb_svg(i, s=4):
    sec = SECTIONS[i - 1]
    dim, hi = [], []
    for p in PIECES:
        x, y = p.rect.c0 * s, p.rect.r0 * s
        (hi if sec.rect.contains(p.rect) else dim).append(leaf_shapes(p, x, y, s))
    r = sec.rect
    body = (f'<g opacity=".28">{"".join(dim)}</g>{"".join(hi)}'
            f'<rect class="thumbsel" x="{f(r.c0 * s)}" y="{f(r.r0 * s)}" width="{f(r.w * s)}" height="{f(r.h * s)}"/>')
    return svg_wrap(body, NCOLS * s, NROWS * s, cls="thumb", title=f"Position of section {i}")


# ------------------------------------------------------- section figures
def section_svg(i, s=34, gap=7, pad=2):
    sec = SECTIONS[i - 1]
    body, w, h, items = draw_exploded(sec, s, gap=gap, pad=pad)
    top, bottom = section_pins(i)
    mg = 13

    def seam_x(gx, row_attr, row):
        right = left = None
        for lf, x, y in items:
            if getattr(lf.rect, row_attr) != row:
                continue
            if lf.rect.c1 == gx:
                right = x + lf.rect.w * s
            if lf.rect.c0 == gx:
                left = x
        if right is None or left is None:
            return None
        return pad + (right + left) / 2

    marks = []
    for gx in top:
        x = seam_x(gx, "r0", sec.rect.r0)
        if x is not None:
            marks.append(f'<polygon class="pin" points="{f(x - 5)},{f(mg - 9)} {f(x + 5)},{f(mg - 9)} {f(x)},{f(mg - 2)}"/>')
    for gx in bottom:
        x = seam_x(gx, "r1", sec.rect.r1)
        if x is not None:
            yy = mg + h
            marks.append(f'<polygon class="pin" points="{f(x - 5)},{f(yy + 9)} {f(x + 5)},{f(yy + 9)} {f(x)},{f(yy + 2)}"/>')
    # ring ends to match: a dot on both pieces that meet there
    dots = []
    for gx, gy, _ in arc_points(sec):
        for lf, x, y in items:
            r = lf.rect
            if r.c0 <= gx <= r.c1 and r.r0 <= gy <= r.r1 and (gx in (r.c0, r.c1) or gy in (r.r0, r.r1)):
                dots.append(f'<circle class="pindot" cx="{f(pad + x + (gx - r.c0) * s)}" cy="{f(pad + y + (gy - r.r0) * s)}" r="3.6"/>')
    inner = f'<g transform="translate(0 {mg})">{body}{"".join(dots)}</g>' + "".join(marks)
    return svg_wrap(inner, w, h + 2 * mg, cls="dia exploded", title=f"Section {i}, exploded")


def assembly_svg(s=14, gap=12):
    """The sections stacked with gaps, each drawn assembled."""
    y = 0
    parts = []
    W = NCOLS * s
    for i, sec in enumerate(SECTIONS, 1):
        secs = [p for p in PIECES if sec.rect.contains(p.rect)]
        parts.append(whole(s, 0, y - sec.rect.r0 * s, pieces=secs))
        parts.append(f'<rect class="edge" x="0" y="{f(y)}" width="{f(W)}" height="{f(sec.rect.h * s)}"/>')
        y += sec.rect.h * s + gap
    return svg_wrap("".join(parts), W, y - gap, cls="dia assembly", title="Join the sections from top to bottom")


# ------------------------------------------------------------ unit figures
def qc_unit_svg(q, s=None, show_layers=True):
    """One quarter-circle unit type: the layers spread out, then the finished unit."""
    from modular import QCUnit
    size = 116
    s = s or size / q["n"]
    u = QCUnit(0, Rect(0, 0, q["n"], q["n"]), "1", q["discs"][0][1], q["bg"], tuple(q["discs"][1:]))
    out = []
    x = 6
    y = 6
    if show_layers:
        S = q["n"] * s
        out.append(f'<rect class="f{q["bg"]}" x="{x}" y="{y}" width="{f(S)}" height="{f(S)}"/><rect class="edge" x="{x}" y="{y}" width="{f(S)}" height="{f(S)}"/>')
        x += S + 18
        for r, fab in q["discs"]:
            R = r * s
            out.append(f'<path class="f{fab}" d="{quarter_path("1", x, y + S, R)}"/><path class="edge" d="{quarter_path("1", x, y + S, R)}"/>')
            x += R + 14
        x += 10
        out.append(f'<text class="arrowtxt" x="{f(x - 14)}" y="{f(y + S / 2)}">→</text>')
        x += 8
    out.append(qc_shapes(u, "1", x, y, s) + f'<rect class="edge" x="{f(x)}" y="{y}" width="{f(q["n"] * s)}" height="{f(q["n"] * s)}"/>')
    W = x + q["n"] * s + 6
    return svg_wrap("".join(out), W, q["n"] * s + 12, cls="dia qcunit", title=f"Quarter-circle unit {q['label']}")


def qc_method_svg(sys_key):
    sy = SYSTEMS[sys_key]
    s = 90  # px per grid unit, for a one-unit example
    a = sy.sa / sy.unit * s
    out = []
    caps = []
    x, y = 10, 28
    S = s + 2 * a
    # 1 trace on fusible web
    out.append(f'<rect class="web" x="{x}" y="{y}" width="{f(S)}" height="{f(S)}"/>')
    out.append(f'<path class="pen" d="{template_path(x, y, s, a, 1, corner="1", total=S)}"/>')
    caps.append((x + S / 2, "1  Trace on fusible web"))
    x += S + 46
    # 2 fuse to fabric, cut out
    out.append(f'<path class="fN" d="{template_path(x, y, s, a, 1, corner="1", total=S)}"/><path class="edge" d="{template_path(x, y, s, a, 1, corner="1", total=S)}"/>')
    caps.append((x + S / 2, "2  Fuse, cut out"))
    x += S + 46
    # 3 place on the square, straight edges on the raw edges
    out.append(f'<rect class="fS" x="{x}" y="{y}" width="{f(S)}" height="{f(S)}"/>')
    out.append(f'<path class="fN" d="{template_path(x, y, s, a, 1, corner="1", total=S)}"/>')
    out.append(f'<rect class="sa" x="{f(x + a)}" y="{f(y + a)}" width="{f(s)}" height="{f(s)}"/>')
    caps.append((x + S / 2, "3  Fuse into the corner"))
    x += S + 46
    # 4 stitch the arc
    out.append(f'<rect class="fS" x="{x}" y="{y}" width="{f(S)}" height="{f(S)}"/>')
    out.append(f'<path class="fN" d="{template_path(x, y, s, a, 1, corner="1", total=S)}"/>')
    cx, cy = x + a, y + S - a
    R = s - 0.12 * s
    out.append(f'<path class="stitch" d="M{f(cx)},{f(cy - R)} A{f(R)},{f(R)} 0 0 1 {f(cx + R)},{f(cy)}"/>')
    caps.append((x + S / 2, "4  Stitch along the arc"))
    W = x + S + 10
    for cxp, t in caps:
        out.append(f'<text class="cap" x="{f(cxp)}" y="{f(y + S + 34)}">{t}</text>')
    return svg_wrap("".join(out), W, y + S + 46, cls="dia qcmethod", title="Making a quarter-circle unit with fusible appliqué")


def template_path(x, y, s, a, r, corner="7", total=None):
    """Template outline: quarter disc of radius r units around the finished corner,
    including the seam allowance along both straight edges. Drawn in a box
    whose top-left is (x, y); corner says which corner of the box holds the centre."""
    R = r * s
    # in local coordinates with the centre at (a, a) and the raw corner at (0, 0)
    e = a + math.sqrt(max(R * R - a * a, 0))
    pts_local = [(0, 0), (e, 0)]
    arc_end = (0, e)
    tot = total if total is not None else e
    def tx(px, py):
        if corner == "7":
            return x + px, y + py
        if corner == "1":
            return x + px, y + tot - py
        if corner == "9":
            return x + tot - px, y + py
        return x + tot - px, y + tot - py
    p0 = tx(0, 0)
    p1 = tx(e, 0)
    p2 = tx(0, e)
    sweep = 1 if corner in "73" else 0
    return (f"M{f(p0[0])},{f(p0[1])} L{f(p1[0])},{f(p1[1])} "
            f"A{f(R)},{f(R)} 0 0 {sweep} {f(p2[0])},{f(p2[1])} Z")


def tpl_strokes(unit):
    """Line styles for true-size sheets: 0.35 mm outlines, 0.25 mm dashed seams,
    whatever the drawing unit."""
    k = 1.0 if unit == "mm" else 1 / 25.4
    return (f"stroke-width:{0.35 * k:.4f}",
            f"stroke-width:{0.25 * k:.4f};stroke-dasharray:{2 * k:.4f} {1.5 * k:.4f}")


def template_drawing(sys_key, r):
    """Template for radius r grid units, in true-size drawing units: mm for the
    metric pattern, inches for the imperial one. Returns (body, W, unit)."""
    sy = SYSTEMS[sys_key]
    unit, k = ("mm", 10.0) if sys_key == "cm" else ("in", 1.0)
    s = sy.unit * k
    a = sy.sa * k
    R = r * s
    e = a + math.sqrt(R * R - a * a)
    m = 6.0 if unit == "mm" else 0.25   # 6 mm margin round the template
    W = e + 2 * m
    line, seam = tpl_strokes(unit)
    body = [f'<path class="tpl" style="{line}" d="{template_path(m, m, s, a, r)}"/>',
            f'<path class="tplsa" style="{seam}" d="M{f(m + a)},{f(m + a)} L{f(m + a + R - 0.001)},{f(m + a)} M{f(m + a)},{f(m + a)} L{f(m + a)},{f(m + a + R)}"/>',
            f'<circle class="tpldot" cx="{f(m + a)}" cy="{f(m + a)}" r="{f(1.2 if unit == "mm" else 0.05)}"/>']
    fs = (3.2 if unit == "mm" else 0.13) * (1.0 if r <= 1 else 1.3)
    tx, ty = m + a + fs * 1.0, m + a + fs * 2.6
    body.append(f'<text class="tpltxt" x="{f(tx)}" y="{f(ty)}" font-size="{f(fs * 1.4)}" font-weight="700">Template {TEMPLATE_NO[r]}</text>')
    body.append(f'<text class="tpltxt" x="{f(tx)}" y="{f(ty + fs * 1.7)}" font-size="{f(fs)}">radius {sy.fmt(r * sy.unit)}</text>')
    if r > 1:
        body.append(f'<text class="tpltxt" x="{f(tx)}" y="{f(ty + fs * 3.4)}" font-size="{f(fs)}">• = corner of the finished unit</text>')
        body.append(f'<text class="tpltxt" x="{f(tx)}" y="{f(ty + fs * 4.9)}" font-size="{f(fs)}">dashed = seam lines</text>')
    return "".join(body), W, unit


def template_sheet_svg(sys_key, r):
    """True-size template for radius r grid units, in mm (cm) or inches."""
    body, W, unit = template_drawing(sys_key, r)
    return (f'<svg class="tplsvg" viewBox="0 0 {f(W)} {f(W)}" width="{f(W)}{unit}" height="{f(W)}{unit}" '
            f'role="img" xmlns="http://www.w3.org/2000/svg"><title>Template {TEMPLATE_NO[r]}, radius {SYSTEMS[sys_key].fmt(r * SYSTEMS[sys_key].unit)}</title>{body}</svg>')


# The printable area A4 and US Letter share with the PDF margins, less room for
# a caption: every part of a large template fits on one page of either paper.
PART_MAX_MM = (182.0, 227.0)
PART_OVERLAP_MM = 10.0


def template_fits(sys_key, r):
    _, W, unit = template_drawing(sys_key, r)
    side = W * (1.0 if unit == "mm" else 25.4)
    return side <= PART_MAX_MM[0] and side <= PART_MAX_MM[1]


def template_parts(sys_key, r):
    """A template too big for one page, split into overlapping page-sized parts.
    Returns (parts, key): parts = [(number, svg)], key = a small map of how
    they go together."""
    body, W, unit = template_drawing(sys_key, r)
    to_mm = 1.0 if unit == "mm" else 25.4
    mm = 1.0 / to_mm                                  # one millimetre in drawing units
    ov = PART_OVERLAP_MM * mm
    maxw, maxh = PART_MAX_MM[0] * mm, PART_MAX_MM[1] * mm
    cols = max(1, math.ceil((W - ov) / (maxw - ov) - 1e-9))
    rows = max(1, math.ceil((W - ov) / (maxh - ov) - 1e-9))
    xs = [W * i / cols for i in range(cols + 1)]
    ys = [W * j / rows for j in range(rows + 1)]
    line, seam = tpl_strokes(unit)
    fs = 3.4 * mm
    no = TEMPLATE_NO[r]
    n = cols * rows

    def ticks(a, b, step=40.0):
        """Positions of matching marks along a join from a to b."""
        inner_a, inner_b = a + 12 * mm, b - 12 * mm
        k = max(1, int((inner_b - inner_a) // (step * mm)) + 1)
        return [inner_a + (inner_b - inner_a) * (t + 0.5) / k for t in range(k)]

    parts = []
    for j in range(rows):
        for i in range(cols):
            idx = j * cols + i + 1
            x0, x1 = xs[i] - (ov if i else 0), xs[i + 1]
            y0, y1 = ys[j] - (ov if j else 0), ys[j + 1]
            assert x1 - x0 <= maxw + 1e-9 and y1 - y0 <= maxh + 1e-9, (sys_key, r, idx)
            extra = []
            if i:   # tape zone: the part on the left is laid over it
                extra.append(f'<rect class="tplglue" x="{f(x0)}" y="{f(y0)}" width="{f(ov)}" height="{f(y1 - y0)}"/>')
                extra.append(f'<path class="tplsa" style="{seam}" d="M{f(xs[i])},{f(y0)} V{f(y1)}"/>')
                tx, ty = x0 + ov / 2, (max(y0, ys[j]) + y1) / 2
                extra.append(f'<text class="tpltxt" x="{f(tx)}" y="{f(ty)}" font-size="{f(fs * 0.8)}" text-anchor="middle" '
                             f'dominant-baseline="central" transform="rotate(-90 {f(tx)} {f(ty)})">part {idx - 1} goes on here</text>')
                for t in ticks(max(y0, ys[j]), y1):
                    extra.append(f'<path class="tpl" style="{line}" d="M{f(xs[i] - 3 * mm)},{f(t)} H{f(xs[i] + 3 * mm)}"/>')
            if j:
                extra.append(f'<rect class="tplglue" x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" height="{f(ov)}"/>')
                extra.append(f'<path class="tplsa" style="{seam}" d="M{f(x0)},{f(ys[j])} H{f(x1)}"/>')
                extra.append(f'<text class="tpltxt" x="{f((max(x0, xs[i]) + x1) / 2)}" y="{f(y0 + ov / 2)}" font-size="{f(fs * 0.8)}" '
                             f'text-anchor="middle" dominant-baseline="central">part {idx - cols} goes on here</text>')
                for t in ticks(max(x0, xs[i]), x1):
                    extra.append(f'<path class="tpl" style="{line}" d="M{f(t)},{f(ys[j] - 3 * mm)} V{f(ys[j] + 3 * mm)}"/>')
            if i < cols - 1:   # this part is cut along its right edge and laid over the next
                extra.append(f'<path class="tpl" style="{line}" d="M{f(x1)},{f(y0)} V{f(y1)}"/>')
                extra.append(f'<text class="tpltxt" x="{f(x1 - 2 * mm)}" y="{f(max(y0, ys[j]) + 6 * mm)}" font-size="{f(fs)}" text-anchor="end">✂ cut</text>')
                for t in ticks(max(y0, ys[j]), y1):
                    extra.append(f'<path class="tpl" style="{line}" d="M{f(x1 - 3 * mm)},{f(t)} H{f(x1)}"/>')
            if j < rows - 1:
                extra.append(f'<path class="tpl" style="{line}" d="M{f(x0)},{f(y1)} H{f(x1)}"/>')
                extra.append(f'<text class="tpltxt" x="{f(max(x0, xs[i]) + 2 * mm)}" y="{f(y1 - 2.5 * mm)}" font-size="{f(fs)}">✂ cut</text>')
                for t in ticks(max(x0, xs[i]), x1):
                    extra.append(f'<path class="tpl" style="{line}" d="M{f(t)},{f(y1 - 3 * mm)} V{f(y1)}"/>')
            # the part's own label and where it sits in the whole
            lx, ly = max(x0, xs[i]) + 8 * mm, y1 - 30 * mm
            cell = 6 * mm
            extra.append(f'<text class="tpltxt" x="{f(lx)}" y="{f(ly)}" font-size="{f(fs * 1.5)}" font-weight="700">Template {no}</text>')
            extra.append(f'<text class="tpltxt" x="{f(lx)}" y="{f(ly + fs * 1.6)}" font-size="{f(fs)}">part {idx} of {n}</text>')
            for jj in range(rows):
                for ii in range(cols):
                    cls = "tplmapon" if (ii, jj) == (i, j) else "tplmap"
                    extra.append(f'<rect class="{cls}" style="{line}" x="{f(lx + ii * cell)}" y="{f(ly + fs * 2.6 + jj * cell)}" width="{f(cell)}" height="{f(cell)}"/>')
            svg = (f'<svg class="tplsvg" viewBox="{f(x0)} {f(y0)} {f(x1 - x0)} {f(y1 - y0)}" width="{f(x1 - x0)}{unit}" '
                   f'height="{f(y1 - y0)}{unit}" role="img" xmlns="http://www.w3.org/2000/svg">'
                   f'<title>Template {no}, part {idx} of {n}</title>{body}{"".join(extra)}</svg>')
            parts.append((idx, svg))
    # a small map: the whole template with its parts numbered
    k = 150 / W
    key = [f'<rect class="stripbg" x="0" y="0" width="{f(W * k)}" height="{f(W * k)}"/>',
           f'<g transform="scale({f(k)})"><path class="pen" vector-effect="non-scaling-stroke" '
           f'd="{template_path(*_tpl_box(sys_key, r))}"/></g>']
    for j in range(rows):
        for i in range(cols):
            key.append(f'<rect class="dim" x="{f(xs[i] * k)}" y="{f(ys[j] * k)}" width="{f((xs[i + 1] - xs[i]) * k)}" height="{f((ys[j + 1] - ys[j]) * k)}"/>')
            key.append(f'<text class="mark" x="{f((xs[i] + xs[i + 1]) / 2 * k)}" y="{f((ys[j] + ys[j + 1]) / 2 * k)}">{j * cols + i + 1}</text>')
    return parts, svg_wrap("".join(key), W * k, W * k, cls="tplkey", title=f"How the parts of template {no} go together")


def _tpl_box(sys_key, r):
    """Arguments for template_path() matching template_drawing()."""
    sy = SYSTEMS[sys_key]
    k = 10.0 if sys_key == "cm" else 1.0
    m = 6.0 if sys_key == "cm" else 0.25
    return m, m, sy.unit * k, sy.sa * k, r


def test_square_mini(sys_key):
    """A small true-size square to check the print scale on every template page."""
    if sys_key == "cm":
        return ('<svg class="tplsvg mini" viewBox="0 0 22 22" width="22mm" height="22mm" role="img" xmlns="http://www.w3.org/2000/svg">'
                f'<title>2 cm test square</title><rect class="tpl" style="{tpl_strokes("mm")[0]}" x="1" y="1" width="20" height="20"/>'
                '<text class="tpltxt" x="11" y="12.2" font-size="4" text-anchor="middle">2 cm</text></svg>')
    return ('<svg class="tplsvg mini" viewBox="0 0 1.1 1.1" width="1.1in" height="1.1in" role="img" xmlns="http://www.w3.org/2000/svg">'
            f'<title>1 inch test square</title><rect class="tpl" style="{tpl_strokes("in")[0]}" x=".05" y=".05" width="1" height="1"/>'
            '<text class="tpltxt" x=".55" y=".6" font-size=".18" text-anchor="middle">1″</text></svg>')


def test_square_svg(sys_key):
    if sys_key == "cm":
        return ('<svg class="tplsvg" viewBox="0 0 54 54" width="54mm" height="54mm" role="img" xmlns="http://www.w3.org/2000/svg">'
                f'<title>Print check: 5 cm square</title><rect class="tpl" style="{tpl_strokes("mm")[0]}" x="2" y="2" width="50" height="50"/>'
                '<text class="tpltxt" x="27" y="29" font-size="5" text-anchor="middle">5 cm</text></svg>')
    return ('<svg class="tplsvg" viewBox="0 0 2.2 2.2" width="2.2in" height="2.2in" role="img" xmlns="http://www.w3.org/2000/svg">'
            f'<title>Print check: 2 inch square</title><rect class="tpl" style="{tpl_strokes("in")[0]}" x="0.1" y="0.1" width="2" height="2"/>'
            '<text class="tpltxt" x="1.1" y="1.15" font-size="0.22" text-anchor="middle">2″</text></svg>')


# -------------------------------------------------------------- HST figure
def hst_method_svg(sys_key, a="W", b="N"):
    sy = SYSTEMS[sys_key]
    S = 104
    k = S / sy.hst_cut
    sa = sy.sa * k
    o = sa * math.sqrt(2)
    gap = 60
    y = 30
    out, cap = [], []
    x = 10
    out.append(f'<rect class="f{b}" x="{f(x + 7)}" y="{f(y + 7)}" width="{S}" height="{S}"/>')
    out.append(f'<rect class="f{a}" x="{f(x)}" y="{f(y)}" width="{S}" height="{S}"/>')
    out.append(f'<rect class="wrongside" x="{f(x)}" y="{f(y)}" width="{S}" height="{S}"/>')
    out.append(f'<path class="pen" d="M{f(x)},{f(y)} L{f(x + S)},{f(y + S)}"/>')
    out.append(f'<path class="stitch" d="M{f(x + o)},{f(y)} L{f(x + S)},{f(y + S - o)} M{f(x)},{f(y + o)} L{f(x + S - o)},{f(y + S)}"/>')
    out.append(f'<text class="dimtxt" x="{f(x + S / 2)}" y="{f(y - 12)}">{sy.fmt(sy.hst_cut)} squares</text>')
    cap.append((x + S / 2, "1  Draw, then sew"))
    x2 = x + S + gap
    d = 8
    for dx, dy, pts in ((d, -d, ((0, 0), (S, 0), (S, S))), (-d, d, ((0, 0), (0, S), (S, S)))):
        P = " ".join(f"{f(x2 + dx + px)},{f(y + dy + py)}" for px, py in pts)
        Pb = " ".join(f"{f(x2 + dx + px + 6)},{f(y + dy + py + 6)}" for px, py in pts)
        out.append(f'<polygon class="f{b}" points="{Pb}"/><polygon class="f{a}" points="{P}"/><polygon class="wrongside" points="{P}"/>')
    cap.append((x2 + S / 2, "2  Cut on the line"))
    x3 = x2 + S + gap
    side = (sy.hst_cut - sy.sa * math.sqrt(2)) * k
    trim = (sy.unit + 2 * sy.sa) * k
    yy = y + (S - side) / 2
    out.append(hst_shapes("9", a, b, x3, yy, side))
    off = (side - trim) / 2
    out.append(f'<rect class="trim" x="{f(x3 + off)}" y="{f(yy + off)}" width="{f(trim)}" height="{f(trim)}"/>')
    cap.append((x3 + side / 2, "3  Press, square up"))
    x4 = x3 + side + gap
    yy4 = y + (S - trim) / 2
    out.append(hst_shapes("9", a, b, x4, yy4, trim))
    out.append(f'<path class="dim" d="M{f(x4)},{f(yy4 + trim + 12)} h{f(trim)} M{f(x4)},{f(yy4 + trim + 7)} v10 M{f(x4 + trim)},{f(yy4 + trim + 7)} v10"/>')
    out.append(f'<text class="dimtxt" x="{f(x4 + trim / 2)}" y="{f(yy4 + trim + 28)}">{sy.fmt(sy.unit + 2 * sy.sa)}</text>')
    cap.append((x4 + trim / 2, "4  Ready to use"))
    W = x4 + trim + 12
    for cx, t in cap:
        out.append(f'<text class="cap" x="{f(cx)}" y="{f(y + S + 50)}">{t}</text>')
    return svg_wrap("".join(out), W, y + S + 58, cls="dia hstfig", title="Half-square triangles two at a time")


# ------------------------------------------------------------ strip plans
def strip_svgs(sys_key, fab, width_px=660):
    sy = SYSTEMS[sys_key]
    k = width_px / sy.wof                       # one scale for every strip, fat-quarter strips are shorter
    plan = PLANS[sys_key][fab]
    L = plan["length"] * k
    figs = []
    n = 0
    for st in plan["strips"]:
        if st["cuts"][0].kind == "binding":
            continue
        n += 1
        h = st["width"] * k
        parts = [f'<rect class="stripbg" x="0" y="0" width="{f(L)}" height="{f(h)}"/>']
        x = 0
        for c in st["cuts"]:
            w = c.b * k
            ph = c.a * k
            parts.append(f'<rect class="f{fab}" x="{f(x)}" y="0" width="{f(w)}" height="{f(ph)}"/>')
            if c.extra and c.extra_on == "b":      # the pale part is trimmed off later
                parts.append(f'<rect class="extra" x="{f(x + (c.b - c.extra) * k)}" y="0" width="{f(c.extra * k)}" height="{f(ph)}"/>')
            elif c.extra:
                parts.append(f'<rect class="extra" x="{f(x)}" y="{f(ph - c.extra * k)}" width="{f(w)}" height="{f(c.extra * k)}"/>')
            if c.kind == "hst":
                parts.append(f'<path class="sqdiag" d="M{f(x + 5)},5 L{f(x + w - 5)},{f(ph - 5)}"/>')
            if c.kind == "disc":
                R = min(w, ph) - 8
                parts.append(f'<path class="discmark" d="M{f(x + 4)},{f(4 + R)} A{f(R)},{f(R)} 0 0 1 {f(x + 4 + R)},4"/>')
            parts.append(f'<rect class="cutedge" x="{f(x)}" y="0" width="{f(w)}" height="{f(ph)}"/>')
            if c.trimmed:
                parts.append(f'<rect class="waste" x="{f(x)}" y="{f(ph)}" width="{f(w)}" height="{f(h - ph)}"/>')
            if c.kind in ("piece", "qcbg"):
                fs = 11 if w > 26 else 9
                parts.append(f'<text class="lb lb{fab}" x="{f(x + w / 2)}" y="{f(ph / 2)}" font-size="{fs}">{c.label}</text>')
            x += w
        if st["free"] > 1e-6:
            parts.append(f'<rect class="waste" x="{f(x)}" y="0" width="{f(L - x)}" height="{f(h)}"/>')
        figs.append((n, st, svg_wrap("".join(parts), width_px, h, cls="dia strip", title=f"Strip {n}")))
    return figs


# ------------------------------------------------------------ quilting
def ditch_path(s, ox, oy):
    """Stitch-in-the-ditch lines: every edge between the background (sky above
    the waterline, navy below) and a shape on it."""
    def bg(fab, y):
        return fab == ("S" if y < 16 else "N")

    unit_at = {}
    for p in PIECES:
        if p.kind == "qc":
            for r, c in p.rect.cells():
                unit_at[(r, c)] = id(p)
    eps = 0.01
    along = (0.3, 0.5, 0.7)             # an edge counts only if the outline follows all of it,
    d = []                              # not where an arc merely touches it
    for r in range(1, NROWS):                       # horizontal grid edges
        for c in range(NCOLS):
            if unit_at.get((r - 1, c), -1) == unit_at.get((r, c), -2):
                continue
            if all(bg(colour_at(c + t, r - eps), r - 0.5) != bg(colour_at(c + t, r + eps), r + 0.5) for t in along):
                d.append(f"M{f(ox + c * s)},{f(oy + r * s)} h{f(s)}")
    for c in range(1, NCOLS):                       # vertical grid edges
        for r in range(NROWS):
            if unit_at.get((r, c - 1), -1) == unit_at.get((r, c), -2):
                continue
            if all(bg(colour_at(c - eps, r + t), r + t) != bg(colour_at(c + eps, r + t), r + t) for t in along):
                d.append(f"M{f(ox + c * s)},{f(oy + r * s)} v{f(s)}")
    for p in PIECES:
        x, y = ox + p.rect.c0 * s, oy + p.rect.r0 * s
        if p.kind == "hst" and bg(p.a, p.rect.r0 + 0.5) != bg(p.b, p.rect.r0 + 0.5):
            (u1, v1), (u2, v2) = [pt for pt in TRI[p.corner] if pt in OPP[p.corner]]
            d.append(f"M{f(x + u1 * s)},{f(y + v1 * s)} L{f(x + u2 * s)},{f(y + v2 * s)}")
        elif p.kind == "qc" and bg(p.unit.bg, p.rect.r0 + 0.5):
            S = p.unit.n * s
            d.append(quarter_arc(p.corner, *corner_xy(p, x, y, S), S))
    return " ".join(d)


def quilting_svg(s=18):
    """Suggested quilting: every line is at most 2.5 cm (1 inch) from the next."""
    pad = 6
    W = NCOLS * s + 2 * pad
    X = lambda gx: f(pad + gx * s)
    Y = lambda gy: f(pad + gy * s)
    castles = lambda p: p.fabric == "C" and p.rect.r1 <= 11
    sky = region_mask("qp-sky", W, W, region_shapes(s, pad, pad, {"S"}), region_shapes(s, pad, pad, {"C"}, pick=castles))
    sea = region_mask("qp-sea", W, W, region_shapes(s, pad, pad, {"N"}))
    sail = region_mask("qp-sail", W, W, region_shapes(s, pad, pad, {"R", "W"}))
    sun = [p for p in PIECES if p.kind == "qc" and p.unit.n == 5][0]
    cx = pad + (sun.rect.c1 if sun.corner in "93" else sun.rect.c0) * s
    cy = pad + (sun.rect.r1 if sun.corner in "13" else sun.rect.r0) * s
    echoes = "".join(f'<circle class="q-plan" cx="{f(cx)}" cy="{f(cy)}" r="{f(r * s)}"/>' for r in (5.5, 6.25, 7.0, 7.75, 8.5))
    d = []
    # rings: one line in the middle of every ring of the sun, bow, stern and waves, and a gill on each herring
    for p in PIECES:
        if p.kind != "qc" or (p.unit.n == 1 and p.unit.bg != "N"):
            continue
        radii = [r for r, _ in p.unit.discs()] + [0.0]
        mids = []
        for outer, inner in zip(radii, radii[1:]):      # one line per ring, two in wide rings
            k = max(1, round(outer - inner))
            mids += [inner + (outer - inner) * (i + 1) / (k + 1) for i in range(k)]
        x, y = pad + p.rect.c0 * s, pad + p.rect.r0 * s
        for r in mids:
            d.append(quarter_arc(p.corner, *corner_xy(p, x, y, p.unit.n * s), r * s))
    # hull: the lines of the bow and stern run on along the middle of each plank
    hull = [p for p in PIECES if p.kind == "qc" and p.unit.n == 3]
    left = min(p.rect.c1 for p in hull)
    right = max(p.rect.c0 for p in hull)
    top = hull[0].rect.r0
    for r in (0.5, 1.5, 2.5):
        d.append(f"M{X(left)},{Y(top + r)} H{X(right)}")
    # mast, yard, flagpole and rudder: one line down the middle
    for p in PIECES:
        if p.kind == "solid" and p.fabric == "B" and p.rect.r0 < 11 or (p.kind == "solid" and p.fabric == "B" and p.rect.w == 1):
            if max(p.rect.w, p.rect.h) < 2:
                continue
            if p.rect.w >= p.rect.h:
                d.append(f"M{X(p.rect.c0)},{Y(p.rect.r0 + p.rect.h / 2)} H{X(p.rect.c1)}")
            else:
                d.append(f"M{X(p.rect.c0 + p.rect.w / 2)},{Y(p.rect.r0)} V{Y(p.rect.r1)}")
    # flag: in the ditch between its white and red halves
    for r in range(1, NROWS):
        for c in range(NCOLS):
            if {colour_at(c + 0.5, r - 0.05), colour_at(c + 0.5, r + 0.05)} == {"W", "R"}:
                d.append(f"M{X(c)},{Y(r)} h{f(s)}")
    # teal band: one line along the middle
    band = [p for p in PIECES if p.kind == "solid" and p.fabric == "T"]
    if band:
        mid = band[0].rect.r0 + 0.5
        d.append(f"M{X(0)},{Y(mid)} H{X(NCOLS)}")
    # herring: a spine from the tip of the tail to the head
    for p in PIECES:
        if p.kind == "qc" and p.unit.bg == "N" and p.corner == "1":
            hx, hy = p.rect.c0, p.rect.r1
            d.append(f"M{X(hx - 1)},{Y(hy)} H{X(hx)}")
    # sail: vertical lines in the ditch of every stripe and down its middle
    stripes = [p for p in PIECES if p.kind == "solid" and p.fabric in "RW" and p.rect.h >= 3]
    c0 = min(p.rect.c0 for p in stripes) - 1
    c1 = max(p.rect.c1 for p in stripes) + 1
    r0 = min(p.rect.r0 for p in stripes)
    r1 = max(p.rect.r1 for p in stripes) + 1
    sail_lines = " ".join(f"M{X(c0 + 0.5 + k * 0.5)},{Y(r0)} V{Y(r1)}" for k in range(int((c1 - c0 - 1) * 2) + 1))
    body = (f'<defs>{sky}{sea}{sail}</defs>'
            f'<g opacity=".88">{whole(s, pad, pad)}</g>'
            f'<g mask="url(#qp-sky)"><path class="q-plan" d="{hlines(pad, pad, NCOLS * s, NROWS * s, s * 0.5)}"/>{echoes}</g>'
            f'<g mask="url(#qp-sea)"><path class="q-plan" d="{wave_lines(pad, pad, NCOLS * s, NROWS * s, s * 0.34, s * 0.07, s * 1.2)}"/></g>'
            f'<g mask="url(#qp-sail)"><path class="q-plan" d="{sail_lines}"/></g>'
            f'<path class="q-plan" d="{" ".join(d)}"/>'
            f'<path class="q-plan q-ditch" d="{ditch_path(s, pad, pad)}"/>'
            f'<rect class="outline" x="{pad}" y="{pad}" width="{NCOLS * s}" height="{NROWS * s}"/>')
    return svg_wrap(body, W, W, cls="dia", title="Quilting plan")


# ---------------------------------------------------------------- binding
def binding_join_svg():
    """Joining the binding strips: sew across the corner, trim, press."""
    w, P = 30, 236
    out, caps = [], []
    y = 18
    x = 30                                   # panel 1: right sides together, sew across
    out.append(f'<rect class="fN" x="{x}" y="{y + 44}" width="150" height="{w}"/>')
    out.append(f'<rect class="fN" x="{x + 120}" y="{y}" width="{w}" height="118"/><rect class="wrongside" x="{x + 120}" y="{y}" width="{w}" height="118"/>')
    out.append(f'<path class="stitch" d="M{x + 120},{y + 44} L{x + 150},{y + 44 + w}"/>')
    caps.append((x + 85, "1  Sew across, right sides together"))
    x += P                                   # panel 2: trimmed and pressed open
    out.append(f'<rect class="fN" x="{x - 10}" y="{y + 44}" width="190" height="{w}"/>')
    out.append(f'<path class="pen" d="M{x + 70},{y + 44 + w} L{x + 100},{y + 44}"/>')
    out.append(f'<text class="dimtxt" x="{x + 85}" y="{y + 44 + w + 20}">seam pressed open</text>')
    caps.append((x + 85, "2  Trim, press the seam open"))
    x += P                                   # panel 3: pressed in half
    out.append(f'<rect class="fN" x="{x - 10}" y="{y + 52}" width="190" height="{w / 2}"/>')
    out.append(f'<text class="dimtxt" x="{x + 85}" y="{y + 44}">fold</text><text class="dimtxt" x="{x + 85}" y="{y + 52 + w / 2 + 18}">raw edges</text>')
    caps.append((x + 85, "3  Press in half lengthwise"))
    for cx, t in caps:
        out.append(f'<text class="cap" x="{f(cx)}" y="{y + 150}">{t}</text>')
    return svg_wrap("".join(out), x + 200, y + 162, cls="dia", title="Joining the binding strips")


def binding_corner_svg():
    """Mitring a binding corner, in three steps (top right corner shown)."""
    w, sa, P = 22, 6, 236
    out, caps = [], []
    Y = 50                                   # the top edge of the quilt
    for n in range(3):
        px = 20 + n * P
        left, X = px + 20, px + 150          # the quilt, and its corner
        out.append(f'<rect class="stripbg" x="{left}" y="{Y}" width="{X - left}" height="120"/>')
        if n == 0:
            out.append(f'<rect class="fN" x="{left}" y="{Y}" width="{X - left + 34}" height="{w}"/>')
            out.append(f'<path class="stitch" d="M{left},{Y + sa} H{X - sa}"/><circle class="pin" cx="{X - sa}" cy="{Y + sa}" r="3"/>')
            caps.append((px + 95, "1  Stop one seam allowance short"))
        elif n == 1:
            out.append(f'<polygon class="fN" points="{left},{Y} {X},{Y} {X - w},{Y + w} {left},{Y + w}"/>')
            out.append(f'<polygon class="fN" points="{X - w},{Y + w} {X},{Y} {X},{Y - 40} {X - w},{Y - 40}"/>')
            out.append(f'<path class="edge" d="M{X - w},{Y + w} L{X},{Y}"/>')
            out.append(f'<path class="stitch" d="M{left},{Y + sa} H{X - sa}"/>')
            caps.append((px + 95, "2  Fold the strip up at 45°"))
        else:
            out.append(f'<rect class="fN" x="{left}" y="{Y}" width="{X - w - left}" height="{w}"/>')
            out.append(f'<rect class="fN" x="{X - w}" y="{Y}" width="{w}" height="120"/>')
            out.append(f'<path class="edge" d="M{X - w},{Y} H{X}"/>')
            out.append(f'<path class="stitch" d="M{left},{Y + sa} H{X - sa} M{X - sa},{Y} V{Y + 120}"/>')
            caps.append((px + 95, "3  Fold it down, sew from the edge"))
    for cx, t in caps:
        out.append(f'<text class="cap" x="{f(cx)}" y="{Y + 145}">{t}</text>')
    return svg_wrap("".join(out), 20 + 3 * P, Y + 158, cls="dia", title="Mitring the binding at a corner")


# --------------------------------------------------------------- colouring
def colouring_svg(s=26):
    """Line drawing of every piece, to try other colours."""
    pad = 8
    W = NCOLS * s + 2 * pad
    body = (f'<rect x="0" y="0" width="{f(W)}" height="{f(W)}" fill="#fff"/>'
            f'<g class="colour-me">{whole(s, pad, pad)}</g>'
            f'<rect x="{pad}" y="{pad}" width="{NCOLS * s}" height="{NROWS * s}" fill="none" stroke="#222" stroke-width="1.6"/>')
    return svg_wrap(body, W, W, cls="dia colouring", title="Colouring sheet")

