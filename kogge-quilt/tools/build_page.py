"""Build the Kogge pattern page.

    python3 tools/build_page.py                      # writes index.html (full document)
    python3 tools/build_page.py --fragment out.html  # body fragment for hosting

Everything on the page is generated from design/kogge.py, so the numbers in
the text, the cutting plans and the diagrams always agree.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

from figures import (assembly_svg, binding_corner_svg, binding_join_svg, chart_svg, colouring_svg, hero_svg,
                     hst_method_svg, map_svg, module_key_svg, qc_method_svg, qc_unit_svg, quilting_svg, section_svg,
                     strip_svgs, template_fits, template_parts, template_sheet_svg, test_square_mini, test_square_svg,
                     thumb_svg)
from modular import H, V, Leaf, leaves
from plan import (BINDING_FABRIC, FABRICS, FQ, LONG, NCOLS, NROWS, ORDER, PARENT, PIECES, PLANS, ROOT, SECTIONS, SYSTEMS,
                  TEMPLATE_NO, TEMPLATES, UNIT_NAMES, WEB_WIDTH, amount, arc_points, backing, binding_need, disc_radii, fusible_buy,
                  hst_types, qc_name, qc_types, sanity, section_pins, solid_table)
from svg import CORNER_WORDS, hst_icon, qc_icon

CM, IN = SYSTEMS["cm"], SYSTEMS["in"]
VERSION = "1.1"
VERSION_DATE = "October 2026"


# ---------------------------------------------------------------- helpers
def m(cm_txt, in_txt):
    return f'<span class="cm">{cm_txt}</span><span class="in">{in_txt}</span>'


def cut_dims(a, b):
    return m(CM.dims(CM.cut(a), CM.cut(b)), IN.dims(IN.cut(a), IN.cut(b)))


def L(x_units):
    return m(CM.fmt(x_units * CM.unit), IN.fmt(x_units * IN.unit))


def fabric_name(k):
    return FABRICS[k][0]


def fabric_lc(k):
    """Fabric name inside a sentence: lower case except proper nouns."""
    words = FABRICS[k][0].split()
    return " ".join(w if w in ("Hanse", "Baltic", "North") else w.lower() for w in words)


QC_BY_LABEL = {q["label"]: q for q in qc_types()}


def chip(lf):
    if lf.kind == "hst":
        return (f'<span class="chip ico-chip" title="{lf.label}: {fabric_lc(lf.a)} {CORNER_WORDS[lf.corner]}">'
                f'{hst_icon(lf.corner, lf.a, lf.b)}<span class="ico-lab">{lf.label}</span></span>')
    if lf.kind == "qc":
        return (f'<span class="chip ico-chip" title="{lf.label}: {qc_name(QC_BY_LABEL[lf.label])}, centred {CORNER_WORDS[lf.corner]}">'
                f'{qc_icon(lf.unit, lf.corner)}<span class="ico-lab">{lf.label}</span></span>')
    return f'<span class="chip c{lf.fabric}">{lf.label}</span>'


def unit_chip(name):
    return f'<span class="chip unit">{name}</span>'


def seq(tokens):
    return '<span class="seq">' + "".join(tokens) + "</span>"


def nested_steps(t):
    """Steps to build part t of a section: nested units first, in the order
    they are made. Returns [(unit name or None for t itself, direction, tokens, node)]."""
    lines = []

    def visit(n, top=False):
        if isinstance(n, Leaf):
            return chip(n)
        toks = [visit(c) for c in n.children]
        direction = "top to bottom" if n.orient == H else "left to right"
        name = None if top else UNIT_NAMES[id(n)].split()[-1]
        lines.append((name, direction, toks, n))
        return None if top else unit_chip(name)

    visit(t, top=True)
    return lines


def measures(node, key):
    """A size check; data-node lets tools/validate.py compare it with the simulation."""
    return f'<span class="meas" data-node="{key}">measures {cut_dims(node.rect.w, node.rect.h)}</span>'


def steps_html(sec):
    """Section steps: build every column (or row) that has more than one
    piece, then join everything left to right (or top to bottom)."""
    part = "Column" if sec.orient == V else "Row"
    final_dir = "left to right" if sec.orient == V else "top to bottom"
    no = SECTIONS.index(sec) + 1
    blocks, toks = [], []
    for k, child in enumerate(sec.children, 1):
        if isinstance(child, Leaf):
            toks.append(chip(child))
            continue
        items = []
        for name, direction, t, node in nested_steps(child):
            who = f"Unit {unit_chip(name)}" if name else f"{part} {unit_chip(str(k))}"
            items.append(f'<li><span class="lead">{who}, {direction}:</span>{seq(t)}{measures(node, f"section {no}, {UNIT_NAMES[id(node)]}")}</li>')
        blocks.append(f'<li class="grp"><ol class="sub">{"".join(items)}</ol></li>')
        toks.append(unit_chip(str(k)))
    lead = f"Join the {part.lower()}s {final_dir}:" if blocks else f"Join {final_dir}:"
    blocks.append(f'<li class="grp final"><span class="lead">{lead}</span>{seq(toks)}'
                  f'<span class="meas">and press the seams open</span></li>')
    return '<ol class="joins">' + "".join(blocks) + "</ol>"


def simple_steps(sec):
    return steps_html(sec)


def usage():
    use = defaultdict(lambda: defaultdict(int))
    for i, sec in enumerate(SECTIONS, 1):
        for lf in leaves(sec):
            use[lf.label][f"section {i}"] += 1
    return use


USE = usage()


def use_text(label):
    return ", ".join(f"{w}{' ×' + str(n) if n > 1 else ''}" for w, n in USE[label].items())


# ---------------------------------------------------------- colourways
COLOURWAYS = {
    "hanse": ("Hanse", {k: v[2] for k, v in FABRICS.items()}),
    "nordsee": ("North Sea", dict(S="#CBDCE3", U="#F2C14E", R="#B8322B", W="#F4F1EA", C="#B9874A",
                                  B="#4A3426", T="#3C7F8C", A="#A9D6D2", N="#1B2C40")),
    "bernstein": ("Amber", dict(S="#EFE2C6", U="#E39B2D", R="#A8321F", W="#FBF6EA", C="#C98A3E",
                                B="#4E2E1E", T="#2F6F66", A="#9CC8B8", N="#24314A")),
}


def lum(hexcol):
    h = hexcol.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def colourway_css():
    out = []
    for i, (key, (_, cols)) in enumerate(COLOURWAYS.items()):
        decl = " ".join(f"--f{k}: {v}; --on{k}: {'#1E2230' if lum(v) > 0.33 else '#F7F1E6'};" for k, v in cols.items())
        sel = ":root" if i == 0 else f':root[data-cw="{key}"]'
        out.append(f"{sel} {{ {decl} }}")
    fab_rules = "".join(
        f".f{k} {{ fill: var(--f{k}); stroke: var(--f{k}); stroke-width: .5px; }}"
        f".lb{k} {{ fill: var(--on{k}); }}"
        f".c{k} {{ background: var(--f{k}); color: var(--on{k}); }}"
        f".sw{k} {{ background: var(--f{k}); }}" for k in ORDER)
    return "\n".join(out) + "\n" + fab_rules


def colourway_buttons():
    out = []
    for i, (key, (name, cols)) in enumerate(COLOURWAYS.items()):
        stops = ", ".join(f"{cols[k]} {j * 100 / 5:.0f}% {(j + 1) * 100 / 5:.0f}%" for j, k in enumerate(("S", "R", "C", "T", "N")))
        out.append(f'<button type="button" class="cw" id="cw-{key}" data-cw="{key}" aria-pressed="{"true" if i == 0 else "false"}">'
                   f'<span class="sw" style="background:conic-gradient({stops})"></span>{name}</button>')
    return "".join(out)


# --------------------------------------------------------------- parts
def facts():
    n_cut = sum(p.kind == "solid" for p in PIECES)
    n_hst = sum(p.kind == "hst" for p in PIECES)
    n_qc = sum(p.kind == "qc" for p in PIECES)
    rows = [
        ("Finished size", m(f"{NCOLS * 5} × {NROWS * 5} cm", f"{NCOLS * 2} × {NROWS * 2}″")),
        ("Grid", m(f"{NCOLS} × {NROWS} units of 5 cm", f"{NCOLS} × {NROWS} units of 2″")),
        ("Pieces", f"{n_cut} cut pieces, {n_hst} triangle units, {n_qc} quarter-circle units"),
        ("Fabrics", f"{len(ORDER)}: sky and navy by the {m('metre', 'yard')}, the rest in small cuts"),
        ("Level", "Intermediate"),
        ("Techniques", "Rotary cutting, half-square triangles, fusible appliqué, straight-seam piecing"),
    ]
    return "".join(f"<div><dt>{a}</dt><dd>{b}</dd></div>" for a, b in rows)


def materials():
    rows = []
    for k in ORDER:
        name, role, _ = FABRICS[k]
        a_cm, n_cm = amount("cm", k)
        a_in, n_in = amount("in", k)
        amt = m(f"{a_cm}" + (f" <small>{FQ['cm'][2]}</small>" if a_cm.startswith("1 fat") else ""),
                f"{a_in}" + (f" <small>{FQ['in'][2]}</small>" if a_in.startswith("1 fat") else ""))
        rows.append(f'<tr><th scope="row"><span class="sw-dot sw{k}"></span>{name} <span class="code">{k}</span></th>'
                    f'<td class="num">{amt}</td><td>{role[0].upper() + role[1:]}</td></tr>')
    bc, bi = backing(CM), backing(IN)
    extra = [
        ("Backing", m(f"{bc['two']} <small>or {bc['wide']} of extra-wide backing</small>",
                      f"{bi['two']} <small>or {bi['wide']} of extra-wide backing</small>"),
         "Cut two lengths of " + m(CM.fmt(bc["piece"]), IN.fmt(bi["piece"])) + ", join them side by side and trim to "
         + m(CM.dims(bc["side"], bc["side"]), IN.dims(bi["side"], bi["side"]))),
        ("Batting", m(CM.dims(bc["side"], bc["side"]), IN.dims(bi["side"], bi["side"])), "Thin cotton keeps a wall quilt flat"),
        ("Fusible web", m(f"{fusible_buy(CM)[0]}, {CM.fmt(WEB_WIDTH['cm'])} wide", f"{fusible_buy(IN)[0]}, {IN.fmt(WEB_WIDTH['in'])} wide"),
         "Light, paper-backed, for the quarter circles"),
        ("Hanging sleeve", m("22 × 115 cm", "8½ × 46″"), "Leftover backing works"),
        ("Thread", "Grey cotton, 50 wt", "Plus thread to match each appliqué colour"),
    ]
    rows += [f'<tr><th scope="row">{a}</th><td class="num">{b}</td><td>{c}</td></tr>' for a, b, c in extra]
    return ('<table class="mat"><thead><tr><th>Material</th><th>Amount</th><th>Used for</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def piece_list(fab):
    out = []
    for r in solid_table():
        if r["fabric"] != fab:
            continue
        out.append(f'<tr><td><span class="chip c{fab}">{r["label"]}</span></td><td class="num">{cut_dims(r["a"], r["b"])}</td>'
                   f'<td class="num">{r["count"]}</td><td class="use">{use_text(r["label"])}</td></tr>')
    for t in hst_types():
        if fab in t["pair"]:
            n = math.ceil(t["count"] / 2)
            out.append(f'<tr><td><span class="chip plain">{t["label"]}</span></td><td class="num">{m(CM.dims(CM.hst_cut, CM.hst_cut), IN.dims(IN.hst_cut, IN.hst_cut))}</td>'
                       f'<td class="num">{n}</td><td class="use">squares for {t["count"]} triangle unit{"s" if t["count"] > 1 else ""} {t["label"]}</td></tr>')
    for q in qc_types():
        if q["bg"] == fab:
            out.append(f'<tr><td><span class="chip plain">{q["label"]}</span></td><td class="num">{cut_dims(q["n"], q["n"])}</td>'
                       f'<td class="num">{q["count"]}</td><td class="use">background squares, {qc_name(q).lower()}</td></tr>')
        for r_, f_ in q["discs"]:
            if f_ == fab:
                out.append(f'<tr><td><span class="chip plain">{q["label"]}</span></td>'
                           f'<td class="num">{m("R " + CM.fmt(r_ * CM.unit), "R " + IN.fmt(r_ * IN.unit))}</td>'
                           f'<td class="num">{q["count"]}</td><td class="use">template {TEMPLATE_NO[r_]}, {qc_name(q).lower()}</td></tr>')
    return ('<table class="pieces"><thead><tr><th>Code</th><th>Size</th><th>Qty</th><th>Used in</th></tr></thead>'
            f'<tbody>{"".join(out)}</tbody></table>')


KIND_WORDS = {"hst": "squares for triangles", "qcbg": "background squares", "disc": "fabric for quarter circles"}


def strip_cards(sys_key, fab):
    sy = SYSTEMS[sys_key]
    cards = []
    for n, st, svg in strip_svgs(sys_key, fab):
        groups = []
        for c in st["cuts"]:
            key = (c.kind, c.label, c.b, c.trimmed, c.a, c.extra, c.r)
            if groups and groups[-1][0] == key:
                groups[-1][1] += 1
            else:
                groups.append([key, 1])
        lines = []
        for (kind, label, b, trimmed, a, extra, r), k in groups:
            square = abs(a - b) < 1e-9
            shape = ("square" if square else "rectangle") + ("s" if k > 1 else "")
            size = sy.dims(min(a, b), max(a, b))      # as in the piece lists
            if kind == "piece":
                t = f"{k} {shape} {size} · {label}"
                if extra:
                    t += f", {sy.fmt(extra)} long on purpose: trim to fit later"
            elif kind == "qcbg":
                t = f"{k} {shape} {size} · {label} background{'s' if k > 1 else ''}"
            elif kind == "hst":
                t = f"{k} {shape} {size} · for triangle units {label}"
            else:
                t = f"{k} {shape} {size} · for template {TEMPLATE_NO[r]} ({label})"
            lines.append(f"<li>{t}</li>")
        cap = (f'<div><p>Cut a strip {sy.fmt(st["width"])} × WOF. From it cut:</p>'
               f'<ul class="cutlist">{"".join(lines)}</ul></div>')
        cards.append(f'<figure class="stripfig"><div class="stripsvg">{svg}</div><figcaption><b>{n}</b>{cap}</figcaption></figure>')
    return cards


def strip_summary(sys_key, fab):
    sy = SYSTEMS[sys_key]
    counts = {}
    for s in PLANS[sys_key][fab]["strips"]:
        kind = "binding" if s["cuts"][0].kind == "binding" else "pieces"
        counts[(s["width"], kind)] = counts.get((s["width"], kind), 0) + 1
    parts = []
    for (w, kind), n in sorted(counts.items(), key=lambda t: (t[0][1] == "binding", -t[0][0])):
        parts.append(f"{n} {'strip' if n == 1 else 'strips'} {sy.fmt(w)}" + (" for the binding" if kind == "binding" else ""))
    return ", ".join(parts)


def cutting_block(fab):
    name, role, _ = FABRICS[fab]
    a_cm = amount("cm", fab)[0]
    a_in = amount("in", fab)[0]
    cards_cm, cards_in = strip_cards("cm", fab), strip_cards("in", fab)
    fq_note = ""
    if a_cm.startswith("1 fat"):
        fq_note = f'<p class="prose small">Cutting from a fat quarter: cut the same strips along its long side instead of across the width of fabric.</p>'
    return f"""
    <article class="fabric" id="cut-{fab}">
      <div class="fabric-start">
        <header class="fabric-head"><span class="sw-dot big sw{fab}"></span><div><h3>{name} <span class="code">{fab}</span></h3><p>{m(a_cm, a_in)} · {role}</p></div></header>
        <p class="cutsum"><span class="cm">Cut {strip_summary("cm", fab)}.</span><span class="in">Cut {strip_summary("in", fab)}.</span></p>
        {fq_note}
        <div class="strips cm">{cards_cm[0]}</div>
        <div class="strips in">{cards_in[0]}</div>
      </div>
      <div class="strips cm more">{"".join(cards_cm[1:])}</div>
      <div class="strips in more">{"".join(cards_in[1:])}</div>
      <details class="plist" open><summary>Piece list for {fabric_lc(fab)}</summary><div class="tablewrap">{piece_list(fab)}</div></details>
    </article>"""


def unit_cards():
    cards = []
    for q in qc_types():
        discs = ", ".join(f"template {TEMPLATE_NO[r]} in {fabric_lc(f_)}" for r, f_ in q["discs"])
        cards.append(f"""
      <article class="card">
        <div class="card-fig">{qc_unit_svg(q)}</div>
        <h3>{q["label"]} · {qc_name(q)} <span class="kind">make {q["count"]} · {q["n"]} × {q["n"]} grid unit{"s" if q["n"] > 1 else ""}</span></h3>
        <p class="need">Background: {fabric_lc(q["bg"])} square {cut_dims(q["n"], q["n"])}. Quarter circles, largest first: {discs}. The finished unit still measures {cut_dims(q["n"], q["n"])}.</p>
      </article>""")
    return "".join(cards)


SECTION_NOTES = {
    1: "Sky, rising sun, gulls, pennant, sail and both castles. Pieced in columns.",
    2: "The hull: the two curved ends, the rudder and three long plank strips.",
    3: "Twelve wave units in a row, turned alternately.",
    4: "The teal band under the waves.",
    5: "A navy band.",
    6: "Two herring swimming with the ship.",
    7: "Two more herring and the bottom of the sea.",
}


def seam_test():
    """How much narrower section 1 comes out than section 2 with every seam a
    little too wide, sewn in software (see tools/validate.py)."""
    from validate import Sewer, simulate
    out = {}
    for key, bias in (("cm", 0.1), ("in", 1 / 32)):
        sewer = Sewer(SYSTEMS[key], seam_bias=bias)
        w1 = simulate(SECTIONS[0], sewer, {})[0]
        w2 = simulate(SECTIONS[1], sewer, {})[0]
        step = 0.1 if key == "cm" else 1 / 8
        out[key] = max(step, round(abs(w2 - w1) / step) * step)
    return out


SEAM_TEST = seam_test()


def trim_note(sec):
    """Which pieces of a section are cut long, and what to trim them to."""
    longs = [lf for lf in leaves(sec) if id(lf) in LONG]
    if not longs:
        return ""
    extra = m(CM.fmt(CM.long_extra), IN.fmt(IN.long_extra))
    names = " and ".join(", ".join(lf.label for lf in longs[:-1]) and [", ".join(lf.label for lf in longs[:-1]), longs[-1].label]
                         or [longs[-1].label])
    verb = "is" if len(longs) == 1 else "are"
    if all(LONG[id(lf)] is None for lf in longs):
        return f'<p class="pins">{names} {verb} cut {extra} longer than needed: trim the joined strip to the width of the section above.</p>'
    parts = []
    for lf in longs:
        nb = LONG[id(lf)]
        dim = "width" if PARENT[id(lf)].orient == H else "height"
        what = UNIT_NAMES.get(id(nb)) if not isinstance(nb, Leaf) else nb.label
        parts.append(f"{lf.label} to the {dim} of {what}")
    it = "it" if len(longs) == 1 else "them"
    return (f'<p class="pins">{names} {verb} cut {extra} longer than needed. Make the rest of the section first, '
            f'then trim {"; ".join(parts)} before you join {it}.</p>')


def section_cards():
    cards = []
    for i, sec in enumerate(SECTIONS, 1):
        r = sec.rect
        if isinstance(sec, Leaf):
            how = f'<ol class="joins"><li>One piece: {chip(sec)}</li></ol>'
        else:
            how = steps_html(sec)
        how += trim_note(sec)
        top, bottom = section_pins(i)
        pins = []
        if top:
            pins.append(f'{len(top)} with section {i - 1} <span class="pinkey down" aria-hidden="true"></span>')
        if bottom:
            pins.append(f'{len(bottom)} with section {i + 1} <span class="pinkey up" aria-hidden="true"></span>')
        if pins:
            how += f'<p class="pins">Pin points: {" · ".join(pins)}</p>'
        arcs = arc_points(sec)
        if arcs:
            labs = sorted({lab for _, _, lab in arcs})
            how += (f'<p class="pins">Arc ends to match: {len(arcs)}. Where a ring of {" and ".join(labs)} meets a seam '
                    f'or another ring, pin it like a seam crossing.</p>')
        cards.append(f"""
      <article class="sec" id="s{i}">
        <div class="sec-head"><span class="secno">{i}</span><div><h3>Section {i}</h3><p>{SECTION_NOTES.get(i, "")}</p></div>
          <p class="check" data-node="section {i}">Measures {cut_dims(r.w, r.h)}</p>{thumb_svg(i)}</div>
        <div class="sec-fig">{section_svg(i)}</div>
        {how}
      </article>""")
    return "".join(cards)


def tracing_list(t):
    """'8 sailcloth (Q1), 4 Baltic navy (Q2), …' for one template."""
    return ", ".join(f"{c} {fabric_lc(f_)} ({lab})" for lab, f_, c in t["uses"])


def tracing_table():
    rows = []
    for t in TEMPLATES:
        r = t["r"]
        rows.append(f'<tr><th scope="row">Template {t["no"]}</th>'
                    f'<td class="num">{m("R " + CM.fmt(r * CM.unit), "R " + IN.fmt(r * IN.unit))}</td>'
                    f'<td class="num">{t["total"]}</td><td class="use">{tracing_list(t)}</td></tr>')
    return ('<table class="mat tracing"><thead><tr><th>Template</th><th>Radius</th><th>Trace</th><th>Fabric (unit)</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def templates_block():
    out = {}
    for key in ("cm", "in"):
        sy = SYSTEMS[key]
        square = "5 × 5 cm" if key == "cm" else "2 × 2″"
        mini = "2 cm" if key == "cm" else "1″"
        small = [f'<figure class="tplfig"><div>{test_square_svg(key)}</div><figcaption>Test square: must measure {square}</figcaption></figure>']
        big = []
        for t in TEMPLATES:
            r = t["r"]
            head = f'<b>Template {t["no"]}</b> · R {sy.fmt(r * sy.unit)} · trace {t["total"]}: {tracing_list(t)}'
            if template_fits(key, r):
                small.append(f'<figure class="tplfig"><div>{template_sheet_svg(key, r)}</div><figcaption>{head}</figcaption></figure>')
                continue
            parts, keymap = template_parts(key, r)
            pieces = "".join(
                f'<figure class="tplfig tplpart"><div>{svg}</div><figcaption>{test_square_mini(key)}'
                f'<span><b>Template {t["no"]}, part {i} of {len(parts)}.</b> Check that the square measures {mini} before you cut.'
                + (f' Template {t["no"]} · R {sy.fmt(r * sy.unit)} · trace {t["total"]}: {tracing_list(t)}.' if i == 1 else "")
                + '</span></figcaption></figure>'
                for i, svg in parts)
            big.append(f'<div class="tplbig"><figure class="tplkeyfig">{keymap}<figcaption>{head}. '
                       f'Printed in {len(parts)} parts that tape together as numbered.</figcaption></figure>'
                       f'<div class="tpls">{pieces}</div></div>')
        out[key] = f'<div class="{key}"><div class="tpls">{"".join(small)}</div>{"".join(big)}</div>'
    return f"""
  <div class="prose">
    <p>Print these pages at 100 % (“actual size”, not “fit to page”) and measure the test square before you trace. Each template is a quarter circle around the corner of the finished unit. Its straight edges include the seam allowance and go on the raw edges of the background square; the dashed lines are the seam lines.</p>
    <p>Templates 4 and 5 are too big for one page and come in parts. Cut each part along its edges marked ✂, lay it over the grey strip of the next part so the cut edge sits on the dashed line and the short marks meet, and tape. Then cut the template out along its outline. If you prefer, draw these two arcs with a string compass instead: tie a pencil to a strip of card, pin the card at the corner dot and swing the pencil.</p>
  </div>
  {out["cm"]}
  {out["in"]}"""


# ------------------------------------------------------------------ CSS
CSS = r"""
:root {
  /* Layout: a pattern booklet. One reading column, diagrams on cutting-mat panels, a sticky ruler bar for units. */
  --paper: #F3F1EC;
  --sheet: #FBFAF7;
  --ink: #171B28;
  --muted: #5B6170;
  --line: #D6D3CA;
  --mat: #E5E4DB;
  --matgrid: rgba(90, 80, 60, .10);
  --accent: #9E2A20;
  --edge: rgba(23, 27, 40, .30);
  --seamline: rgba(120, 128, 142, .85);
  --pen: #C2410C;
  --shadow: rgba(12, 16, 26, .38);
  --display: "Bricolage Grotesque", "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --body: "Instrument Sans", "Helvetica Neue", Arial, system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #12141A; --sheet: #191C24; --ink: #E9E6DF; --muted: #A0A3AD; --line: #2C303B;
    --mat: #1E222B; --matgrid: rgba(220, 210, 190, .06); --accent: #F0907B; --edge: rgba(233, 230, 223, .34);
    --seamline: rgba(150, 158, 172, .9); --pen: #FB923C; --shadow: rgba(0, 0, 0, .55);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #12141A; --sheet: #191C24; --ink: #E9E6DF; --muted: #A0A3AD; --line: #2C303B;
  --mat: #1E222B; --matgrid: rgba(220, 210, 190, .06); --accent: #F0907B; --edge: rgba(233, 230, 223, .34);
  --seamline: rgba(150, 158, 172, .9); --pen: #FB923C; --shadow: rgba(0, 0, 0, .55);
  color-scheme: dark;
}
/*COLOURWAYS*/

