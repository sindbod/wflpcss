"""All figures of the pattern, as inline SVG strings."""
from __future__ import annotations

import math

from plan import (BAND_TREE, BLOCK_TREES, BLOCKS, FRAME, FRAME_LEAVES, GRID, NCOLS, NROWS, PLANS, SYSTEMS,
                  WINDOW, WINDOW_TREE, all_leaves, match_points)
from quilt import H, V, Leaf, Node, Rect, leaves
from svg import DTRI, TRI, cell_shapes, draw_exploded, draw_flat, explode, f, label_text, svg_wrap


def poly(pts, x, y, s):
    return " ".join(f"{f(x + u * s)},{f(y + v * s)}" for u, v in pts)


def in_window(lf):
    return WINDOW.contains(lf.rect)


def region_shapes(s, ox, oy, fabric, where):
    """Clip shapes for fabric 'L' or 'D' in 'window' or 'outer' parts of the quilt."""
    out = []
    for lf in all_leaves():
        inside = in_window(lf)
        if (where == "window") != inside:
            continue
        x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
        if lf.kind == fabric:
            out.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
        elif lf.kind == "HST":
            pts = TRI[lf.corner] if fabric == "L" else DTRI[lf.corner]
            out.append(f'<polygon points="{poly(pts, x, y, s)}"/>')
    return "".join(out)


