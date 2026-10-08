"""Build the Steinbock pattern page.

    python3 tools/build_page.py            # writes index.html (full document)
    python3 tools/build_page.py --fragment out.html   # body fragment for hosting

Everything on the page is generated from design/steinbock.txt, so the
numbers in the text, the cutting plans and the diagrams always agree.
"""
from __future__ import annotations

import html
import math
import sys
from collections import defaultdict
from pathlib import Path

from figures import (assembly_svg, band_svg, block_flat_svg, block_svg, chart_svg, constellation_svg,
                     hero_svg, hst_method_svg, section_pins, section_svg, strip_svgs, window_map_svg,
                     window_thumb_svg)
from plan import (BAND_TREE, BLOCK_INFO, BLOCK_TREES, FRAME_LEAVES, GRID, HST_COUNT, NCOLS, NROWS, PLANS,
                  ROOT, SYSTEMS, WINDOW, WINDOW_TREE, all_leaves, piece_table, sanity)
from quilt import H, Leaf, leaves
from svg import CORNER_WORDS, hst_icon

CM, IN = SYSTEMS["cm"], SYSTEMS["in"]


# ------------------------------------------------------------------ helpers
def m(cm_txt, in_txt):
    return f'<span class="cm">{cm_txt}</span><span class="in">{in_txt}</span>'


def cut_dims(a, b):
    return m(CM.dims(CM.cut(a), CM.cut(b)), IN.dims(IN.cut(a), IN.cut(b)))


def fin_dims(a, b):
    return m(CM.dims(a * CM.unit, b * CM.unit), IN.dims(a * IN.unit, b * IN.unit))


def unf_dims(a, b):
    """Unfinished size of an assembled unit a x b grid units."""
    return cut_dims(a, b)


def L(cm, inch):
    return m(CM.fmt(cm), IN.fmt(inch))


def chip(lf):
    if lf.kind == "HST":
        return f'<span class="chip hst" title="Half-square triangle, {CORNER_WORDS[lf.corner]}">{hst_icon(lf.corner)}<span class="sr">HST, {CORNER_WORDS[lf.corner]}</span></span>'
    if lf.kind == "BLOCK":
        return f'<span class="chip blk">{BLOCK_INFO[lf.block]["title"]}</span>'
    return f'<span class="chip {lf.kind}">{lf.label}</span>'


def unit_chip(name):
    return f'<span class="chip unit">{name}</span>'


def seq(tokens):
    return '<span class="seq">' + "".join(tokens) + "</span>"


def join_steps(tree):
    """Generic step list for a sub-tree: nested units first, then the final join."""
    steps = []
    letters = iter("abcdefghijklmnopqrstuvwxyz")

    def visit(t, top=False):
        if isinstance(t, Leaf):
            return chip(t)
        toks = [visit(c) for c in t.children]
        direction = "top to bottom" if t.orient == H else "left to right"
        if top:
            steps.append((None, direction, toks))
            return None
        name = next(letters)
        steps.append((name, direction, toks))
        return unit_chip(name)

    visit(tree, top=True)
    return steps


def steps_html(tree):
    out = []
    for name, direction, toks in join_steps(tree):
        if name:
            out.append(f'<li>Make unit {unit_chip(name)}: join {direction} {seq(toks)}</li>')
        else:
            out.append(f'<li>Join {direction} {seq(toks)}</li>')
    return "<ol class=\"joins\">" + "".join(out) + "</ol>"


# --------------------------------------------------------------- piece use
def usage():
    use = defaultdict(lambda: defaultdict(int))
    for lf in leaves(BAND_TREE):
        if lf.kind == "BLOCK":
            for l2 in leaves(BLOCK_TREES[lf.block]):
                use[l2.label][BLOCK_INFO[lf.block]["title"]] += 1
        else:
            use[lf.label]["sky band"] += 1
    for i, ch in enumerate(WINDOW_TREE.children, 1):
        for lf in leaves(ch):
            if lf.kind == "BLOCK":
                for l2 in leaves(BLOCK_TREES[lf.block]):
                    use[l2.label][BLOCK_INFO[lf.block]["title"]] += 1
            else:
                use[lf.label][f"section {i}"] += 1
    for lf in FRAME_LEAVES.values():
        use[lf.label]["frame"] += 1
    return use


USE = usage()


def use_text(label):
    parts = []
    for where, n in USE[label].items():
        parts.append(f"{where}{' ×' + str(n) if n > 1 else ''}")
    return ", ".join(parts)


# ------------------------------------------------------------- page parts
SECTION_NOTES = [
    "Night sky above the horn: a single strip.",
    "The crown of the horn.",
    "The horn arches over. First ridge on the right.",
    "Horn tip on the left, second ridge on the right.",
    "Horn tip, third ridge and the top of the head.",
    "Back of the head, the eye and the nose.",
    "Neck and muzzle.",
    "Tail, withers, throat and beard.",
    "The body: one long L11.",
    "The belly curve.",
    "Four legs and the edelweiss.",
]

COLORWAYS = [
    ("midnight", "Midnight gold", "#D8A44A", "#1B2338"),
    ("leo", "Lion pair", "#CB9631", "#141416"),
    ("snow", "First snow", "#ECEDE7", "#3C4856"),
    ("alpenglow", "Alpenglow", "#EC9A6E", "#2A2134"),
]


def colorway_buttons():
    out = []
    for key, name, a, b in COLORWAYS:
        pressed = "true" if key == "midnight" else "false"
        out.append(f'<button type="button" class="cw" id="cw-{key}" data-cw="{key}" aria-pressed="{pressed}">'
                   f'<span class="sw" style="background:linear-gradient(135deg,{a} 0 50%,{b} 50% 100%)"></span>{name}</button>')
    return "".join(out)