:root[data-units="in"] .cm { display: none !important; }
:root:not([data-units="in"]) .in { display: none !important; }

* { box-sizing: border-box; }
html { scroll-padding-top: 72px; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 1.0625rem/1.62 var(--body); -webkit-font-smoothing: antialiased; }
.wrap { max-width: 1160px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 40px); }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
small { font-size: .82em; color: var(--muted); font-weight: 500; }

.bar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; background: var(--paper); border-bottom: 1px solid var(--line); }
.bar::after { content: ""; position: absolute; left: 0; right: 0; bottom: -7px; height: 6px; pointer-events: none;
  background: repeating-linear-gradient(90deg, var(--muted) 0 1px, transparent 1px 10px); opacity: .28; }
.bar-in { display: flex; align-items: center; gap: 18px; padding-block: 10px; }
.brand { font: 800 1.15rem/1 var(--display); letter-spacing: -.01em; text-decoration: none; white-space: nowrap; }
.toc { display: flex; gap: 16px; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; mask-image: linear-gradient(90deg, #000 88%, transparent); }
.toc::-webkit-scrollbar { display: none; }
.toc a { color: var(--muted); text-decoration: none; white-space: nowrap; font-size: .92rem; padding-block: 4px; }
.toc a:hover { color: var(--ink); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; padding: 3px; background: var(--sheet); flex: none; }
.seg button { font: 600 .82rem/1 var(--mono); color: var(--muted); background: none; border: 0; border-radius: 999px; padding: 7px 12px; cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }

.hero { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.08fr); gap: clamp(28px, 5vw, 72px); align-items: center; padding-block: clamp(36px, 6vw, 80px) clamp(28px, 4vw, 56px); }
.eyebrow { font: 500 .76rem/1.4 var(--mono); letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin: 0 0 14px; }
h1 { font: 800 clamp(3.4rem, 10vw, 7.2rem)/.86 var(--display); letter-spacing: -.045em; margin: 0 0 6px; font-variation-settings: "opsz" 96; }
.subtitle { font: 600 clamp(1.15rem, 2.4vw, 1.5rem)/1.25 var(--display); margin: 0 0 22px; color: var(--muted); letter-spacing: -.01em; text-wrap: balance; }
.lede { max-width: 58ch; margin: 0 0 26px; }
.facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 28px; margin: 0; padding-top: 22px; border-top: 1px solid var(--line); }
.facts dt { font: 500 .7rem/1.3 var(--mono); text-transform: uppercase; letter-spacing: .12em; color: var(--muted); }
.facts dd { margin: 4px 0 0; font-weight: 600; font-size: .98rem; line-height: 1.35; }
.hero-fig { margin: 0; }
.hero-fig .quilt { display: block; width: 100%; max-width: 560px; margin: 0 auto; }
.hero-svg { width: 100%; height: auto; display: block; }
.cws { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 14px; }
.cw { display: inline-flex; align-items: center; gap: 8px; font: 500 .86rem/1 var(--body); color: var(--ink); background: var(--sheet); border: 1px solid var(--line); border-radius: 999px; padding: 6px 12px 6px 6px; cursor: pointer; }
.cw[aria-pressed="true"] { border-color: var(--ink); box-shadow: inset 0 0 0 1px var(--ink); }
.cw .sw { width: 22px; height: 22px; border-radius: 50%; flex: none; }
.hero-fig figcaption { text-align: center; color: var(--muted); font-size: .86rem; margin-top: 10px; }

