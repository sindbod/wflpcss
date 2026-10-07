# Steinbock: a Capricorn patchwork wall quilt

![Steinbock quilt preview](steinbock-preview.png)

An original two-fabric wall quilt made as a companion to the patchwork lion (Leo).
It uses the same visual language: squares, rectangles and half-square triangles on a grid.
An alpine ibex (*Steinbock*, German for both the ibex and the sign of Capricorn) stands in a
night window. Above it, a sky band shows the four brightest stars of the constellation
Capricornus in their real order: Deneb Algedi, Nashira, Dabih and Algedi.

| | |
|---|---|
| Finished size | 100 × 100 cm (40 × 40″) |
| Grid | 20 × 20 units of 5 cm (2″) |
| Pieces | 69 squares and rectangles, 45 half-square triangles |
| Fabric L, light | 1 m (1 yd) |
| Fabric D, dark, incl. binding | 1.3 m (1½ yd) |
| Level | Confident beginner |

![The four colourways](steinbock-colourways.png)

## Files

| File | What it is |
|---|---|
| `index.html` | The full pattern. Open it in a browser and switch between cm and inch and between four colourways. |
| `steinbock-pattern-cm.pdf`, `steinbock-pattern-in.pdf` | Printable A4 versions of the pattern (metric and imperial). |
| `design/steinbock.txt` | The design grid that everything else is generated from. |
| `tools/` | The generator: piecing solver, cutting planner, diagrams, page and PDF builder. |

The pattern covers materials, a strip-by-strip cutting plan for each fabric, half-square
triangles, the three star blocks, the sky band, the night window in 11 sections (each
with a size check), framing, quilting suggestions, binding, a hanging sleeve and a full
layout chart with every piece code.

## How it is generated

The design is one grid of cells in `design/steinbock.txt`:

```
#  fabric L (light)         .  fabric D (dark)
7 9 1 3  half-square triangle; the digit is the numpad corner that is light
```

`tools/plan.py` turns the grid into a sewing plan:

1. **Piecing.** `tools/quilt.py` searches every way to split each region with straight,
   full-length seams. It keeps the split with the fewest pieces, and then the fewest
   sub-assemblies. The stars and the edelweiss are kept whole as blocks. The night window
   is limited to horizontal sections, so every step reads as "join these left to right".
2. **Piece codes.** Identical cut pieces share a code (L1–L11, D1–D14), numbered by size.
3. **Cutting.** Pieces are packed into strips cut across the width of the fabric (usable
   width 105 cm / 40″). Fabric amounts are the strip total plus a straightening allowance.
4. **Checks.** Every grid cell must be covered exactly once with the right fabric. The
   fabric area must add up, and every planned cut must match the piece list. The build
   stops if any check fails.

Rebuild after editing the grid:

```sh
python3 tools/build_page.py   # writes index.html
node tools/make_pdf.js        # writes both PDFs (needs Playwright with Chromium)
```

Star positions come from Wolfram StarData.