def facts():
    n_cut = sum(r["count"] for r in piece_table())
    rows = [
        ("Finished size", m("100 × 100 cm", "40 × 40″")),
        ("Grid", m("20 × 20 units of 5 cm", "20 × 20 units of 2″")),
        ("Pieces", f"{n_cut} squares and rectangles, {HST_COUNT} half-square triangles"),
        ("Fabrics", "2, plus backing"),
        ("Level", "Confident beginner"),
        ("Techniques", "Rotary cutting, half-square triangles, straight-seam piecing"),
    ]
    return "".join(f"<div><dt>{a}</dt><dd>{b}</dd></div>" for a, b in rows)


def materials():
    pl, pd = PLANS["cm"], PLANS["in"]
    rows = [
        ('<span class="sw-dot fLbg"></span>Fabric L, light',
         m(pl["L"]["buy"], pd["L"]["buy"]),
         "Ibex, edelweiss, frame, sky band, half of every triangle"),
        ('<span class="sw-dot fDbg"></span>Fabric D, dark',
         m(pl["D"]["buy"], pd["D"]["buy"]),
         "Night window, star centres, half of every triangle, binding"),
        ("Backing", m("120 × 120 cm", "48 × 48″"), "Piece it if your fabric is narrower"),
        ("Batting", m("120 × 120 cm", "48 × 48″"), "Thin cotton or cotton blend keeps a wall quilt flat"),
        ("Hanging sleeve", m("22 × 95 cm", "8½ × 38″"), "Leftover backing works"),
        ("Thread", "Neutral grey cotton, 50 wt", "Plus quilting thread to match each fabric"),
    ]
    body = "".join(f"<tr><th scope=\"row\">{a}</th><td class=\"num\">{b}</td><td>{c}</td></tr>" for a, b, c in rows)
    return f'<table class="mat"><thead><tr><th>Material</th><th>Amount</th><th>Used for</th></tr></thead><tbody>{body}</tbody></table>'


def piece_list(fab):
    out = []
    for r in piece_table():
        if r["fabric"] != fab:
            continue
        out.append(f'<tr><td><span class="chip {fab}">{r["label"]}</span></td>'
                   f'<td class="num">{cut_dims(r["a"], r["b"])}</td>'
                   f'<td class="num">{r["count"]}</td><td class="use">{use_text(r["label"])}</td></tr>')
    return ('<table class="pieces"><thead><tr><th>Code</th><th>Cut size</th><th>Qty</th><th>Used in</th></tr></thead>'
            f'<tbody>{"".join(out)}</tbody></table>')


def strip_summary(sys_key, fab):
    sy = SYSTEMS[sys_key]
    strips = PLANS[sys_key][fab]["strips"]
    counts = {}
    for s in strips:
        kind = "binding" if s["cuts"][0].label == "binding" else ("hst" if s["cuts"][0].label == "□" else "pieces")
        key = (s["width"], kind)
        counts[key] = counts.get(key, 0) + 1
    parts = []
    for (w, kind), n in sorted(counts.items(), key=lambda t: (t[0][1] == "binding", -t[0][0])):
        what = {"pieces": "", "hst": " for the triangle squares", "binding": " for the binding"}[kind]
        parts.append(f"{n} {'strip' if n == 1 else 'strips'} {sy.fmt(w)} × WOF{what}")
    return ", ".join(parts)


def strip_cards(sys_key, fab):
    sy = SYSTEMS[sys_key]
    cards = []
    for n, st, svg in strip_svgs(sys_key, fab):
        if st["cuts"][0].label == "□":
            k = len(st["cuts"])
            cap = f'{sy.fmt(st["width"])} strip → {k} squares {sy.dims(sy.hst_cut, sy.hst_cut, unit=False)} for the triangles'
        else:
            groups = []
            for c in st["cuts"]:
                key = (c.label, c.b, c.trimmed, c.a, c.extra)
                if groups and groups[-1][0] == key:
                    groups[-1][1] += 1
                else:
                    groups.append([key, 1])
            names = []
            for (label, b, trimmed, a, extra), k in groups:
                t = f'{k} × {label}' if k > 1 else label
                t += f' at {sy.fmt(b)}'
                if extra:
                    t += f' ({sy.fmt(extra)} extra, trim to fit later)'
                if trimmed:
                    t += f', trimmed to {sy.fmt(a)} wide'
                names.append(t)
            cap = f'{sy.fmt(st["width"])} strip → ' + " · ".join(names)
        cards.append(f'<figure class="stripfig"><div class="stripsvg">{svg}</div><figcaption><b>{n}</b>{cap}</figcaption></figure>')
    return "".join(cards)


def cutting_block(fab, name, blurb):
    return f"""
    <article class="fabric" id="cut-{fab}">
      <header class="fabric-head"><span class="sw-dot big f{fab}bg"></span><div><h3>{name}</h3><p>{blurb}</p></div></header>
      <p class="cutsum"><span class="cm">Cut {strip_summary("cm", fab)}.</span><span class="in">Cut {strip_summary("in", fab)}.</span></p>
      <div class="strips cm">{strip_cards("cm", fab)}</div>
      <div class="strips in">{strip_cards("in", fab)}</div>
      <details class="plist" open><summary>Piece list for fabric {fab}</summary>{piece_list(fab)}</details>
    </article>"""


