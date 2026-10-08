"""KOGGE - a Hanseatic cog in modular geometric patchwork.

The design is drawn on a 24 x 24 grid. Every cell is one module:

    fill(x, y, w, h, F)        solid squares of fabric F
    hst(x, y, corner, F, G)    half-square triangle, F in the numpad corner, G in the rest
    qc(x, y, n, corner, F, G, rings)
                               quarter circle unit, n x n cells: a quarter disc of F
                               centred on the numpad corner, on background G, with
                               optional smaller discs (radius in cells, fabric) on top

Numpad corners: 7 top-left, 9 top-right, 1 bottom-left, 3 bottom-right.
Later calls paint over earlier ones.
"""

FABRICS = {  # key: (name, role, default colour)
    "S": ("Sky", "background above the waterline", "#F3C6B6"),
    "U": ("Sun gold", "sun", "#F1B23A"),
    "R": ("Hanse red", "sail stripes, pennant, flag, sun", "#C8352B"),
    "W": ("Sailcloth", "sail stripes, flag, herring", "#F5EDDD"),
    "C": ("Copper", "castles, planking, sun", "#C47A3D"),
    "B": ("Oak brown", "hull, mast, yard, rudder", "#5E3423"),
    "T": ("Teal", "waves", "#2A8A87"),
    "A": ("Aqua", "wave crests", "#8FCFC4"),
    "N": ("Baltic navy", "deep sea, gulls, binding", "#1D3150"),
}
W = H = 24


def build(d):
    # sea
    d.fill(0, 14, W, H - 14, "N")
    for x in range(0, W, 4):
        d.qc(x, 14, 2, "3", "T", "S", rings=[(1, "A")])
        d.qc(x + 2, 14, 2, "1", "T", "S", rings=[(1, "A")])
    d.fill(0, 16, W, 1, "T")
    # rising sun in the top right corner
    d.qc(19, 0, 5, "9", "U", "S", rings=[(3.5, "C"), (2, "R")])
    # mast, yard and the striped square sail
    d.fill(12, 1, 1, 10, "B")
    d.fill(7, 3, 11, 1, "B")
    for i, x in enumerate(range(8, 17)):
        d.fill(x, 4, 1, 7, "R" if i % 2 == 0 else "W")
    d.qc(8, 10, 1, "9", "R", "S")
    d.qc(16, 10, 1, "7", "R", "S")
    # pennant at the masthead, streaming with the wind
    d.fill(13, 1, 2, 1, "R")
    d.hst(15, 1, "7", "R", "S")
    # hull: oak with a copper plank band that bends round bow and stern
    d.fill(6, 11, 12, 3, "B")
    d.fill(6, 12, 12, 1, "C")
    d.qc(3, 11, 3, "9", "B", "S", rings=[(2, "C"), (1, "B")])
    d.qc(18, 11, 3, "7", "B", "S", rings=[(2, "C"), (1, "B")])
    # stern castle with crenellations and a window, bow castle
    d.fill(3, 7, 5, 4, "C")
    d.fill(4, 7, 1, 1, "S")
    d.fill(6, 7, 1, 1, "S")
    d.fill(5, 9, 1, 1, "B")
    d.fill(18, 9, 3, 2, "C")
    d.fill(19, 9, 1, 1, "S")
    # stern rudder
    d.fill(2, 11, 1, 3, "B")
    # Luebeck flag, white over red, on the stern castle
    d.fill(4, 4, 1, 3, "B")
    d.fill(5, 4, 2, 1, "W")
    d.fill(5, 5, 2, 1, "R")
    # gulls
    for x, y in ((1, 2), (4, 1)):
        d.qc(x, y, 1, "1", "N", "S")
        d.qc(x + 1, y, 1, "3", "N", "S")
    # herring: tail, body, round head
    for x, y in ((4, 18), (10, 20), (15, 18), (19, 21)):
        d.hst(x, y, "1", "W", "N")
        d.hst(x, y + 1, "7", "W", "N")
        d.fill(x + 1, y, 1, 2, "W")
        d.qc(x + 2, y, 1, "1", "W", "N")
        d.qc(x + 2, y + 1, 1, "7", "W", "N")