.part { padding-block: clamp(36px, 6vw, 72px); border-top: 1px solid var(--line); }
.part-head { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; margin-bottom: 26px; max-width: 70ch; }
.step { font: 500 .74rem/1 var(--mono); letter-spacing: .14em; text-transform: uppercase; color: var(--accent); }
h2 { font: 750 clamp(1.8rem, 3.6vw, 2.6rem)/1.05 var(--display); letter-spacing: -.025em; margin: 0; text-wrap: balance; }
h3 { font: 700 1.2rem/1.25 var(--display); letter-spacing: -.01em; margin: 0; text-wrap: balance; }
.prose { max-width: 68ch; }
.prose p, .prose li { margin-block: 0 .8em; }
.small { font-size: .92rem; color: var(--muted); }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: clamp(24px, 4vw, 48px); align-items: start; }
.panel { background-color: var(--mat); background-image: linear-gradient(var(--matgrid) 1px, transparent 1px), linear-gradient(90deg, var(--matgrid) 1px, transparent 1px); background-size: 24px 24px; border-radius: 12px; padding: clamp(14px, 2.6vw, 28px); overflow-x: auto; }
figure { margin: 0; }
figcaption { font-size: .88rem; color: var(--muted); }
.panel figcaption { margin-top: 12px; }
svg.dia { display: block; max-width: 100%; height: auto; margin-inline: auto; }
.note { border-left: 3px solid var(--accent); padding: 4px 0 4px 14px; color: var(--ink); margin: 18px 0; max-width: 68ch; }
.note b { font-weight: 650; }
.code { font: 600 .74rem/1 var(--mono); color: var(--muted); border: 1px solid var(--line); border-radius: 4px; padding: 2px 5px; vertical-align: 2px; }