def block_cards():
    star = BLOCK_INFO["deneb"]
    pw = BLOCK_INFO["nashira"]
    fs = BLOCK_INFO["edelweiss"]
    t = BLOCK_TREES
    return f"""
    <div class="blocks">
      <article class="card">
        <div class="card-fig two">{block_svg("deneb", 25)}<span class="arrow" aria-hidden="true">→</span>{block_flat_svg("deneb", 19)}</div>
        <h3>Deneb Algedi <span class="kind">sawtooth star · make 1</span></h3>
        <p class="need">You need 8 triangles, 4 × <span class="chip L">L1</span>, 1 × <span class="chip D">D11</span>.</p>
        <ol>
          <li>Join the top row and the bottom row: an L1, two triangles, an L1. The two dark points of each pair meet at the centre seam.</li>
          <li>Join two triangles top to bottom for each side, then sew them to the left and right of D11.</li>
          <li>Join the three rows. The block measures {unf_dims(4, 4)}.</li>
        </ol>
      </article>
      <article class="card">
        <div class="card-fig two">{block_svg("nashira", 38)}<span class="arrow" aria-hidden="true">→</span>{block_flat_svg("nashira", 30)}</div>
        <h3>Nashira, Dabih, Algedi <span class="kind">pinwheels · make 3</span></h3>
        <p class="need">You need 4 triangles per pinwheel.</p>
        <ol>
          <li>Join the triangles in two rows of two, exactly as shown, so all three pinwheels spin the same way.</li>
          <li>Join the rows. Pin the centre so the four points meet. Each block measures {unf_dims(2, 2)}.</li>
          <li>Eight seams meet in the centre. Press the last seam open, or spin it: undo the two stitches inside the seam allowance at the centre and press the seams around in a circle, so the centre lies flat.</li>
        </ol>
      </article>
      <article class="card">
        <div class="card-fig two">{block_svg("edelweiss", 30)}<span class="arrow" aria-hidden="true">→</span>{block_flat_svg("edelweiss", 23)}</div>
        <h3>Edelweiss <span class="kind">friendship star · make 1</span></h3>
        <p class="need">You need 4 triangles, 4 × <span class="chip D">D1</span>, 1 × <span class="chip L">L1</span>.</p>
        <ol>
          <li>Join three rows of three: D1, triangle, D1 / triangle, L1, triangle / D1, triangle, D1.</li>
          <li>Join the rows. The block measures {unf_dims(3, 3)}.</li>
        </ol>
      </article>
    </div>"""


def section_cards():
    cards = []
    for i, node in enumerate(WINDOW_TREE.children, 1):
        r = node.rect
        if isinstance(node, Leaf):
            how = (f'<ol class="joins"><li>One piece: {chip(node)}. It is cut {m(CM.fmt(CM.long_extra), IN.fmt(IN.long_extra))} long: '
                   f'trim it to the width of section 2 before you join the two.</li></ol>')
        else:
            how = steps_html(node)
        top, bottom = section_pins(i)
        pins = []
        if top:
            pins.append(f'{len(top)} with section {i - 1} <span class="pinkey down" aria-hidden="true"></span>')
        if bottom:
            pins.append(f'{len(bottom)} with section {i + 1} <span class="pinkey up" aria-hidden="true"></span>')
        if pins:
            how += f'<p class="pins">Pin points: {" · ".join(pins)}</p>'
        cards.append(f"""
      <article class="sec" id="s{i}">
        <div class="sec-head"><span class="secno">{i}</span><div><h3>Section {i}</h3><p>{SECTION_NOTES[i - 1]}</p></div>
          <p class="check">Measures {unf_dims(r.w, r.h)}</p>{window_thumb_svg(i)}</div>
        <div class="sec-fig">{section_svg(i)}</div>
        {how}
      </article>""")
    return "".join(cards)


# ------------------------------------------------------------------- page
PIN_TOTAL = 0