def whole_quilt(s, ox=0.0, oy=0.0, labels=False, seams=False):
    parts = []
    for lf in all_leaves():
        x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
        parts.append(cell_shapes(lf.kind, lf.corner, x, y, lf.rect.w, lf.rect.h, s))
    if seams:
        for lf in all_leaves():
            x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
            parts.append(f'<rect class="seam" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
    if labels:
        for lf in all_leaves():
            x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
            parts.append(label_text(lf, x, y, lf.rect.w, lf.rect.h, s))
    return "".join(parts)


def wave_lines(x0, y0, w, h, gap, amp, wl):
    d = []
    y = y0 + gap / 2
    n = int(math.ceil(w / wl)) * 2 + 2
    while y < y0 + h:
        seg = f"M{f(x0 - wl)},{f(y)} q{f(wl / 4)},{f(-amp)} {f(wl / 2)},0" + f" t{f(wl / 2)},0" * n
        d.append(seg)
        y += gap
    return " ".join(d)


def diag_lines(x0, y0, w, h, gap, slope=1):
    """Lines at 45 degrees. slope=1 runs top-left to bottom-right."""
    d = []
    step = gap * math.sqrt(2)
    t = -h
    while t < w + h:
        if slope > 0:
            d.append(f"M{f(x0 + t)},{f(y0)} l{f(h)},{f(h)}")
        else:
            d.append(f"M{f(x0 + t)},{f(y0)} l{f(-h)},{f(h)}")
        t += step
    return " ".join(d)


def hlines(x0, y0, w, h, gap):
    d = []
    y = y0 + gap / 2
    while y < y0 + h:
        d.append(f"M{f(x0)},{f(y)} h{f(w)}")
        y += gap
    return " ".join(d)


def quilting_paths(s, ox, oy, uid, cls_l, cls_d):
    """Suggested quilting: wind lines in the night, 45-degree lines in the ibex,
    straight horizontal lines in the light band and frame."""
    W, Hh = NCOLS * s, NROWS * s
    defs = (f'<clipPath id="{uid}-wd">{region_shapes(s, ox, oy, "D", "window")}</clipPath>'
            f'<clipPath id="{uid}-wl">{region_shapes(s, ox, oy, "L", "window")}</clipPath>'
            f'<clipPath id="{uid}-ol">{region_shapes(s, ox, oy, "L", "outer")}</clipPath>')
    wx, wy = ox + WINDOW.c0 * s, oy + WINDOW.r0 * s
    ww, wh = WINDOW.w * s, WINDOW.h * s
    body = (f'<g clip-path="url(#{uid}-wd)"><path class="{cls_d}" d="{wave_lines(wx, wy, ww, wh, s * 0.34, s * 0.07, s * 1.2)}"/></g>'
            f'<g clip-path="url(#{uid}-wl)"><path class="{cls_l}" d="{diag_lines(wx, wy, ww, wh, s * 0.25, 1)}"/></g>'
            f'<g clip-path="url(#{uid}-ol)"><path class="{cls_l}" d="{hlines(ox, oy, W, Hh, s * 0.5)}"/></g>')
    return defs, body


# --------------------------------------------------------------- hero image
def hero_svg(s=26):
    uid = "hero"
    m = s * 0.22  # binding
    pad = s * 0.6
    W = NCOLS * s + 2 * (m + pad)
    ox = oy = m + pad
    qdefs, qbody = quilting_paths(s, ox, oy, uid, "q-onL", "q-onD")
    defs = (qdefs +
            f'<filter id="{uid}-mottle" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="0.018 0.03" numOctaves="4" seed="17"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.25 -0.52"/></filter>'
            f'<filter id="{uid}-grain" x="0" y="0" width="100%" height="100%">'
            f'<feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="3"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 -0.42"/></filter>'
            f'<filter id="{uid}-soft" x="-10%" y="-10%" width="120%" height="125%">'
            f'<feGaussianBlur stdDeviation="{f(s * 0.35)}"/></filter>')
    q0x, q0y, qw = ox - m, oy - m, NCOLS * s + 2 * m
    body = (f'<rect x="{f(q0x + s * 0.15)}" y="{f(q0y + s * 0.35)}" width="{f(qw)}" height="{f(qw)}" '
            f'class="shadow" filter="url(#{uid}-soft)"/>'
            f'<rect class="fD" x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}"/>'
            f'{whole_quilt(s, ox, oy)}{qbody}'
            f'<rect x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}" filter="url(#{uid}-mottle)" opacity=".2"/>'
            f'<rect x="{f(q0x)}" y="{f(q0y)}" width="{f(qw)}" height="{f(qw)}" filter="url(#{uid}-grain)" opacity=".22"/>')
    return svg_wrap(body, W, W, cls="hero-svg",
                    title="Steinbock quilt: a light ibex with a ridged horn on a dark night window, under a light band with four dark stars",
                    extra_defs=defs)


# ------------------------------------------------------------ layout chart
def chart_svg(s=30):
    left = 84
    top = 10
    W = left + NCOLS * s + 12
    Hh = top + NROWS * s + 12
    ox, oy = left, top
    body = [whole_quilt(s, ox, oy, labels=True, seams=True)]
    # section brackets
    marks = [("Band", 0, 4)]
    for i, ch in enumerate(WINDOW_TREE.children, 1):
        marks.append((str(i), ch.rect.r0, ch.rect.r1))
    marks.append(("L8", 19, 20))
    for name, r0, r1 in marks:
        y0, y1 = oy + r0 * s + 3, oy + r1 * s - 3
        body.append(f'<path class="bracket" d="M{left - 8},{f(y0)} h-6 V{f(y1)} h6"/>')
        body.append(f'<text class="mark end" x="{left - 20}" y="{f((y0 + y1) / 2)}">{name}</text>')
    body.append(f'<rect class="outline" x="{ox}" y="{oy}" width="{NCOLS * s}" height="{NROWS * s}"/>')
    return svg_wrap("".join(body), W, Hh, cls="dia chart",
                    title="Layout chart of the whole quilt with every piece code")


# --------------------------------------------------- window map (step 4)
def window_map_svg(s=24):
    left = 44
    W = left + WINDOW.w * s + 8
    Hh = WINDOW.h * s + 8
    ox, oy = left - WINDOW.c0 * s, 4 - WINDOW.r0 * s
    parts = []
    for lf in all_leaves():
        if not in_window(lf):
            continue
        x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
        parts.append(cell_shapes(lf.kind, lf.corner, x, y, lf.rect.w, lf.rect.h, s))
    for lf in all_leaves():
        if in_window(lf):
            x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
            parts.append(f'<rect class="seam thin" x="{f(x)}" y="{f(y)}" width="{f(lf.rect.w * s)}" height="{f(lf.rect.h * s)}"/>')
    for i, ch in enumerate(WINDOW_TREE.children, 1):
        y0 = oy + ch.rect.r0 * s
        y1 = oy + ch.rect.r1 * s
        parts.append(f'<rect class="secline" x="{left}" y="{f(y0)}" width="{WINDOW.w * s}" height="{f(y1 - y0)}"/>')
        parts.append(f'<text class="mark" x="{left - 14}" y="{f((y0 + y1) / 2)}">{i}</text>')
    return svg_wrap("".join(parts), W, Hh, cls="dia map", title="The night window divided into its 11 sections")


def window_thumb_svg(i, s=6):
    node = WINDOW_TREE.children[i - 1]
    ox, oy = -WINDOW.c0 * s, -WINDOW.r0 * s
    dim, hi = [], []
    for lf in all_leaves():
        if not in_window(lf):
            continue
        x, y = ox + lf.rect.c0 * s, oy + lf.rect.r0 * s
        (hi if node.rect.contains(lf.rect) else dim).append(cell_shapes(lf.kind, lf.corner, x, y, lf.rect.w, lf.rect.h, s))
    r = node.rect
    body = (f'<g opacity=".28">{"".join(dim)}</g>{"".join(hi)}'
            f'<rect class="thumbsel" x="{f(ox + r.c0 * s)}" y="{f(oy + r.r0 * s)}" width="{f(r.w * s)}" height="{f(r.h * s)}"/>')
    return svg_wrap(body, WINDOW.w * s, WINDOW.h * s, cls="thumb", title=f"Position of section {i} in the window")


# ------------------------------------------------------- exploded figures
def exploded_svg(tree, s, gap=8, title=None, expand_blocks=False):
    body, w, h = draw_exploded(tree, s, gap=gap, block_trees=BLOCK_TREES, expand_blocks=expand_blocks)
    return svg_wrap(body, w, h, cls="dia exploded", title=title)


def section_pins(i):
    """Seams where an outline continues into the section above / below."""
    node = WINDOW_TREE.children[i - 1]
    r = node.rect
    top = match_points(r.r0, r.c0, r.c1) if i > 1 else []
    bottom = match_points(r.r1, r.c0, r.c1) if i < len(WINDOW_TREE.children) else []
    return top, bottom


def section_svg(i, s=40, gap=7, pad=2):
    node = WINDOW_TREE.children[i - 1]
    body, w, h = draw_exploded(node, s, gap=gap, block_trees=BLOCK_TREES, expand_blocks=False, pad=pad)
    items, _, _ = explode(node, s, gap, BLOCK_TREES, False)
    top, bottom = section_pins(i)
    mg = 13

    def seam_x(gx, row_attr, row):
        right = left = None
        for lf, x, y, tag in items:
            if tag not in (None, "frame") or getattr(lf.rect, row_attr) != row:
                continue
            if lf.rect.c1 == gx:
                right = x + lf.rect.w * s
            if lf.rect.c0 == gx:
                left = x
        return pad + (right + left) / 2

    marks = []
    for gx in top:
        x = seam_x(gx, "r0", node.rect.r0)
        marks.append(f'<polygon class="pin" points="{f(x - 5)},{f(mg - 9)} {f(x + 5)},{f(mg - 9)} {f(x)},{f(mg - 2)}"/>')
    for gx in bottom:
        x = seam_x(gx, "r1", node.rect.r1)
        y = mg + h
        marks.append(f'<polygon class="pin" points="{f(x - 5)},{f(y + 9)} {f(x + 5)},{f(y + 9)} {f(x)},{f(y + 2)}"/>')
    inner = f'<g transform="translate(0 {mg})">{body}</g>' + "".join(marks)
    return svg_wrap(inner, w, h + 2 * mg, cls="dia exploded", title=f"Section {i}, exploded, with pin marks")


def band_svg(s=42):
    return exploded_svg(BAND_TREE, s, gap=10, title="Sky band, exploded")


def block_svg(name, s=40):
    return exploded_svg(BLOCK_TREES[name], s, gap=7, title=f"{name} block, exploded")


def block_flat_svg(name, s=40):
    t = BLOCK_TREES[name]
    body = draw_flat(t, s)
    return svg_wrap(body, t.rect.w * s, t.rect.h * s, cls="dia", title=f"{name} block, finished")


# --------------------------------------------------- final assembly (step 5)
def assembly_svg(s=16):
    g1, g2, g3 = 10, 16, 22
    band_h = 4 * s
    win_w, win_h = WINDOW.w * s, WINDOW.h * s
    W = NCOLS * s + 2 * g2
    Hh = band_h + g3 + win_h + g1 + s
    parts = []
    # band
    bx = (W - NCOLS * s) / 2
    for lf in leaves(BAND_TREE):
        if lf.kind == "BLOCK":
            for l2 in leaves(BLOCK_TREES[lf.block]):
                parts.append(cell_shapes(l2.kind, l2.corner, bx + l2.rect.c0 * s, l2.rect.r0 * s, l2.rect.w, l2.rect.h, s))
        else:
            parts.append(cell_shapes(lf.kind, lf.corner, bx + lf.rect.c0 * s, lf.rect.r0 * s, lf.rect.w, lf.rect.h, s))
    parts.append(f'<rect class="edge" x="{f(bx)}" y="0" width="{NCOLS * s}" height="{band_h}"/>')
    y0 = band_h + g3
    # left frame
    parts.append(f'<rect class="fL" x="0" y="{f(y0)}" width="{s}" height="{f(win_h + g1 + s)}"/>')
    parts.append(f'<rect class="edge" x="0" y="{f(y0)}" width="{s}" height="{f(win_h + g1 + s)}"/>')
    # window
    wx = s + g2
    for lf in leaves(WINDOW_TREE):
        if lf.kind == "BLOCK":
            for l2 in leaves(BLOCK_TREES[lf.block]):
                parts.append(cell_shapes(l2.kind, l2.corner, wx + (l2.rect.c0 - 1) * s, y0 + (l2.rect.r0 - 4) * s, l2.rect.w, l2.rect.h, s))
        else:
            parts.append(cell_shapes(lf.kind, lf.corner, wx + (lf.rect.c0 - 1) * s, y0 + (lf.rect.r0 - 4) * s, lf.rect.w, lf.rect.h, s))
    parts.append(f'<rect class="edge" x="{f(wx)}" y="{f(y0)}" width="{win_w}" height="{win_h}"/>')
    # bottom frame
    by = y0 + win_h + g1
    parts.append(f'<rect class="fL" x="{f(wx)}" y="{f(by)}" width="{win_w}" height="{s}"/>')
    parts.append(f'<rect class="edge" x="{f(wx)}" y="{f(by)}" width="{win_w}" height="{s}"/>')
    # right frame
    rx = wx + win_w + g2
    parts.append(f'<rect class="fL" x="{f(rx)}" y="{f(y0)}" width="{s}" height="{f(win_h + g1 + s)}"/>')
    parts.append(f'<rect class="edge" x="{f(rx)}" y="{f(y0)}" width="{s}" height="{f(win_h + g1 + s)}"/>')
    # labels
    lab = []
    lab.append(f'<text class="lbL" x="{f(s / 2)}" y="{f(y0 + (win_h + g1 + s) / 2)}" font-size="12" transform="rotate(-90 {f(s / 2)} {f(y0 + (win_h + g1 + s) / 2)})">L7</text>')
    lab.append(f'<text class="lbL" x="{f(rx + s / 2)}" y="{f(y0 + (win_h + g1 + s) / 2)}" font-size="12" transform="rotate(-90 {f(rx + s / 2)} {f(y0 + (win_h + g1 + s) / 2)})">L7</text>')
    lab.append(f'<text class="lbL" x="{f(wx + win_w / 2)}" y="{f(by + s / 2)}" font-size="12">L8</text>')
    lab.append(f'<text class="callout" x="{f(wx + win_w / 2)}" y="{f(y0 + win_h * 0.06)}">1</text>')
    return svg_wrap("".join(parts) + "".join(lab), W, Hh, cls="dia assembly",
                    title="Final assembly: window, bottom strip, side strips, then the sky band")


# ------------------------------------------------------------- HST method
def hst_method_svg(sys_key):
    sy = SYSTEMS[sys_key]
    S = 120  # px for the cut square
    k = S / sy.hst_cut
    sa = sy.sa * k
    o = sa * math.sqrt(2)
    gap = 70
    y = 34
    out, cap = [], []
    # 1: light square (wrong side up) on a dark square, drawn line, two stitching lines
    x = 10
    out.append(f'<rect class="fD" x="{f(x + 7)}" y="{f(y + 7)}" width="{S}" height="{S}"/>')
    out.append(f'<rect class="fL" x="{f(x)}" y="{f(y)}" width="{S}" height="{S}"/>')
    out.append(f'<rect class="wrongside" x="{f(x)}" y="{f(y)}" width="{S}" height="{S}"/>')
    out.append(f'<path class="pen" d="M{f(x)},{f(y)} L{f(x + S)},{f(y + S)}"/>')
    out.append(f'<path class="stitch" d="M{f(x + o)},{f(y)} L{f(x + S)},{f(y + S - o)} M{f(x)},{f(y + o)} L{f(x + S - o)},{f(y + S)}"/>')
    out.append(f'<text class="dimtxt" x="{f(x + S / 2)}" y="{f(y - 12)}">{sy.fmt(sy.hst_cut)} squares</text>')
    cap.append((x + S / 2, "1  Draw, then sew"))
    # 2: cut apart on the drawn line
    x2 = x + S + gap
    d = 9
    out.append(f'<polygon class="fD" points="{f(x2 + d + 6)},{f(y - d + 6)} {f(x2 + S + d + 6)},{f(y - d + 6)} {f(x2 + S + d + 6)},{f(y + S - d + 6)}"/>')
    out.append(f'<polygon class="fL" points="{f(x2 + d)},{f(y - d)} {f(x2 + S + d)},{f(y - d)} {f(x2 + S + d)},{f(y + S - d)}"/>')
    out.append(f'<polygon class="wrongside" points="{f(x2 + d)},{f(y - d)} {f(x2 + S + d)},{f(y - d)} {f(x2 + S + d)},{f(y + S - d)}"/>')
    out.append(f'<polygon class="fD" points="{f(x2 - d + 6)},{f(y + d + 6)} {f(x2 - d + 6)},{f(y + S + d + 6)} {f(x2 + S - d + 6)},{f(y + S + d + 6)}"/>')
    out.append(f'<polygon class="fL" points="{f(x2 - d)},{f(y + d)} {f(x2 - d)},{f(y + S + d)} {f(x2 + S - d)},{f(y + S + d)}"/>')
    out.append(f'<polygon class="wrongside" points="{f(x2 - d)},{f(y + d)} {f(x2 - d)},{f(y + S + d)} {f(x2 + S - d)},{f(y + S + d)}"/>')
    out.append(f'<path class="stitch" d="M{f(x2 + d + o)},{f(y - d)} L{f(x2 + S + d)},{f(y + S - d - o)} M{f(x2 - d)},{f(y + d + o)} L{f(x2 + S - d - o)},{f(y + S + d)}"/>')
    cap.append((x2 + S / 2, "2  Cut on the line"))
    # 3: pressed open, oversized, trimming frame
    x3 = x2 + S + gap
    side = (sy.hst_cut - sy.sa * math.sqrt(2)) * k
    trim = (sy.unit + 2 * sy.sa) * k
    yy = y + (S - side) / 2
    out.append(f'<rect class="fD" x="{f(x3)}" y="{f(yy)}" width="{f(side)}" height="{f(side)}"/>')
    out.append(f'<polygon class="fL" points="{f(x3)},{f(yy)} {f(x3 + side)},{f(yy)} {f(x3 + side)},{f(yy + side)}"/>')
    off = (side - trim) / 2
    out.append(f'<rect class="trim" x="{f(x3 + off)}" y="{f(yy + off)}" width="{f(trim)}" height="{f(trim)}"/>')
    cap.append((x3 + side / 2, "3  Press, square up"))
    # 4: finished unit with dimension
    x4 = x3 + side + gap
    yy4 = y + (S - trim) / 2
    out.append(f'<rect class="fD" x="{f(x4)}" y="{f(yy4)}" width="{f(trim)}" height="{f(trim)}"/>')
    out.append(f'<polygon class="fL" points="{f(x4)},{f(yy4)} {f(x4 + trim)},{f(yy4)} {f(x4 + trim)},{f(yy4 + trim)}"/>')
    out.append(f'<path class="dim" d="M{f(x4)},{f(yy4 + trim + 12)} h{f(trim)} M{f(x4)},{f(yy4 + trim + 7)} v10 M{f(x4 + trim)},{f(yy4 + trim + 7)} v10"/>')
    out.append(f'<text class="dimtxt" x="{f(x4 + trim / 2)}" y="{f(yy4 + trim + 28)}">{sy.fmt(sy.unit + 2 * sy.sa)}</text>')
    cap.append((x4 + trim / 2, "4  Ready to use"))
    W = x4 + trim + 12
    Hh = y + S + 58
    for cx, t in cap:
        out.append(f'<text class="cap" x="{f(cx)}" y="{f(y + S + 50)}">{t}</text>')
    return svg_wrap("".join(out), W, Hh, cls="dia hstfig", title="Making half-square triangles two at a time")


# ------------------------------------------------------------ strip plans
def strip_svgs(sys_key, fab, width_px=660):
    sy = SYSTEMS[sys_key]
    k = width_px / sy.wof
    figs = []
    n = 0
    for st in PLANS[sys_key][fab]["strips"]:
        if st["cuts"][0].label == "binding":
            continue
        n += 1
        h = st["width"] * k
        parts = [f'<rect class="stripbg" x="0" y="0" width="{f(width_px)}" height="{f(h)}"/>']
        x = 0
        for c in st["cuts"]:
            w = c.b * k
            ph = c.a * k
            cls = "f" + fab
            parts.append(f'<rect class="{cls}" x="{f(x)}" y="0" width="{f(w)}" height="{f(ph)}"/>')
            parts.append(f'<rect class="cutedge" x="{f(x)}" y="0" width="{f(w)}" height="{f(ph)}"/>')
            if c.trimmed:
                parts.append(f'<rect class="waste" x="{f(x)}" y="{f(ph)}" width="{f(w)}" height="{f(h - ph)}"/>')
            if c.extra:
                xe = x + (c.b - c.extra) * k
                parts.append(f'<rect class="extra" x="{f(xe)}" y="0" width="{f(c.extra * k)}" height="{f(ph)}"/>')
            if c.label == "□":
                parts.append(f'<path class="sqdiag" d="M{f(x + 5)},{f(5)} L{f(x + w - 5)},{f(ph - 5)}"/>')
            else:
                lc = "lbL" if fab == "L" else "lbD"
                fs = 11 if w > 26 else 9
                parts.append(f'<text class="{lc}" x="{f(x + w / 2)}" y="{f(ph / 2)}" font-size="{fs}">{c.label}</text>')
            x += w
        if st["free"] > 1e-6:
            parts.append(f'<rect class="waste" x="{f(x)}" y="0" width="{f(width_px - x)}" height="{f(h)}"/>')
        svg = svg_wrap("".join(parts), width_px, h, cls="dia strip", title=f"Strip {n}")
        figs.append((n, st, svg))
    return figs


# ---------------------------------------------------------- constellation
STARS = {  # RA (h), Dec (deg), magnitude  (Wolfram StarData)
    "α": (20.3009, -12.5449, 3.58), "β": (20.3502, -14.7814, 3.05), "ψ": (20.7683, -25.2709, 4.13),
    "ω": (20.8637, -26.9191, 4.12), "24": (21.1188, -25.0059, 4.49), "ζ": (21.4445, -22.4113, 3.77),
    "δ": (21.7840, -16.1273, 2.85), "γ": (21.6682, -16.6623, 3.69), "ι": (21.3708, -16.8345, 4.28),
    "θ": (21.0991, -17.2327, 4.08), "ε": (21.6180, -19.4660, 4.51),
}
LINES = [("α", "β"), ("β", "θ"), ("θ", "ι"), ("ι", "γ"), ("γ", "δ"), ("β", "ψ"), ("ψ", "ω"),
         ("ω", "24"), ("24", "ζ"), ("ζ", "ε"), ("ε", "δ")]
NAMED = {"δ": "Deneb Algedi", "γ": "Nashira", "β": "Dabih", "α": "Algedi"}
BAND_POS = {"δ": BLOCKS["deneb"], "γ": BLOCKS["nashira"], "β": BLOCKS["dabih"], "α": BLOCKS["algedi"]}


def constellation_svg(s=24):
    W = NCOLS * s
    ra0, dec0 = 21.04, -19.7
    cosd = math.cos(math.radians(dec0))
    # sky chart: east (larger RA) to the left, north up
    def proj(ra, dec):
        return -(ra - ra0) * 15 * cosd, -(dec - dec0)
    pts = {k: proj(v[0], v[1]) for k, v in STARS.items()}
    xs = [p[0] for p in pts.values()]
    ys = [p[1] for p in pts.values()]
    span = max(xs) - min(xs)
    sc = (W - 3 * s) / span
    cx0 = 1.5 * s - min(xs) * sc
    cy0 = 40 - min(ys) * sc
    P = {k: (cx0 + x * sc, cy0 + y * sc) for k, (x, y) in pts.items()}
    sky_h = (max(ys) - min(ys)) * sc + 76
    band_y = sky_h + 22
    parts = [f'<rect class="sky" x="0" y="0" width="{f(W)}" height="{f(sky_h)}" rx="6"/>']
    for a, b in LINES:
        parts.append(f'<path class="cline" d="M{f(P[a][0])},{f(P[a][1])} L{f(P[b][0])},{f(P[b][1])}"/>')
    for k, (x, y) in P.items():
        mag = STARS[k][2]
        r = 1.6 + (4.8 - mag) * 1.9
        cls = "cstar named" if k in NAMED else "cstar"
        parts.append(f'<circle class="{cls}" cx="{f(x)}" cy="{f(y)}" r="{f(r)}"/>')
        if k in NAMED:
            tx, ty, anchor = {
                "δ": (x - 4, y - r - 9, "start"),
                "γ": (x - 2, y + r + 16, "start"),
                "β": (x + 6, y + r + 16, "end"),
                "α": (x - r - 8, y + 4, "end"),
            }[k]
            parts.append(f'<text class="cname" x="{f(tx)}" y="{f(ty)}" text-anchor="{anchor}">{k} {NAMED[k]}</text>')
        else:
            parts.append(f'<text class="cgreek" x="{f(x + r + 4)}" y="{f(y + 4)}">{k}</text>')
    # band
    parts.append(f'<g transform="translate(0 {f(band_y)})">')
    for lf in leaves(BAND_TREE):
        if lf.kind == "BLOCK":
            for l2 in leaves(BLOCK_TREES[lf.block]):
                parts.append(cell_shapes(l2.kind, l2.corner, l2.rect.c0 * s, l2.rect.r0 * s, l2.rect.w, l2.rect.h, s))
        else:
            parts.append(cell_shapes(lf.kind, lf.corner, lf.rect.c0 * s, lf.rect.r0 * s, lf.rect.w, lf.rect.h, s))
    parts.append('</g>')
    for k, rect in BAND_POS.items():
        bx = (rect.c0 + rect.c1) / 2 * s
        parts.append(f'<text class="bname" x="{f(bx)}" y="{f(band_y + 4 * s + 18)}">{k} {NAMED[k]}</text>')
    Hh = band_y + 4 * s + 26
    return svg_wrap("".join(parts), W, Hh, cls="dia constellation",
                    title="The constellation Capricornus and the four stars that the sky band shows")