/* svg vocabulary */
.edge { fill: none; stroke: var(--edge); stroke-width: 1; }
.seam { fill: none; stroke: var(--seamline); stroke-width: 1; }
.lb { font-family: var(--mono); font-weight: 600; text-anchor: middle; dominant-baseline: central; }
.mark { font: 600 13px var(--mono); fill: var(--muted); text-anchor: middle; dominant-baseline: central; }
.mark.end { text-anchor: end; }
.thumbsel { fill: none; stroke: var(--accent); stroke-width: 1.5; }
svg.thumb { display: block; flex: none; border-radius: 3px; }
.sqdiag { stroke: var(--seamline); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.discmark { stroke: var(--seamline); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.extra { fill: var(--paper); opacity: .5; }
.pin { fill: var(--pen); }
.pinkey { display: inline-block; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; vertical-align: 1px; margin-inline: 2px; }
.pinkey.down { border-top: 7px solid var(--pen); }
.pinkey.up { border-bottom: 7px solid var(--pen); }
p.pins { margin: 10px 0 0; font-size: .92rem; color: var(--muted); }
.wrongside { fill: #fff; opacity: .42; }
.web { fill: #FFFDF5; stroke: var(--line); }
.sa { fill: none; stroke: var(--seamline); stroke-width: 1; stroke-dasharray: 4 3; }
.bracket { fill: none; stroke: var(--muted); stroke-width: 1.2; }
.outline { fill: none; stroke: var(--ink); stroke-width: 1.5; }
.secline { fill: none; stroke: var(--paper); stroke-width: 2.5; }
.shadow { fill: var(--shadow); }
.q-light { fill: none; stroke: rgba(40, 30, 10, .16); stroke-width: .7; }
.q-dark { fill: none; stroke: rgba(255, 255, 255, .13); stroke-width: .7; }
.q-plan { fill: none; stroke: var(--pen); stroke-width: 1.1; }
.pen { stroke: var(--ink); stroke-width: 1.4; fill: none; }
.stitch { stroke: var(--pen); stroke-width: 1.4; stroke-dasharray: 4 3; fill: none; }
.trim { fill: none; stroke: var(--pen); stroke-width: 1.4; stroke-dasharray: 5 3; }
.dim { stroke: var(--muted); stroke-width: 1; fill: none; }
.dimtxt { font: 500 12px var(--mono); fill: var(--muted); text-anchor: middle; }
.cap { font: 600 12px var(--body); fill: var(--ink); text-anchor: middle; }
.arrowtxt { font: 400 22px var(--body); fill: var(--muted); text-anchor: middle; dominant-baseline: central; }
.stripbg { fill: var(--sheet); stroke: var(--line); }
.cutedge { fill: none; stroke: var(--edge); stroke-width: 1; }
.waste { fill: var(--line); opacity: .55; }
.tpl { fill: none; stroke: #111; }
.tplsa { fill: none; stroke: #111; }
.tpldot { fill: #111; }
.tpltxt { font-family: var(--body); fill: #111; }
svg.tplsvg { display: block; background: #fff; }
.tpls { display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start; margin-top: 18px; }
.tplfig { background: #fff; color: #333; padding: 10px; border-radius: 8px; border: 1px solid var(--line); max-width: 100%; overflow-x: auto; }
.tplfig figcaption { color: #555; margin-top: 6px; }
.tplpart figcaption { display: flex; align-items: center; gap: 12px; }
.tplglue { fill: #e6e6e6; }
.tplmap { fill: none; stroke: #111; }
.tplmapon { fill: #111; stroke: #111; }
.tplbig { margin-top: 26px; }
.tplkeyfig { display: flex; align-items: center; gap: 16px; margin-bottom: 4px; max-width: 70ch; }
.tplkeyfig svg { flex: none; }
.tplkeyfig figcaption { font-size: .92rem; color: var(--ink); }
svg.tplsvg.mini { flex: none; }
ol.steps2 { columns: 2 320px; column-gap: 44px; max-width: none; }
ol.steps2 li { break-inside: avoid; }
.meas { color: var(--muted); font-size: .84rem; margin-left: 4px; white-space: nowrap; }
.bindfigs { display: grid; grid-template-columns: minmax(0, 1fr); gap: 18px; margin-top: 22px; }
.colouring { background: #fff; border-radius: 4px; }
.colour-me rect, .colour-me polygon, .colour-me path { fill: #fff !important; stroke: #222; stroke-width: .7; }
.colourpanel svg { max-width: 640px; }
footer .version { margin-top: 6px; font-size: .85rem; }
table.tracing td.use { min-width: 22ch; }

/* chips */
.chip { display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-width: 2.2em; height: 1.65em; padding: 0 .45em; border-radius: 4px; font: 600 .8rem/1 var(--mono); vertical-align: middle; white-space: nowrap; box-shadow: inset 0 0 0 1px var(--edge); }
.chip.plain { background: var(--mat); color: var(--ink); }
.chip.unit { background: var(--ink); color: var(--paper); border-radius: 999px; min-width: 1.65em; padding: 0 .32em; box-shadow: none; }
.chip.ico-chip { background: var(--mat); color: var(--ink); padding: 0 .4em 0 0; }
.ico { display: block; width: 1.65em; height: 1.65em; border-radius: 3px 0 0 3px; }
.ico-lab { font: 600 .74rem/1 var(--mono); }
.seq { display: inline-flex; flex-wrap: wrap; gap: 4px; vertical-align: middle; }
ol.joins { list-style: none; padding: 0; margin: 14px 0 0; display: grid; gap: 10px; }
ol.joins li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }
ol.joins li.grp { display: block; }
ol.joins li.grp > .lead { margin-right: 8px; }
ol.joins .lead { font-weight: 500; }
ol.joins li.grp.final { padding-top: 4px; }
ol.joins li.grp.final .lead { font-weight: 600; }
ol.sub { list-style: none; padding: 8px 12px; margin: 0; display: grid; gap: 8px; background: var(--mat); border-radius: 8px; }
ol.sub li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }

.blocks { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
@media (max-width: 900px) { .blocks { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .blocks { grid-template-columns: minmax(0, 1fr); } }
.card { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: 18px; display: grid; gap: 10px; align-content: start; min-width: 0; }
.card-fig { background: var(--mat); border-radius: 8px; padding: 14px 10px; display: flex; align-items: center; justify-content: center; min-height: 150px; }
.card-fig svg { max-width: 100%; height: auto; }
.kind { display: block; font: 500 .74rem/1.4 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-top: 3px; }
.need { margin: 0; }

.secs { display: grid; gap: 16px; }
.sec { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px 18px; min-width: 0; }
.sec-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }
.sec-head > div { flex: 1; min-width: 180px; }
.sec-head p { margin: 2px 0 0; color: var(--muted); font-size: .94rem; }
.secno { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--fN); color: var(--onN); font: 700 1.05rem/1 var(--display); flex: none; }
.check { margin: 0 !important; font: 500 .82rem/1.3 var(--mono); color: var(--ink) !important; background: var(--mat); padding: 6px 10px; border-radius: 6px; }
.sec-fig { background: var(--mat); border-radius: 8px; padding: 12px; overflow-x: auto; }
.sec-fig svg { min-width: 520px; }
.chartpanel svg { min-width: 640px; }

.fabric { margin-top: 30px; }
.fabric-head { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
.fabric-head p { margin: 2px 0 0; color: var(--muted); }
.sw-dot { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 8px; vertical-align: -2px; border: 1px solid var(--edge); }
.sw-dot.big { width: 34px; height: 34px; margin: 0; flex: none; }
.cutsum { font-weight: 600; max-width: 70ch; }
.strips { display: grid; gap: 10px; background: var(--mat); border-radius: 12px; padding: clamp(12px, 2vw, 20px); overflow-x: auto; }
.fabric-start .strips { border-radius: 12px 12px 0 0; padding-bottom: 5px; }
.strips.more { border-radius: 0 0 12px 12px; padding-top: 5px; }
.strips.more:empty { display: none; }
.fabric-start .strips:has(+ .strips.more:empty), .fabric-start:has(~ .strips.more:empty) .strips { border-radius: 12px; }
.stripfig { display: grid; gap: 4px; }
.stripsvg svg { min-width: 560px; width: 100%; height: auto; display: block; }
.stripfig figcaption { font-size: .86rem; color: var(--muted); display: flex; gap: 8px; align-items: flex-start; }
.stripfig figcaption p { margin: 2px 0 0; color: var(--ink); }
ul.cutlist { margin: 2px 0 0; padding-left: 1.1em; display: grid; gap: 1px; }
.stripfig figcaption b { flex: none; display: inline-grid; vertical-align: 1px; place-items: center; min-width: 1.6em; height: 1.6em; border-radius: 50%; background: var(--ink); color: var(--paper); font: 600 .75rem/1 var(--mono); margin-right: 6px; }
details.plist { margin-top: 14px; }
details.plist summary { cursor: pointer; font-weight: 600; padding: 6px 0; }
table { border-collapse: collapse; width: 100%; font-size: .95rem; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: middle; }
thead th { font: 500 .72rem/1.3 var(--mono); text-transform: uppercase; letter-spacing: .1em; color: var(--muted); }
td.num { font-variant-numeric: tabular-nums; white-space: nowrap; }
td.use { color: var(--muted); font-size: .9rem; }
.tablewrap { overflow-x: auto; }
table.mat th[scope="row"] { font-weight: 600; white-space: nowrap; }

.conv { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin: 0; padding: 0; list-style: none; }
@media (max-width: 900px) { .conv { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .conv { grid-template-columns: minmax(0, 1fr); } }
.conv li { background: var(--sheet); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.conv b { display: block; font-family: var(--display); font-size: 1.02rem; margin-bottom: 4px; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; font-size: .88rem; color: var(--muted); margin-top: 12px; }
.legend i { display: inline-block; width: 22px; height: 0; border-top: 2px dashed var(--pen); vertical-align: middle; margin-right: 6px; }

footer { border-top: 1px solid var(--line); padding-block: 28px 48px; color: var(--muted); font-size: .9rem; }
footer p { max-width: 70ch; }

@media (max-width: 860px) {
  .hero, .cols { grid-template-columns: minmax(0, 1fr); }
  .hero-fig { order: -1; }
  .toc { display: none; }
  .bar-in { justify-content: space-between; }
}
@media (max-width: 520px) { .facts { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 640px) {
  .sec-fig svg, .stripsvg svg { min-width: 0; }
  .sec-head svg.thumb { width: 72px; height: auto; }
}
@media print {
  .bar, .cws, .seg { display: none !important; }
  body { font-size: 10pt; background: #fff; }
  .wrap { padding-inline: 0; }
  .part { break-before: page; border-top: 0; padding-block: 0 8px; }
  .hero { grid-template-columns: minmax(0, 1fr) !important; padding-block: 0; gap: 14px; }
  .hero-fig { order: 0 !important; }
  .hero-fig .quilt { max-width: 112mm; }
  .hero-fig figcaption { display: none; }
  h1 { font-size: 48pt; }
  .lede { max-width: none; margin-bottom: 14px; }
  .facts { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; gap: 10px 20px; padding-top: 12px; }
  .fabric-head, .cutsum, details.plist > summary { break-after: avoid; }
  .fabric { margin-top: 8mm; }
  .fabric-start { break-inside: avoid; }
  .blocks { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .card { padding: 12px; }
  .chartpanel svg { min-width: 0 !important; max-width: 150mm; }
  .sec, .card, .stripfig, figure, tr, .conv li, .note, .tplfig { break-inside: avoid; }
  .tplpart { break-before: page; }
  .tplpart figcaption { margin-top: 4mm; }
  .colourpanel svg { max-width: 150mm; }
  .tplkeyfig { display: none !important; }
  footer { break-before: avoid; }
  .sec-fig svg, .stripsvg svg { min-width: 0 !important; }
  .panel, .strips, .sec-fig, .card-fig { background-image: none; }
  details.plist > summary { list-style: none; }
  .tplfig { border: 0; padding: 0; overflow: visible; }
  footer { padding-block: 8px 0; font-size: 8.5pt; border-top: 0; }
}
"""

JS = r"""
(function () {
  var root = document.documentElement;
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function units(u) {
    if (u === 'in') root.setAttribute('data-units', 'in'); else root.removeAttribute('data-units');
    document.querySelectorAll('[data-units-btn]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-units-btn') === (u === 'in' ? 'in' : 'cm')));
    });
  }
  function colourway(c) {
    if (c && c !== 'hanse') root.setAttribute('data-cw', c); else root.removeAttribute('data-cw');
    document.querySelectorAll('button[data-cw]').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-cw') === (c || 'hanse')));
    });
  }
  units(get('kogge-units') || 'cm');
  colourway(get('kogge-cw') || 'hanse');
  document.addEventListener('click', function (e) {
    var u = e.target.closest('[data-units-btn]');
    if (u) { var v = u.getAttribute('data-units-btn'); units(v); set('kogge-units', v); return; }
    var c = e.target.closest('button[data-cw]');
    if (c) { var w = c.getAttribute('data-cw'); colourway(w); set('kogge-cw', w); }
  });
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800'
         '&family=Instrument+Sans:wght@400..700&family=IBM+Plex+Mono:wght@500;600&display=swap">')


def page_body():
    hst = hst_types()
    toc = [("design", "Design"), ("materials", "Materials"), ("cutting", "Cutting"), ("triangles", "Triangles"),
           ("circles", "Quarter circles"), ("sections", "Sections"), ("assembly", "Assembly"),
           ("finishing", "Finishing"), ("templates", "Templates"), ("chart", "Chart"), ("colouring", "Colouring")]
    toc_html = "".join(f'<a href="#{a}">{b}</a>' for a, b in toc)
    hst_lines = "".join(f"<li><b>{t['label']}</b>, {fabric_lc(t['pair'][0])} with {fabric_lc(t['pair'][1])}: "
                        f"make {t['count']} from {math.ceil(t['count'] / 2)} pair{'s' if math.ceil(t['count'] / 2) > 1 else ''} of squares"
                        f"{' (one spare)' if t['count'] % 2 else ''}.</li>" for t in hst)
    plain = [i for i, s in enumerate(SECTIONS, 1) if all(isinstance(c, Leaf) and c.kind == "solid" for c in leaves(s))]
    n_bind = sum(1 for st in PLANS["cm"][BINDING_FABRIC]["strips"] if st["cuts"][0].kind == "binding")
    n_bind_in = sum(1 for st in PLANS["in"][BINDING_FABRIC]["strips"] if st["cuts"][0].kind == "binding")
    top_unf = cut_dims(NCOLS, NROWS)
    return f"""
<header class="bar"><div class="wrap bar-in">
  <a class="brand" href="#top">Kogge</a>
  <nav class="toc" aria-label="Pattern sections">{toc_html}</nav>
  <div class="seg" role="group" aria-label="Measurements">
    <button type="button" id="u-cm" data-units-btn="cm" aria-pressed="true">cm</button>
    <button type="button" id="u-in" data-units-btn="in" aria-pressed="false">inch</button>
  </div>
</div></header>

<main class="wrap">
<section class="hero" id="top">
  <div>
    <p class="eyebrow">Modular patchwork · Hanseatic League · c. 1380</p>
    <h1>Kogge</h1>
    <p class="subtitle">A Hanseatic cog in squares, triangles and quarter circles</p>
    <p class="lede">The cog was the ship of the Hanseatic League, the league of merchant towns led by Lübeck that dominated trade on the Baltic and the North Sea from the 13th to the 15th century. The best-preserved cog ever found was built around 1380 and raised from the river Weser at Bremen in 1962. This quilt draws one in the modular manner of the Icelandic artist Siggi Eggertsson: every square of a grid holds one simple shape, and quarter circles turn hard pixels into a round hull, rolling waves and a rising sun.</p>
    <dl class="facts">{facts()}</dl>
  </div>
  <figure class="hero-fig">
    <div class="quilt">{hero_svg()}</div>
    <div class="cws" role="group" aria-label="Colourway">{colourway_buttons()}</div>
    <figcaption>Choose a colourway. Every diagram on this page follows it.</figcaption>
  </figure>
</section>

<section class="part" id="design">
  <div class="part-head"><span class="step">The design</span><h2>Four shapes, one grid</h2></div>
  <div class="cols">
    <div class="prose">
      <p>Each square of the {NCOLS} × {NROWS} grid holds a square of one fabric, a half-square triangle, or part of a quarter circle. Stacking smaller quarter circles on bigger ones gives the rings that bend the copper plank band round the bow and stern, curl the waves and colour the rising sun.</p>
      <p><b>The cog.</b> One mast and one square sail, castles fore and aft, and a rudder hung on the sternpost. Cogs were among the first northern ships to steer that way instead of with an oar over the side.</p>
      <p><b>The flag.</b> White over red is the flag of Lübeck, the leading city of the League. Red and white are still the colours of the old Hanseatic towns.</p>
      <p><b>The herring.</b> Salted Baltic herring, preserved with salt from Lüneburg, was one of the trades that made the Hanse rich, so a shoal swims along with the ship.</p>
    </div>
    <figure class="panel">{module_key_svg()}<figcaption>The modules. A quarter circle is a background square with a quarter disc appliquéd into one corner; rings are smaller discs stacked on top.</figcaption></figure>
  </div>
</section>

<section class="part" id="materials">
  <div class="part-head"><span class="step">Materials</span><h2>What you need</h2></div>
  <div class="tablewrap">{materials()}</div>
  <p class="note"><b>Fabric choice.</b> Solids or tone-on-tone prints keep the shapes crisp. Check that the sky, the sail cloth and the aqua read clearly apart, and that the navy is the darkest fabric.</p>
  <p class="prose"><b>Tools:</b> rotary cutter, cutting mat and a long ruler; a square ruler of {m("15 cm", "6½″")} or more for trimming the triangle units; small sharp scissors for the appliqué; an iron, a pressing cloth and an appliqué pressing sheet or baking paper; a pencil; clear tape for joining template parts; a walking foot for straight-line quilting and an open-toe foot for stitching the arcs.</p>
</section>

<section class="part" id="before">
  <div class="part-head"><span class="step">Before you begin</span><h2>How this pattern works</h2></div>
  <ul class="conv">
    <li><b>Read first</b>Read the whole pattern before you cut. Cut every fabric as its cutting plan shows and label each stack with its code as you go.</li>
    <li><b>Abbreviations</b>WOF: width of fabric, from selvage to selvage ({m("105 cm", "40″")} usable assumed). RST: right sides together. HST: half-square triangle. FQ: fat quarter ({m(FQ["cm"][2], FQ["in"][2])}).</li>
    <li><b>Prewashing</b>Optional. The fabric amounts allow for 5 % shrinkage.</li>
    <li><b>Seam allowance</b>Sew all seams right sides together. All sizes include {m("0.75 cm", "¼″")} seams. Sew six {m("6.5 cm", "2½″")} scrap squares into a row: it must be {m("31.5 cm", "12½″")} long, give or take {m("2 mm", "1/16″")}. If it is shorter your seams are too wide, if longer too narrow: adjust and sew a new row. It matters: with every seam {m("1 mm", "1/32″")} too wide, section 1 comes out {m(CM.fmt(SEAM_TEST["cm"]), IN.fmt(SEAM_TEST["in"]))} narrower than the hull below it.</li>
    <li><b>Grid</b>One grid unit is {m("5 cm", "2″")} finished. Every piece is a whole number of units, so every seam lines up with the grid.</li>
    <li><b>Piece codes</b>The letter is the fabric (S sky, U sun gold, R red, W sail cloth, C copper, B brown, T teal, A aqua, N navy), the number the size. H are triangle units, Q quarter-circle units.</li>
    <li><b>Appliqué</b>Quarter circles are fused to their background squares and stitched before any piecing. Their straight edges disappear into the seams; only the arcs are stitched.</li>
    <li><b>Pressing</b>Press triangle seams toward the darker fabric and all other seams open. Press appliqué from the back.</li>
    <li><b>Diagrams</b>All diagrams show the right side. Gaps show the order: the narrower the gap, the earlier the seam.</li>
  </ul>
</section>

<section class="part" id="cutting">
  <div class="part-head"><span class="step">Cutting</span><h2>Cut each fabric</h2>
    <p class="prose">Each diagram is one strip cut across the width of the fabric, with the pieces in cutting order. Grey areas are left over. Squares with a dashed diagonal are for triangle units; squares with an arc are fabric for quarter circles, to be backed with fusible web and cut to shape later. Strips with a pale end are cut long on purpose and trimmed to fit.</p></div>
  {"".join(cutting_block(f) for f in ORDER)}
</section>

<section class="part" id="triangles">
  <div class="part-head"><span class="step">Step 1</span><h2>Make the triangle units</h2></div>
  <figure class="panel"><div class="cm">{hst_method_svg("cm")}</div><div class="in">{hst_method_svg("in")}</div>
    <figcaption>The pale square is the wrong side of the lighter fabric. The drawn line is solid; the stitching lines are dashed.</figcaption></figure>
  <div class="cols" style="margin-top:22px">
    <ol class="prose">
      <li>Draw a diagonal on the wrong side of each lighter {m("8 cm", "3″")} square and place it right sides together on its darker partner.</li>
      <li>Sew {m("0.75 cm", "¼″")} from the line on both sides, cut on the line and press toward the darker fabric.</li>
      <li>Trim each unit to {m("6.5 × 6.5 cm", "2½ × 2½″")} with the seam running exactly corner to corner: lay the 45° line of the square ruler on the seam, trim two sides, turn the unit and trim the other two.</li>
    </ol>
    <ul class="prose">{hst_lines}</ul>
  </div>
</section>

<section class="part" id="circles">
  <div class="part-head"><span class="step">Step 2</span><h2>Make the quarter-circle units</h2>
    <p class="prose">{sum(q["count"] for q in qc_types())} units in {len(qc_types())} kinds. Every unit is a background square with one or more quarter discs fused into a corner. The discs are traced from {len(TEMPLATES)} templates at the end of the pattern; this list says how many of each to trace, and for which fabric.</p></div>
  <div class="tablewrap">{tracing_table()}</div>
  <figure class="panel"><div class="cm">{qc_method_svg("cm")}</div><div class="in">{qc_method_svg("in")}</div></figure>
  <div style="margin-top:22px">
    <ol class="prose steps2">
      <li><b>Trace.</b> Lay the fusible web paper side up over a template and trace it as many times as the list says, about {m("1 cm", "⅜″")} apart. Mark the corner dot and write the unit code beside each tracing. Quarter circles are symmetrical, so they never need reversing.</li>
      <li><b>Rough-cut.</b> Cut each tracing out about {m("5 mm", "¼″")} outside the line. On templates 3 to 5, also cut away the middle, leaving a ring of web about {m("1.5 cm", "⅝″")} wide inside the line, so the sun, bow and stern stay soft.</li>
      <li><b>Fuse.</b> Iron each tracing, paper side up, onto the wrong side of its fabric square, with its straight edges along two edges of the square. Follow the instructions of your web.</li>
      <li><b>Cut.</b> Cut along the curved line with small sharp scissors. With the paper still on, the fabric cuts like card.</li>
      <li><b>Place.</b> Peel off the paper. Lay the disc right side up in the corner of its background square, as the unit picture shows: corner dot on the corner, both straight edges on the raw edges. Fuse with a pressing cloth.</li>
      <li><b>Rings.</b> Fuse the next smaller disc into the same corner on top of it, then the next.</li>
      <li><b>Stitch.</b> Stitch along every arc about {m("2 mm", "1/16″")} inside its edge in matching thread, with an open-toe foot: a straight stitch, a narrow zigzag ({m("1.5 mm", "1/16″")} wide and long) or a blanket stitch. Zigzag and blanket stitch keep raw edges tidiest in the wash. Leave the straight edges: the seams hold them.</li>
      <li><b>Check.</b> Press from the back. Trim anything that overhangs the square; the unit still measures its cut size.</li>
    </ol>
    <p class="note"><b>New to fusible appliqué?</b> Make one herring head (Q1) from scraps first, to learn how hot and how long your web needs, and how your machine stitches round a curve.</p>
  </div>
  <div class="blocks" style="margin-top:22px">{unit_cards()}</div>
</section>

<section class="part" id="sections">
  <div class="part-head"><span class="step">Step 3</span><h2>Piece the {len(SECTIONS)} sections</h2>
    <p class="prose">The top is pieced as {len(SECTIONS)} horizontal sections. Sew each one, press the seams open and check its size before going on: if it is more than {m("5 mm", "3/16″")} off, take in or let out a few of its seams (each seam changes the width by twice as much as you move it). Turn each triangle and quarter-circle unit exactly as its icon shows.</p></div>
  <div class="cols">
    <figure class="panel">{map_svg()}<figcaption>The sections. Thin lines are the seams inside each section.</figcaption></figure>
    <div class="prose">
      <p>In each diagram the pieces are spread apart along the seams you sew. Sections with columns are sewn column by column from the top down, then the columns are joined from left to right.</p>
      <p>Icons show each unit as it sits in the quilt. For example {chip(next(p for p in PIECES if p.kind == "qc" and p.unit.n == 2))} is a wave unit with its disc in the bottom right corner.</p>
      <p class="note"><b>Long strips.</b> Pieces with “trim to fit” in the cutting plan are a little long. Measure the part they join and trim them to match before sewing.</p>
    </div>
  </div>
  <div class="secs" style="margin-top:22px">{section_cards()}</div>
</section>

<section class="part" id="assembly">
  <div class="part-head"><span class="step">Step 4</span><h2>Join the sections</h2></div>
  <div class="cols">
    <figure class="panel">{assembly_svg()}<figcaption>Join the sections from top to bottom.</figcaption></figure>
    <ol class="prose">
      <li>Join sections {plain[0] if plain else 4}{" and " + str(plain[1]) if len(plain) > 1 else ""} first: sew each pair of strips end to end and trim the band to the width of section 3.</li>
      <li>Join sections 1 to {len(SECTIONS)} from top to bottom. Pin at the ends and at every seam that meets a seam across the join, then ease in any difference between pins.</li>
      <li>The quilt top <span data-node="quilt top">measures {top_unf}</span>. Stay-stitch around the edge about {m("0.3 cm", "⅛″")} from the raw edge.</li>
    </ol>
  </div>
</section>

<section class="part" id="finishing">
  <div class="part-head"><span class="step">Steps 5 and 6</span><h2>Quilt, bind and hang</h2></div>
  <div class="cols">
    <div class="prose">
      <h3>Quilting</h3>
      <ol>
        <li>Layer backing (right side down), batting and top, and baste.</li>
        <li><b>Outlines first:</b> stitch in the ditch round the ship, the sun, the gulls, the tops of the waves and each herring. This holds the layers before the long lines.</li>
        <li><b>Sky:</b> straight horizontal lines {m("2.5 cm", "1″")} apart, carried across the castles and broken by echo arcs that ripple out from the sun.</li>
        <li><b>Sail:</b> vertical lines {m("2.5 cm", "1″")} apart: in the ditch of every stripe and down its middle.</li>
        <li><b>Hull:</b> one line along the middle of each plank, curving round the bow and stern with the rings. One line down the mast, the yard, the flagpole and the rudder.</li>
        <li><b>Sun and waves:</b> one line in the middle of every ring (two in the wide rings of the sun), and one along the teal band. Stitch the seam between the white and red halves of the flag in the ditch.</li>
        <li><b>Sea:</b> gently wavy lines {m("1.7 cm", "⅝″")} apart in the navy, stopping at the herring. Give each herring a spine from tail to head and a gill line.</li>
        <li>No two lines are more than {m("8 cm", "3″")} apart, close enough for any common batting.</li>
      </ol>
      <h3 style="margin-top:22px">Binding and sleeve</h3>
      <ol>
        <li>Trim batting and backing even with the top.</li>
        <li>Join the {n_bind} {fabric_lc(BINDING_FABRIC)} binding strips ({m(CM.fmt(CM.binding_w), IN.fmt(IN.binding_w))} × WOF) end to end with diagonal seams into one strip about {m(CM.fmt(n_bind * CM.wof), IN.fmt(n_bind_in * IN.wof))} long; you need {m(CM.fmt(binding_need(CM)), IN.fmt(binding_need(IN)))}. Press it in half lengthwise, wrong sides together.</li>
        <li>Hem the short ends of the sleeve, fold it in half lengthwise and baste it to the top edge of the back, so the binding seam catches its raw edges.</li>
        <li>Start halfway along one side and leave a {m("20 cm", "8″")} tail. Sew the binding to the front, raw edges together, with a {m("0.75 cm", "¼″")} seam, mitring each corner as shown.</li>
        <li>Join the two ends with a diagonal seam, finish sewing, turn the binding to the back and hand-stitch its fold over the seam. Hand-stitch the lower edge of the sleeve.</li>
        <li>Add a label: your name, the year, and “Kogge”.</li>
      </ol>
    </div>
    <figure class="panel">{quilting_svg()}<figcaption><span class="legend"><span><i></i>Suggested quilting lines</span></span></figcaption></figure>
  </div>
  <div class="bindfigs">
    <figure class="panel">{binding_join_svg()}<figcaption>Joining the binding strips. The pale strip is shown wrong side up.</figcaption></figure>
    <figure class="panel">{binding_corner_svg()}<figcaption>Mitring a corner. Turn the quilt and carry on down the next side.</figcaption></figure>
  </div>
</section>

<section class="part" id="templates">
  <div class="part-head"><span class="step">Templates</span><h2>Quarter-circle templates</h2></div>
  {templates_block()}
</section>

<section class="part" id="chart">
  <div class="part-head"><span class="step">Reference</span><h2>Layout chart</h2>
    <p class="prose">The whole quilt with every piece code. Brackets mark the sections. Triangle and quarter-circle units carry their codes in the section steps.</p></div>
  <figure class="panel chartpanel">{chart_svg()}</figure>
</section>

<section class="part" id="colouring">
  <div class="part-head"><span class="step">Reference</span><h2>Colour your own</h2>
    <p class="prose">Print this page and try your own colours before you buy fabric. Every line is a seam or the edge of a quarter circle.</p></div>
  <figure class="panel colourpanel">{colouring_svg()}</figure>
</section>

<footer>
  <p>Kogge is an original quilt design, inspired by the modular geometric illustrations of Siggi Eggertsson and by the Bremen cog of about 1380. Every measurement, cutting plan and diagram on this page is generated from one design grid and checked against it, and the top was also sewn in software with real seam allowances.</p>
  <p class="version">Pattern version {VERSION}, {VERSION_DATE}. Please read all instructions before you start.</p>
</footer>
</main>
"""


def build(fragment=False):
    sanity()
    css = CSS.replace("/*COLOURWAYS*/", colourway_css())
    head = "<title>Kogge Quilt Pattern</title>" + FONTS + f"<style>{css}</style>"
    body = page_body() + f"<script>{JS}</script>"
    if fragment:
        return head + body
    meta = ('<meta name="description" content="Kogge: a modular patchwork quilt pattern of a Hanseatic cog, with cutting '
            'plans, appliqué templates and step-by-step diagrams in cm and inches.">')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            + meta + head + "</head><body>" + body + "</body></html>")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--fragment":
        out = Path(args[1])
        out.write_text(build(fragment=True), encoding="utf-8")
    else:
        out = ROOT / "index.html"
        out.write_text(build(), encoding="utf-8")
    print("wrote", out, f"{out.stat().st_size / 1024:.0f} KB")