CSS = r"""
:root {
  /* Layout: a pattern booklet. One reading column, diagrams laid on cutting-mat panels, a sticky ruler bar for units. */
  --paper: #F1F2EC;
  --sheet: #FAFAF7;
  --ink: #161B29;
  --muted: #586071;
  --line: #D3D6CC;
  --mat: #E2E6DB;
  --matgrid: rgba(80, 98, 72, .10);
  --accent: #8A6012;
  --edge: rgba(22, 27, 41, .30);
  --seamline: rgba(120, 128, 142, .85);
  --pen: #C2410C;
  --shadow: rgba(12, 16, 26, .38);
  --display: "Bricolage Grotesque", "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --body: "Instrument Sans", "Helvetica Neue", Arial, system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
  /* fabric colourway, independent of the page theme */
  --fabL: #D8A44A; --fabD: #1B2338; --onL: #1B2338; --onD: #F3E5C6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #0F131B; --sheet: #151A24; --ink: #E7E5DE; --muted: #9AA1AE; --line: #283041;
    --mat: #1A202B; --matgrid: rgba(200, 210, 190, .06); --accent: #E3B457; --edge: rgba(231, 229, 222, .34);
    --seamline: rgba(150, 158, 172, .9); --pen: #FB923C; --shadow: rgba(0, 0, 0, .55);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #0F131B; --sheet: #151A24; --ink: #E7E5DE; --muted: #9AA1AE; --line: #283041;
  --mat: #1A202B; --matgrid: rgba(200, 210, 190, .06); --accent: #E3B457; --edge: rgba(231, 229, 222, .34);
  --seamline: rgba(150, 158, 172, .9); --pen: #FB923C; --shadow: rgba(0, 0, 0, .55);
  color-scheme: dark;
}
:root[data-cw="leo"] { --fabL: #CB9631; --fabD: #141416; --onL: #141416; --onD: #F4E2BA; }
:root[data-cw="snow"] { --fabL: #ECEDE7; --fabD: #3C4856; --onL: #2B3440; --onD: #F0F1EC; }
:root[data-cw="alpenglow"] { --fabL: #EC9A6E; --fabD: #2A2134; --onL: #2A2134; --onD: #F8DECF; }

:root[data-units="in"] .cm { display: none !important; }
:root:not([data-units="in"]) .in { display: none !important; }

* { box-sizing: border-box; }
html { scroll-padding-top: 72px; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 1.0625rem/1.62 var(--body); -webkit-font-smoothing: antialiased; }
.wrap { max-width: 1160px; margin: 0 auto; padding-inline: clamp(16px, 4vw, 40px); }
a { color: inherit; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

/* ruler bar */
.bar { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20; background: var(--paper); border-bottom: 1px solid var(--line); }
.bar::after { content: ""; position: absolute; left: 0; right: 0; bottom: -7px; height: 6px; pointer-events: none;
  background: repeating-linear-gradient(90deg, var(--muted) 0 1px, transparent 1px 10px); opacity: .28;
  -webkit-mask: linear-gradient(#000, #000); }
.bar-in { display: flex; align-items: center; gap: 18px; padding-block: 10px; }
.brand { font: 800 1.15rem/1 var(--display); letter-spacing: -.01em; text-decoration: none; white-space: nowrap; }
.toc { display: flex; gap: 16px; overflow-x: auto; flex: 1; min-width: 0; scrollbar-width: none; mask-image: linear-gradient(90deg, #000 88%, transparent); }
.toc::-webkit-scrollbar { display: none; }
.toc a { color: var(--muted); text-decoration: none; white-space: nowrap; font-size: .92rem; padding-block: 4px; }
.toc a:hover { color: var(--ink); }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; padding: 3px; background: var(--sheet); flex: none; }
.seg button { font: 600 .82rem/1 var(--mono); color: var(--muted); background: none; border: 0; border-radius: 999px; padding: 7px 12px; cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }

/* hero */
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

/* sections */
.part { padding-block: clamp(36px, 6vw, 72px); border-top: 1px solid var(--line); }
.part-head { display: grid; grid-template-columns: minmax(0, 1fr); gap: 6px; margin-bottom: 26px; max-width: 70ch; }
.step { font: 500 .74rem/1 var(--mono); letter-spacing: .14em; text-transform: uppercase; color: var(--accent); }
h2 { font: 750 clamp(1.8rem, 3.6vw, 2.6rem)/1.05 var(--display); letter-spacing: -.025em; margin: 0; text-wrap: balance; }
h3 { font: 700 1.2rem/1.25 var(--display); letter-spacing: -.01em; margin: 0; text-wrap: balance; }
.prose { max-width: 68ch; }
.prose p, .prose li { margin-block: 0 .8em; }
.cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: clamp(24px, 4vw, 48px); align-items: start; }
.panel { background-color: var(--mat); background-image: linear-gradient(var(--matgrid) 1px, transparent 1px), linear-gradient(90deg, var(--matgrid) 1px, transparent 1px); background-size: 24px 24px; border-radius: 12px; padding: clamp(14px, 2.6vw, 28px); overflow-x: auto; }
.panel + .panel { margin-top: 16px; }
figure { margin: 0; }
figcaption { font-size: .88rem; color: var(--muted); }
.panel figcaption { margin-top: 12px; }
svg.dia { display: block; max-width: 100%; height: auto; margin-inline: auto; }
.note { border-left: 3px solid var(--accent); padding: 4px 0 4px 14px; color: var(--ink); margin: 18px 0; max-width: 68ch; }
.note b { font-weight: 650; }

/* svg vocabulary */
.fL { fill: var(--fabL); stroke: var(--fabL); stroke-width: .5px; }
.fD { fill: var(--fabD); stroke: var(--fabD); stroke-width: .5px; }
.hst-ico .fL, .hst-ico .fD { stroke-width: .3px; }
.edge { fill: none; stroke: var(--edge); stroke-width: 1; }
.seam { fill: none; stroke: var(--seamline); stroke-width: 1; }
.seam.thin { stroke-width: .7; }
.lbL, .lbD { font-family: var(--mono); font-weight: 600; text-anchor: middle; dominant-baseline: central; }
.lbL { fill: var(--onL); }
.lbD { fill: var(--onD); }
.blockframe { fill: none; stroke: var(--accent); stroke-width: 2; stroke-dasharray: 5 3; }
.mark { font: 600 13px var(--mono); fill: var(--muted); text-anchor: middle; dominant-baseline: central; }
.mark.end { text-anchor: end; }
.thumbsel { fill: none; stroke: var(--accent); stroke-width: 1.5; }
svg.thumb { display: block; flex: none; border-radius: 3px; }
.sqdiag { stroke: var(--seamline); stroke-width: 1; stroke-dasharray: 3 3; fill: none; }
.extra { fill: var(--paper); opacity: .5; }
.pin { fill: var(--pen); }
.pinkey { display: inline-block; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; vertical-align: 1px; margin-inline: 2px; }
.pinkey.down { border-top: 7px solid var(--pen); }
.pinkey.up { border-bottom: 7px solid var(--pen); }
p.pins { margin: 10px 0 0; font-size: .92rem; color: var(--muted); }
.wrongside { fill: #fff; opacity: .42; }
.bracket { fill: none; stroke: var(--muted); stroke-width: 1.2; }
.outline { fill: none; stroke: var(--ink); stroke-width: 1.5; }
.secline { fill: none; stroke: var(--paper); stroke-width: 2.5; }
.shadow { fill: var(--shadow); }
.q-onL { fill: none; stroke: rgba(40, 30, 10, .2); stroke-width: .7; }
.q-onD { fill: none; stroke: rgba(255, 255, 255, .13); stroke-width: .7; }
.q-plan { fill: none; stroke: var(--pen); stroke-width: 1.1; }
.callout { display: none; }
.pen { stroke: var(--ink); stroke-width: 1.4; fill: none; }
.stitch { stroke: var(--pen); stroke-width: 1.4; stroke-dasharray: 4 3; fill: none; }
.cutline { stroke: var(--ink); stroke-width: 1.2; stroke-dasharray: 2 3; fill: none; }
.trim { fill: none; stroke: var(--pen); stroke-width: 1.4; stroke-dasharray: 5 3; }
.dim { stroke: var(--muted); stroke-width: 1; fill: none; }
.dimtxt, .cap { font: 500 12px var(--mono); fill: var(--muted); text-anchor: middle; }
.cap { font: 600 12px var(--body); fill: var(--ink); }
.stripbg { fill: var(--sheet); stroke: var(--line); }
.cutedge { fill: none; stroke: var(--edge); stroke-width: 1; }
.waste { fill: var(--line); opacity: .55; }
.sky { fill: var(--fabD); }
.cline { stroke: var(--fabL); stroke-opacity: .45; stroke-width: 1.2; fill: none; }
.cstar { fill: var(--fabL); opacity: .65; }
.cstar.named { opacity: 1; }
.cname { font: 600 12px var(--body); fill: var(--onD); }
.bname { font: 600 11.5px var(--body); fill: var(--ink); text-anchor: middle; }
.cgreek { font: 400 11px var(--body); fill: var(--onD); opacity: .6; }

/* chips */
.chip { display: inline-flex; align-items: center; justify-content: center; min-width: 2.2em; height: 1.65em; padding: 0 .45em; border-radius: 4px; font: 600 .8rem/1 var(--mono); vertical-align: middle; white-space: nowrap; box-shadow: inset 0 0 0 1px var(--edge); }
.chip.L { background: var(--fabL); color: var(--onL); }
.chip.D { background: var(--fabD); color: var(--onD); }
.chip.blk { background: transparent; border: 1.5px dashed var(--accent); color: var(--ink); font-family: var(--body); box-shadow: none; }
.chip.unit { background: var(--ink); color: var(--paper); border-radius: 50%; min-width: 1.65em; padding: 0; box-shadow: none; }
.chip.hst { padding: 0; min-width: 0; height: auto; box-shadow: none; }
.hst-ico { display: block; width: 1.65em; height: 1.65em; border-radius: 3px; outline: 1px solid var(--edge); outline-offset: -1px; }
.seq { display: inline-flex; flex-wrap: wrap; gap: 4px; vertical-align: middle; }
ol.joins { list-style: none; padding: 0; margin: 14px 0 0; display: grid; gap: 10px; }
ol.joins li { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }

/* cards */
.blocks { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 18px; }
.card { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: 18px; display: grid; gap: 10px; align-content: start; min-width: 0; }
.card-fig { background: var(--mat); border-radius: 8px; padding: 16px 10px; display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; }
.card-fig svg { flex: none; }
.arrow { color: var(--muted); font-size: 1.3rem; }
.kind { display: block; font: 500 .74rem/1.4 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-top: 3px; }
.card ol { margin: 0; padding-left: 1.2em; }
.card li { margin-bottom: .45em; }
.need { margin: 0; }

.secs { display: grid; gap: 16px; }
.sec { background: var(--sheet); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px 18px; min-width: 0; }
.sec-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }
.sec-head > div { flex: 1; min-width: 180px; }
.sec-head p { margin: 2px 0 0; color: var(--muted); font-size: .94rem; }
.secno { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--fabD); color: var(--onD); font: 700 1.05rem/1 var(--display); flex: none; }
.check { margin: 0 !important; font: 500 .82rem/1.3 var(--mono); color: var(--ink) !important; background: var(--mat); padding: 6px 10px; border-radius: 6px; }
.sec-fig { background: var(--mat); border-radius: 8px; padding: 12px; overflow-x: auto; }
.sec-fig svg { min-width: 520px; }
.chartpanel svg { min-width: 640px; }

/* cutting */
.fabric { margin-top: 30px; }
.fabric-head { display: flex; gap: 14px; align-items: center; margin-bottom: 10px; }
.fabric-head p { margin: 2px 0 0; color: var(--muted); }
.sw-dot { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 8px; vertical-align: -2px; border: 1px solid var(--edge); }
.sw-dot.big { width: 34px; height: 34px; margin: 0; flex: none; }
.fLbg { background: var(--fabL); }
.fDbg { background: var(--fabD); }
.cutsum { font-weight: 600; max-width: 70ch; }
.strips { display: grid; gap: 10px; background: var(--mat); border-radius: 12px; padding: clamp(12px, 2vw, 20px); overflow-x: auto; }
.stripfig { display: grid; gap: 4px; }
.stripsvg svg { min-width: 560px; width: 100%; height: auto; display: block; }
.stripfig figcaption { font-size: .86rem; color: var(--muted); }
.stripfig figcaption b { display: inline-grid; vertical-align: 1px; place-items: center; min-width: 1.6em; height: 1.6em; border-radius: 50%; background: var(--ink); color: var(--paper); font: 600 .75rem/1 var(--mono); margin-right: 6px; }
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
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend i { display: inline-block; width: 22px; height: 0; border-top: 2px dashed var(--pen); }
.legend i.solid { border-top-style: solid; border-color: var(--ink); }

footer { border-top: 1px solid var(--line); padding-block: 28px 48px; color: var(--muted); font-size: .9rem; }
footer p { max-width: 70ch; }

@media (max-width: 860px) {
  .hero, .cols { grid-template-columns: minmax(0, 1fr); }
  .hero-fig { order: -1; }
  .toc { display: none; }
  .bar-in { justify-content: space-between; }
}
@media (max-width: 520px) {
  .facts { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 640px) {
  .sec-fig svg, .stripsvg svg { min-width: 0; }
  .sec-head svg.thumb { width: 72px; height: auto; }
}
@media (prefers-reduced-motion: no-preference) {
  .hero-svg { transition: filter .3s; }
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
  #cut-D { break-before: page; }
  .blocks { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .card { padding: 12px; }
  .card-fig svg { max-width: 100%; height: auto; flex: 0 1 auto; }
  .chartpanel svg { min-width: 0 !important; }
  .sec, .card, .stripfig, figure, tr, .conv li, .note { break-inside: avoid; }
  .sec-fig svg, .stripsvg svg { min-width: 0 !important; }
  .panel, .strips, .sec-fig, .card-fig { background-image: none; }
  details.plist > summary { list-style: none; }
  .chartpanel svg { max-width: 150mm; }
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
  function colorway(c) {
    if (c && c !== 'midnight') root.setAttribute('data-cw', c); else root.removeAttribute('data-cw');
    document.querySelectorAll('[data-cw]').forEach(function (b) {
      if (b === root) return;
      b.setAttribute('aria-pressed', String(b.getAttribute('data-cw') === (c || 'midnight')));
    });
  }
  units(get('steinbock-units') || 'cm');
  colorway(get('steinbock-cw') || 'midnight');
  document.addEventListener('click', function (e) {
    var u = e.target.closest('[data-units-btn]');
    if (u) { var v = u.getAttribute('data-units-btn'); units(v); set('steinbock-units', v); return; }
    var c = e.target.closest('button[data-cw]');
    if (c) { var w = c.getAttribute('data-cw'); colorway(w); set('steinbock-cw', w); }
  });
})();
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500..800'
         '&family=Instrument+Sans:wght@400..700&family=IBM+Plex+Mono:wght@500;600&display=swap">')


def page_body():
    global PIN_TOTAL
    PIN_TOTAL = sum(len(section_pins(i)[1]) for i in range(1, len(WINDOW_TREE.children) + 1))
    pl = PLANS
    hst_pairs = math.ceil(HST_COUNT / 2)
    total_hst = hst_pairs * 2
    win_unf = unf_dims(WINDOW.w, WINDOW.h)
    band_unf = unf_dims(20, 4)
    top_unf = unf_dims(20, 20)
    toc = [("design", "Design"), ("materials", "Materials"), ("cutting", "Cutting"), ("triangles", "Triangles"),
           ("blocks", "Stars"), ("band", "Sky band"), ("window", "Night window"), ("assembly", "Assembly"),
           ("finishing", "Finishing"), ("chart", "Chart")]
    toc_html = "".join(f'<a href="#{a}">{b}</a>' for a, b in toc)

    return f"""
<header class="bar"><div class="wrap bar-in">
  <a class="brand" href="#top">Steinbock</a>
  <nav class="toc" aria-label="Pattern sections">{toc_html}</nav>
  <div class="seg" role="group" aria-label="Measurements">
    <button type="button" id="u-cm" data-units-btn="cm" aria-pressed="true">cm</button>
    <button type="button" id="u-in" data-units-btn="in" aria-pressed="false">inch</button>
  </div>
</div></header>

<main class="wrap">
<section class="hero" id="top">
  <div>
    <p class="eyebrow">Zodiac patchwork · Capricorn · 22 Dec – 19 Jan</p>
    <h1>Steinbock</h1>
    <p class="subtitle">A two-fabric wall quilt of the alpine ibex under the stars of Capricornus</p>
    <p class="lede"><i>Steinbock</i> is German for the alpine ibex and for the sign of Capricorn. The quilt speaks the same language as the patchwork lion: two fabrics, and nothing but squares, rectangles and half-square triangles on a {m("5 cm", "2″")} grid. The ibex’s horn is a staircase of triangles with three ridges, the beard is a single triangle and the eye is one dark square. Above the ibex, the four brightest stars of the constellation stand in their true order.</p>
    <dl class="facts">{facts()}</dl>
  </div>
  <figure class="hero-fig">
    <div class="quilt">{hero_svg()}</div>
    <div class="cws" role="group" aria-label="Colourway">{colorway_buttons()}</div>
    <figcaption>Choose a colourway. Every diagram on this page follows it. <b>Lion pair</b> matches the mustard-and-black lion.</figcaption>
  </figure>
</section>

<section class="part" id="design">
  <div class="part-head"><span class="step">The design</span><h2>A star chart in the top band</h2></div>
  <div class="cols">
    <div class="prose">
      <p>Read the band as a star chart: you are facing south on an autumn evening, when Capricornus sits low over the horizon, so east is on the left and west is on the right.</p>
      <p><b>Deneb Algedi</b>, the brightest star of the constellation, gets the big sawtooth star. Its name is Arabic for “the tail of the goat”, so it shines above the ibex’s tail. <b>Nashira</b> sits next to it. <b>Dabih</b> and <b>Algedi</b> mark the goat’s head and horns in the old star maps, so their pinwheels hang above the ibex’s head.</p>
      <p>Down in the night window, an <b>edelweiss</b> star grows under the ibex’s chin. It is a friendship star block, reversed out in light on dark.</p>
      <p>The ibex faces right and the lion faces left. Hang the ibex to the left of the lion and the two look at each other.</p>
    </div>
    <figure class="panel">{constellation_svg()}<figcaption>Capricornus as it appears in the sky (top) and the four stars the band shows (bottom). Dot sizes follow brightness.</figcaption></figure>
  </div>
</section>

<section class="part" id="materials">
  <div class="part-head"><span class="step">Materials</span><h2>What you need</h2></div>
  <div class="tablewrap">{materials()}</div>
  <p class="note"><b>Contrast is everything.</b> Fabric L should be clearly lighter than fabric D. Photograph them side by side in black and white: if they look alike, the ibex will disappear. A mottled or hand-dyed light fabric gives the shimmer of the lion’s gold. A near-solid dark lets the stars read crisply.</p>
  <p class="prose">Tools: rotary cutter, mat and long ruler, a square ruler of at least {m("6.5 cm", "6½″")} for trimming triangles, a fabric marker, pins, and sticky notes for the piece codes.</p>
</section>

<section class="part" id="before">
  <div class="part-head"><span class="step">Before you begin</span><h2>How this pattern works</h2></div>
  <ul class="conv">
    <li><b>Seam allowance</b>All sizes include {m("0.75 cm", "¼″")} seams. Test before you start: sew six {m("6.5 cm", "2½″")} scrap squares into a row. It must be {m("31.5 cm", "12½″")} long, exactly as long as a D6 strip. Shorter means your seam is too wide, longer means too narrow. This is the check that matters most: {m("1 mm", "1/32″")} off per seam makes the busiest sections {m("2.4 cm", "¾″")} shorter than the plain strips.</li>
    <li><b>Grid</b>One grid unit is {m("5 cm", "2″")} finished. Every piece is a whole number of units, so every seam lines up with the grid.</li>
    <li><b>Piece codes</b>L = light fabric, D = dark fabric, numbered from smallest to largest. Label each stack as you cut.</li>
    <li><b>WOF</b>Width of fabric: cut strips selvage to selvage. The plans need {m("105 cm", "40″")} of usable width.</li>
    <li><b>Pressing</b>Press triangle seams toward the dark fabric. Press every other seam open: open seams keep the many intersections flat.</li>
    <li><b>Diagrams</b>All diagrams show the right side of the fabric. Gaps show which pieces are joined first: the narrower the gap, the earlier the seam.</li>
  </ul>
</section>

<section class="part" id="cutting">
  <div class="part-head"><span class="step">Cutting</span><h2>Cut the strips, then the pieces</h2>
    <p class="prose">Each diagram is one strip cut across the width of the fabric, with the pieces in cutting order. Grey areas are left over. Pieces marked “trimmed” are cut to length from a wider strip and then trimmed to width.</p>
    <p class="prose">The four long strips <span class="chip D">D10</span> <span class="chip L">L6</span> <span class="chip L">L7</span> <span class="chip L">L8</span> are cut {m(CM.fmt(CM.long_extra), IN.fmt(IN.long_extra))} longer than they finish (the pale end in the diagrams). Each one is sewn to a pieced part, so you trim it to the length you measure on that part.</p></div>
  {cutting_block("L", "Fabric L, light", m(pl["cm"]["L"]["buy"], pl["in"]["L"]["buy"]) + " · ibex, frame, sky band")}
  {cutting_block("D", "Fabric D, dark", m(pl["cm"]["D"]["buy"], pl["in"]["D"]["buy"]) + " · night window, star centres, binding")}
  <p class="note">Backing and batting: cut both to {m("120 × 120 cm", "48 × 48″")}. Hanging sleeve: one strip {m("22 × 95 cm", "8½ × 38″")}.</p>
</section>

<section class="part" id="triangles">
  <div class="part-head"><span class="step">Step 1</span><h2>Make {HST_COUNT} half-square triangles</h2>
    <p class="prose">Every triangle unit in the quilt is the same: half light, half dark. Only the way it is turned changes, and every diagram shows it by where the light half sits. The cutting plan gives {hst_pairs} pairs of squares, so you will make {total_hst} units, with one to spare.</p></div>
  <figure class="panel"><div class="cm">{hst_method_svg("cm")}</div><div class="in">{hst_method_svg("in")}</div>
    <figcaption>The pale square is the wrong side of fabric L. The drawn line is solid; the stitching lines are dashed. Centre the trimming frame on the seam.</figcaption></figure>
  <div class="cols" style="margin-top:22px">
    <ol class="prose">
      <li>Draw a diagonal line on the wrong side of each light {m("8 cm", "3″")} square.</li>
      <li>Place it right sides together on a dark square. Sew {m("0.75 cm", "¼″")} from the line on both sides.</li>
      <li>Cut on the line. Press the seam toward the dark fabric.</li>
      <li>Trim to {m("6.5 × 6.5 cm", "2½ × 2½″")}. Lay the 45° line of the square ruler on the seam so the diagonal runs exactly corner to corner.</li>
    </ol>
    <p class="note"><b>Faster: eight at a time.</b> Instead of the small squares, cut 6 light and 6 dark squares of {m("16 cm", "6″")}. Draw both diagonals, sew on both sides of both lines, cut horizontally, vertically and along both diagonals, then trim. That gives 48 units. Their edges are on the bias, so press gently and do not pull.</p>
  </div>
</section>

<section class="part" id="blocks">
  <div class="part-head"><span class="step">Step 2</span><h2>Piece the stars</h2>
    <p class="prose">Five small blocks: the sawtooth star of Deneb Algedi, three pinwheel stars and the edelweiss. Sew them first. In the later diagrams each block appears as one unit inside a dashed outline.</p></div>
  {block_cards()}
</section>

<section class="part" id="band">
  <div class="part-head"><span class="step">Step 3</span><h2>Assemble the sky band</h2></div>
  <div class="panel">{band_svg()}</div>
  <div class="cols" style="margin-top:20px">
    <ol class="prose">
      <li>Middle row, left to right: <span class="seq"><span class="chip L">L2</span><span class="chip blk">Nashira</span><span class="chip L">L10</span><span class="chip blk">Dabih</span><span class="chip L">L2</span><span class="chip blk">Algedi</span><span class="chip L">L9</span></span>. It measures {unf_dims(14, 2)}. Note that L10 lies on its side here.</li>
      <li>Measure the middle row through its centre and trim both <span class="chip L">L6</span> strips to that length. Sew one to the top and one to the bottom. The unit measures {unf_dims(14, 4)}.</li>
      <li>Join <span class="chip L">L10</span>, the Deneb Algedi block and this unit, left to right.</li>
    </ol>
    <p class="note">The finished band measures {band_unf}. Its light background and the light side strips of the frame become one colour field, so the stars float in a light sky.</p>
  </div>
</section>

<section class="part" id="window">
  <div class="part-head"><span class="step">Step 4</span><h2>Piece the night window in 11 sections</h2>
    <p class="prose">The window is pieced as eleven horizontal sections. Sew each section, press the seams open and check its size before going on. Then join sections 1 to 11 from top to bottom.</p></div>
  <div class="cols">
    <figure class="panel">{window_map_svg()}<figcaption>The window and its sections. Thin lines are the seams inside each section.</figcaption></figure>
    <div class="prose">
      <p>In each diagram below, the pieces are spread apart along the seams you sew. Most sections are a single row joined left to right. Section 11 has one column to make first: the edelweiss block over a <span class="chip D">D3</span>.</p>
      <p>Triangles appear as small icons in the sewing order. For example, {chip(Leaf(WINDOW, "HST", corner="9"))} is a triangle unit with the light half at the top right.</p>
      <p class="note"><b>Keep the lines straight.</b> The triangle marks <span class="pinkey down" aria-hidden="true"></span><span class="pinkey up" aria-hidden="true"></span> in each diagram show the {PIN_TOTAL} seams where the horn, head, neck, body or legs continue into the next section. Pin those first, then both ends, then ease in any difference between the pins. If a section is more than {m("3 mm", "⅛″")} off its size, re-sew a seam rather than stretching it.</p>
      <p>Sections 10 and 11 have the most pin points. Sew them first as a test: if the legs line up there, the rest will too.</p>
      <p>The finished window measures {win_unf}.</p>
    </div>
  </div>
  <div class="secs" style="margin-top:22px">{section_cards()}</div>
</section>

<section class="part" id="assembly">
  <div class="part-head"><span class="step">Step 5</span><h2>Frame and assemble the top</h2></div>
  <div class="cols">
    <figure class="panel">{assembly_svg()}<figcaption>Wide gaps are sewn last: window and L8 first, then the side strips, then the sky band.</figcaption></figure>
    <ol class="prose">
      <li>Measure the window across its middle and trim <span class="chip L">L8</span> to that length. Sew it to the bottom edge. The ibex now stands on solid ground.</li>
      <li>Measure the height of window and L8 through the middle and trim both <span class="chip L">L7</span> strips to that length. Sew them to the left and right edges.</li>
      <li>Sew the sky band to the top. Match its ends with the side strips.</li>
      <li>The quilt top measures {top_unf}. Stay-stitch around the edge, about {m("0.3 cm", "⅛″")} from the raw edge, to keep the outer seams from opening.</li>
    </ol>
  </div>
</section>

<section class="part" id="finishing">
  <div class="part-head"><span class="step">Steps 6 and 7</span><h2>Quilt, bind and hang</h2></div>
  <div class="cols">
    <div class="prose">
      <h3>Quilting</h3>
      <p>Layer the backing (right side down), the batting and the top. Baste with pins or spray. Then quilt:</p>
      <ol>
        <li>Stitch in the ditch around the ibex, the stars and along the frame to stabilise the layers.</li>
        <li><b>Night:</b> gently wavy horizontal lines {m("1.7 cm", "⅝″")} apart, like wind over a ridge. A free-motion meander works too.</li>
        <li><b>Ibex:</b> straight diagonal lines {m("1.25 cm", "½″")} apart, parallel to the horn ridges. They read as fur.</li>
        <li><b>Band and frame:</b> straight horizontal lines {m("2.5 cm", "1″")} apart. Stop at the stars.</li>
      </ol>
      <p>Use thread that blends into each fabric, or a slightly lighter gold on the night fabric for a starry shimmer.</p>
      <h3 style="margin-top:22px">Binding and hanging sleeve</h3>
      <ol>
        <li>Trim the batting and backing even with the top.</li>
        <li>Join the five binding strips end to end with diagonal seams and press them open. Fold the strip in half lengthwise, wrong sides together.</li>
        <li>Hem the short ends of the sleeve strip. Fold it lengthwise, wrong sides together, and baste its raw edges to the top edge of the back. The binding seam will catch it.</li>
        <li>Sew the binding to the front with a {m("0.75 cm", "¼″")} seam, mitring the corners. Turn it to the back and hand-stitch it down.</li>
        <li>Hand-stitch the folded lower edge of the sleeve to the backing. Leave a little slack so the rod does not distort the front.</li>
        <li>Add a label with your name, the year and the star sign.</li>
      </ol>
    </div>
    <figure class="panel">{quilting_plan_svg()}
      <figcaption><span class="legend"><span><i></i>Suggested quilting lines</span></span></figcaption></figure>
  </div>
</section>

<section class="part" id="chart">
  <div class="part-head"><span class="step">Reference</span><h2>Layout chart</h2>
    <p class="prose">The whole quilt with every piece code. The brackets on the left mark the sky band, the eleven window sections and the bottom strip. Triangle units carry no code: there is only one kind.</p></div>
  <figure class="panel chartpanel">{chart_svg()}</figure>
</section>

<footer>
  <p>Steinbock is an original design made as a companion to the patchwork lion zodiac quilt. Every measurement, cutting plan and diagram on this page is generated from one design grid and checked against it: each grid cell is covered exactly once, with the right fabric. The quilt was also sewn in software, seam by seam in the order given here, with real seam allowances and realistic sewing errors.</p>
  <p>Star positions: Wolfram StarData. Names: δ Cap Deneb Algedi, γ Cap Nashira, β Cap Dabih, α Cap Algedi.</p>
</footer>
</main>
"""


def quilting_plan_svg(s=20):
    from figures import quilting_paths, whole_quilt
    from svg import svg_wrap
    pad = 6
    defs, body = quilting_paths(s, pad, pad, "qp", "q-plan", "q-plan")
    W = NCOLS * s + 2 * pad
    inner = (f'<g opacity=".88">{whole_quilt(s, pad, pad)}</g>{body}'
             f'<rect class="outline" x="{pad}" y="{pad}" width="{NCOLS * s}" height="{NROWS * s}"/>')
    return svg_wrap(inner, W, W, cls="dia", title="Quilting plan", extra_defs=defs)


def build(fragment=False):
    sanity()
    title = "<title>Steinbock Quilt Pattern</title>"
    meta = ('<meta name="description" content="Steinbock: a two-fabric patchwork wall quilt pattern of the alpine ibex '
            'under the stars of Capricornus, with cutting plans and step-by-step diagrams in cm and inches.">')
    head = title + FONTS + f"<style>{CSS}</style>"
    body = page_body() + f"<script>{JS}</script>"
    if fragment:
        return head + body
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
