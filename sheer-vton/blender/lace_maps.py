"""Procedural embroidered-lace texture maps: burgundy rose lace as in the reference photo.

    python lace_maps.py [out_dir] [--ppm 32]

Two designs: an allover tile for the side panels and a scalloped edging (eyelash fringe, footing) for
the top border. Every motif is embroidered thread mass: satin-stitch petals and fishbone leaves with a
raised cord (cordonnet) along their outlines, corded stems, a spiral at each rose's heart and French-knot
seeds. Only the thread mass is drawn; the tulle ground between motifs is the OSL net shader in the scene.

Per design the script writes (row 0 of the arrays is the bottom edge; images are flipped on save):
  <kind>_mask.png    R thread coverage, G cord, B cavity (shading between threads), A inside the trim
  <kind>_normal.png  tangent-space normals from the thread heights (OpenGL convention, +G = up)
  <kind>.json        tile size in mm and the UV offsets the scene's Mapping node needs
  <kind>_preview.png thread colour over skin, for checking
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))


class Canvas:
    def __init__(self, w_mm, h_mm, ppm, wrap_x=True, wrap_y=True):
        self.w_mm, self.h_mm, self.ppm = w_mm, h_mm, ppm
        self.W, self.H = int(round(w_mm * ppm)), int(round(h_mm * ppm))
        self.cov = np.zeros((self.H, self.W), np.float32)
        self.h = np.zeros((self.H, self.W), np.float32)
        self.cord = np.zeros((self.H, self.W), np.float32)
        self.wrap_x, self.wrap_y = wrap_x, wrap_y

    def paint(self, el, lift=0.0):
        x0, y0, x1, y1 = el.bbox()
        ox = (-self.w_mm, 0.0, self.w_mm) if self.wrap_x else (0.0,)
        oy = (-self.h_mm, 0.0, self.h_mm) if self.wrap_y else (0.0,)
        for dx in ox:
            for dy in oy:
                i0 = max(int(math.floor((x0 + dx) * self.ppm)) - 2, 0)
                i1 = min(int(math.ceil((x1 + dx) * self.ppm)) + 2, self.W)
                j0 = max(int(math.floor((y0 + dy) * self.ppm)) - 2, 0)
                j1 = min(int(math.ceil((y1 + dy) * self.ppm)) + 2, self.H)
                if i1 <= i0 or j1 <= j0:
                    continue
                xs = (np.arange(i0, i1) + 0.5) / self.ppm - dx
                ys = (np.arange(j0, j1) + 0.5) / self.ppm - dy
                X, Y = np.meshgrid(xs, ys)
                a, h, c = el.eval(X, Y, self.ppm)
                if a is None:
                    continue
                sl = (slice(j0, j1), slice(i0, i1))
                cov, hh, cd = self.cov[sl], self.h[sl], self.cord[sl]
                self.h[sl] = a * (h + lift) + (1 - a) * hh
                self.cord[sl] = a * c + (1 - a) * cd
                self.cov[sl] = a + (1 - a) * cov


def aa(d, ppm):
    """Coverage from a signed distance in mm (negative inside), one-pixel ramp."""
    return np.clip(0.5 - d * ppm, 0.0, 1.0)


def inner_dist(mask, ppm):
    return ndimage.distance_transform_edt(mask) / ppm


def cord_profile(dist, width, height):
    """Raised cord running along the outline: dist is the distance inside the shape (mm)."""
    x = (dist - width / 2) / (width / 2)
    return np.where(np.abs(x) < 1, height * np.sqrt(np.clip(1 - x * x, 0, 1)), 0.0), (np.abs(x) < 1).astype(np.float32)


class Shape:
    """Filled motif with satin-stitch ripples and a cord along its outline."""
    fill_h, dome, ripple, period, cord_w, cord_h = 0.10, 0.10, 0.022, 0.30, 0.34, 0.30

    def eval(self, X, Y, ppm):
        d, q = self.sdf(X, Y)
        a = aa(d, ppm)
        if not a.any():
            return None, None, None
        dist = inner_dist(d < 0, ppm)
        h = self.fill_h + self.dome * (1 - np.exp(-dist / 0.7)) + self.ripple * np.cos(2 * np.pi * q / self.period)
        ch, cm = cord_profile(dist, self.cord_w, self.cord_h)
        h = np.maximum(h, ch + 0.06)
        return a, h, cm


class Petal(Shape):
    """Satin-stitch petal. grille > 0 opens the outer part of the petal into a fine grid of holes
    (Leavers 'grille' fill) starting at that fraction of its length; eyelets punch corded holes."""

    def __init__(self, base, ang, length, width, notch=0.07, curl=0.0, grille=0.0, eyelets=0, seed=0):
        self.b, self.ang, self.L, self.Wd, self.notch, self.curl = np.array(base, float), ang, length, width, notch, curl
        self.grille, self.eyelets, self.seed = grille, eyelets, seed

    def bbox(self):
        r = self.L + self.Wd
        return self.b[0] - r, self.b[1] - r, self.b[0] + r, self.b[1] + r

    def sdf(self, X, Y):
        c, s = math.cos(self.ang), math.sin(self.ang)
        dx, dy = X - self.b[0], Y - self.b[1]
        u, t = dx * c + dy * s, -dx * s + dy * c
        t = t - self.curl * self.Wd * (u / self.L) ** 2
        lim = self.L * (1 - self.notch * np.exp(-(t / (0.16 * self.Wd)) ** 2))
        x = np.clip(u / lim, 0, 1)
        hw = 0.5 * self.Wd * np.sqrt(np.clip(1 - ((x - 0.55) / 0.45) ** 2, 0, 1)) * x ** 0.35
        d = np.abs(t) - hw
        d = np.where((u < 0) | (u > lim), np.maximum(d, np.minimum(np.abs(u), np.abs(u - lim))), d)
        self._u, self._t = u, t
        return d, t  # stitches run along the petal axis

    def eval(self, X, Y, ppm):
        a, h, cm = super().eval(X, Y, ppm)
        if a is None:
            return a, h, cm
        u, t, L, W = self._u, self._t, self.L, self.Wd
        # two veins from the base
        for off in (-0.2, 0.2):
            vein = (np.abs(t - off * W * (u / L)) < 0.07) & (u > 0.12 * L) & (u < 0.55 * L)
            h = np.where(vein, h - 0.05, h)
        if self.grille > 0:
            dist = inner_dist(a > 0.5, ppm)
            zone = (u > self.grille * L) & (dist > self.cord_w * 1.15)
            g = 0.42
            gx = (u + t) / math.sqrt(2) / g
            gy = (u - t) / math.sqrt(2) / g
            hole = np.hypot(gx - np.round(gx), gy - np.round(gy)) * g < 0.14
            a = np.where(zone & hole, 0.0, a)
            h = np.where(zone & ~hole, 0.13 + 0.02 * np.cos(2 * np.pi * t / 0.21), h)
        if self.eyelets:
            rng = np.random.default_rng(self.seed)
            for _ in range(self.eyelets):
                eu = rng.uniform(0.45, 0.7) * L
                et = rng.uniform(-0.18, 0.18) * W
                r = np.hypot(u - eu, t - et)
                a = np.where(r < 0.32, 0.0, a)
                ring = (r >= 0.32) & (r < 0.55)
                h = np.where(ring, 0.30 * np.sqrt(np.clip(1 - ((r - 0.435) / 0.115) ** 2, 0, 1)) + 0.1, h)
                cm = np.where(ring, 1.0, cm)
        return a, h, cm


class Leaf(Shape):
    period = 0.32

    def __init__(self, base, ang, length, width, bend=0.0):
        self.b, self.ang, self.L, self.Wd, self.bend = np.array(base, float), ang, length, width, bend

    def bbox(self):
        r = self.L + self.Wd
        return self.b[0] - r, self.b[1] - r, self.b[0] + r, self.b[1] + r

    def sdf(self, X, Y):
        c, s = math.cos(self.ang), math.sin(self.ang)
        dx, dy = X - self.b[0], Y - self.b[1]
        u, t = dx * c + dy * s, -dx * s + dy * c
        x = u / self.L
        t = t - self.bend * self.L * 4 * np.clip(x, 0, 1) * (1 - np.clip(x, 0, 1))
        hw = 0.5 * self.Wd * np.sin(np.pi * np.clip(x, 0, 1)) ** 0.75
        d = np.abs(t) - hw
        d = np.where((x < 0) | (x > 1), np.maximum(d, np.minimum(np.abs(u), np.abs(u - self.L))), d)
        self._t, self._x = t, x
        al = math.radians(38)
        q = -u * math.sin(al) + np.abs(t) * math.cos(al)  # fishbone stitches angled towards the tip
        return d, q

    def eval(self, X, Y, ppm):
        a, h, cm = super().eval(X, Y, ppm)
        if a is None:
            return a, h, cm
        # midrib cord
        rib = (np.abs(self._t) < 0.14) & (self._x > 0.06) & (self._x < 0.86)
        h = np.where(rib, np.maximum(h, 0.26 - 2.0 * np.abs(self._t)), h)
        cm = np.maximum(cm, rib.astype(np.float32))
        return a, h, cm


class Cord:
    """Corded line along a polyline (stems, tendrils, spirals, the scallop edge)."""

    def __init__(self, pts, width, height=0.26, twist=0.5):
        self.p = np.asarray(pts, float)
        self.w, self.ht, self.twist = width, height, twist

    def bbox(self):
        m = self.w
        return self.p[:, 0].min() - m, self.p[:, 1].min() - m, self.p[:, 0].max() + m, self.p[:, 1].max() + m

    def eval(self, X, Y, ppm):
        best = np.full(X.shape, np.inf)
        along = np.zeros(X.shape)
        acc = 0.0
        for a, b in zip(self.p[:-1], self.p[1:]):
            ab = b - a
            L2 = float(ab @ ab)
            if L2 < 1e-12:
                continue
            t = np.clip(((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / L2, 0, 1)
            d = np.hypot(X - a[0] - t * ab[0], Y - a[1] - t * ab[1])
            m = d < best
            best = np.where(m, d, best)
            along = np.where(m, acc + t * math.sqrt(L2), along)
            acc += math.sqrt(L2)
        r = self.w / 2
        a = aa(best - r, ppm)
        if not a.any():
            return None, None, None
        x = np.clip(best / r, 0, 1)
        h = self.ht * np.sqrt(np.clip(1 - x * x, 0, 1)) + 0.03 * np.cos(2 * np.pi * (along + 0.6 * best) / self.twist)
        return a, h + 0.05, np.ones_like(a)


class Seed:
    def __init__(self, c, r):
        self.c, self.r = np.asarray(c, float), r

    def bbox(self):
        return self.c[0] - self.r, self.c[1] - self.r, self.c[0] + self.r, self.c[1] + self.r

    def eval(self, X, Y, ppm):
        d = np.hypot(X - self.c[0], Y - self.c[1])
        a = aa(d - self.r, ppm)
        if not a.any():
            return None, None, None
        x = np.clip(d / self.r, 0, 1)
        return a, 0.08 + 0.26 * np.sqrt(1 - x * x), np.zeros_like(a)


class Band:
    """Dense straight footing along the bottom edge of the edging (stitches across the band)."""

    def __init__(self, y0, y1, w_mm):
        self.y0, self.y1, self.w = y0, y1, w_mm

    def bbox(self):
        return 0, self.y0, self.w, self.y1

    def eval(self, X, Y, ppm):
        d = np.maximum(self.y0 - Y, Y - self.y1)
        a = aa(d, ppm)
        h = 0.14 + 0.025 * np.cos(2 * np.pi * X / 0.28)
        top = np.abs(Y - (self.y1 - 0.25)) < 0.25
        h = np.where(top, 0.26, h)
        return a, h, top.astype(np.float32)


def bezier(p0, p1, p2, p3, n=48):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(p, float) for p in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def spiral(c, r0, r1, turns, rot, n=80):
    t = np.linspace(0, 1, n)
    a = rot + 2 * np.pi * turns * t
    r = r0 + (r1 - r0) * t
    return np.stack([c[0] + r * np.cos(a), c[1] + r * np.sin(a)], 1)


def rose(c, R, rot, rng, buds=False):
    """Embroidered rose: outer, middle and inner petal rings painted back to front, spiral heart."""
    els = []
    c = np.asarray(c, float)
    rot = math.radians(rot)
    if not buds:
        for k in range(5):
            a = rot + k * 2 * np.pi / 5 + rng.uniform(-0.12, 0.12)
            b = c + 0.14 * R * np.array([math.cos(a), math.sin(a)])
            els.append((Petal(b, a, 0.86 * R * rng.uniform(0.94, 1.06), 0.92 * R, notch=0.08, curl=rng.uniform(-0.15, 0.15),
                              grille=0.42 if R > 4.5 else 0.0, eyelets=int(rng.integers(0, 2)) if R > 6 else 0,
                              seed=int(rng.integers(1 << 30))), 0.0))
    for k in range(4):
        a = rot + np.pi / 4 + k * np.pi / 2 + rng.uniform(-0.1, 0.1)
        b = c + 0.07 * R * np.array([math.cos(a), math.sin(a)])
        els.append((Petal(b, a, 0.58 * R, 0.66 * R, notch=0.05), 0.07))
    for k in range(3):
        a = rot + 0.3 + k * 2 * np.pi / 3
        els.append((Petal(c, a, 0.34 * R, 0.4 * R, notch=0.0), 0.13))
    els.append((Cord(spiral(c, 0.04 * R, 0.24 * R, 1.6, rot), 0.36, height=0.22), 0.18))
    return els


def vine(cv, pts, rng, leaf_every=5.5, leaf_len=(5.5, 8.0), width=0.6, start_side=1, skip_ends=2.0):
    """Corded stem with leaves attached along it on alternating sides."""
    pts = np.asarray(pts, float)
    cv.paint(Cord(pts, width, height=0.24))
    seg = np.hypot(*np.diff(pts, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(seg)])
    side = start_side
    for at in np.arange(skip_ends + leaf_every * 0.5, cum[-1] - skip_ends, leaf_every):
        k = int(np.searchsorted(cum, at)) - 1
        k = max(min(k, len(seg) - 1), 0)
        f = (at - cum[k]) / max(seg[k], 1e-9)
        p = pts[k] + f * (pts[k + 1] - pts[k])
        tang = math.atan2(*(pts[k + 1] - pts[k])[::-1])
        ang = tang + side * math.radians(rng.uniform(40, 62))
        L = rng.uniform(*leaf_len)
        cv.paint(Leaf(p, ang, L, L * rng.uniform(0.42, 0.5), side * rng.uniform(0.0, 0.12)))
        side = -side


def floret(c, R, rot, rng):
    els = []
    for k in range(5):
        a = rot + k * 2 * np.pi / 5 + rng.uniform(-0.1, 0.1)
        els.append((Petal(np.asarray(c, float), a, R, 0.95 * R, notch=0.1), 0.0))
    els.append((Seed(c, 0.33 * R), 0.06))
    return els


def fill_gaps(cv, rng, gap_mm=3.2, trim=None, max_items=400):
    """Greedy filler: florets and seed clusters wherever the thread mass leaves a gap wider than gap_mm.
    The free-space map is computed once and then lowered around every placed filler."""
    ppm = cv.ppm
    occ = cv.cov > 0.3
    if trim is not None:
        occ = occ | (trim < 0.5)
    px, py = (int(8 * ppm) if cv.wrap_x else 0), (int(8 * ppm) if cv.wrap_y else 0)
    padded = np.pad(occ, ((py, py), (px, px)), mode='wrap')
    free = ndimage.distance_transform_edt(~padded)[py:py + cv.H, px:px + cv.W] / ppm
    X = (np.arange(cv.W) + 0.5) / ppm
    Y = (np.arange(cv.H) + 0.5) / ppm
    for _ in range(max_items):
        j, i = np.unravel_index(np.argmax(free), free.shape)
        if free[j, i] < gap_mm:
            break
        c = ((i + 0.5) / ppm, (j + 0.5) / ppm)
        r = min(free[j, i] * 0.55, 2.6)
        if rng.random() < 0.6 and r > 1.4:
            for el, lift in floret(c, r, rng.uniform(0, 2 * np.pi), rng):
                cv.paint(el, lift)
            ext = r
        else:
            for k in range(3):
                a = rng.uniform(0, 2 * np.pi)
                cv.paint(Seed((c[0] + 0.75 * math.cos(a + k * 2.1), c[1] + 0.75 * math.sin(a + k * 2.1)), rng.uniform(0.3, 0.42)))
            ext = 1.2
        dx = X - c[0]
        dy = Y - c[1]
        if cv.wrap_x:
            dx = (dx + cv.w_mm / 2) % cv.w_mm - cv.w_mm / 2
        if cv.wrap_y:
            dy = (dy + cv.h_mm / 2) % cv.h_mm - cv.h_mm / 2
        free = np.minimum(free, np.hypot(dx[None, :], dy[:, None]) - ext)


def leaf_on(p, ang_deg, L, W, bend=0.0):
    return Leaf(p, math.radians(ang_deg), L, W, bend)


def allover(ppm):
    """64 x 64 mm repeat for the side panels: roses on vines, leaves, buds, filler florets."""
    rng = np.random.default_rng(7)
    cv = Canvas(64.0, 64.0, ppm)
    vines = [
        (bezier((17, 42), (24, 28), (34, 22), (47, 13)), 1),
        (bezier((17, 42), (28, 56), (42, 60), (53, 50.5)), -1),
        (bezier((47, 13), (58, 6), (66, 4), (70, 10)), 1),
        (bezier((17, 42), (6, 36), (2, 22), (6, 10)), -1),
        (bezier((53, 50.5), (60, 44), (63, 36), (61, 30)), 1),
        (bezier((47, 13), (50, 24), (44, 31), (36, 35)), -1),
        (bezier((53, 50.5), (50, 60), (42, 66), (38, 72)), 1),
        (bezier((6, 10), (12, 4), (22, 3), (28, 8)), -1),
    ]
    for pts, side in vines:
        vine(cv, pts, rng, start_side=side)
    for tc, r1, rot in (((36.5, 35.5), 1.9, 0.4), ((58.5, 24.5), 1.6, 2.0), ((26.0, 58.5), 1.5, 4.0), ((29.5, 9.5), 1.4, 1.0)):
        cv.paint(Cord(spiral(tc, 0.3, r1, 1.5, rot), 0.32, height=0.18))
    for c, R, rot, bud in (((17, 42), 9.2, 10, False), ((47, 13), 7.8, 50, False), ((53, 50.5), 5.2, 20, False),
                           ((6, 10), 3.6, 70, True), ((61, 30), 3.2, 0, True), ((36, 35), 3.0, 40, True)):
        for el, lift in rose(c, R, rot, rng, buds=bud):
            cv.paint(el, lift)
    fill_gaps(cv, rng, gap_mm=3.0)
    inside = np.ones((cv.H, cv.W), np.float32)
    return cv, inside, dict(tile_mm=[64.0, 64.0], u0=0.0, v0=0.0)


def edging(ppm, z0_mm=248.0):
    """64 x 52 mm repeat along the border: straight footing at the bottom, scallops and eyelash on top."""
    rng = np.random.default_rng(11)
    cv = Canvas(64.0, 52.0, ppm, wrap_x=True, wrap_y=False)
    P = 64.0 / 3

    def edge_y(x):
        return 40.0 + 8.0 * np.abs(np.sin(np.pi * x / P)) ** 0.65

    xs = np.linspace(-2, 66, 900)
    edge = np.stack([xs, edge_y(xs) - 0.45], 1)
    # vine along the lower part, with leaves either side and small buds
    vx = np.linspace(-4, 68, 300)
    vine_pts = np.stack([vx, 15 + 3.5 * np.sin(2 * np.pi * vx / P)], 1)
    cv.paint(Band(0.0, 1.7, 64.0))
    vine(cv, vine_pts, rng, leaf_every=4.2, leaf_len=(4.8, 6.4), skip_ends=0.0)
    for k in range(3):
        x = (k + 0.5) * P
        cv.paint(Cord(bezier((x, 15 + 3.5 * math.sin(2 * math.pi * x / P)), (x - 1.5, 20), (x + 1.0, 24), (x, 28)), 0.55))
        cv.paint(leaf_on((x - 0.4, 25), 150, 6.2, 2.9, 0.1))
        cv.paint(leaf_on((x + 0.4, 25.5), 28, 6.2, 2.9, -0.1))
        for el, lift in rose((x, 33.5), 5.4, 25 + 40 * k, rng):
            cv.paint(el, lift)
        xc = k * P
        cv.paint(leaf_on((xc, 34), 120, 6.0, 2.7, 0.08))
        cv.paint(leaf_on((xc, 34), 60, 6.0, 2.7, -0.08))
        cv.paint(Seed((xc, 29.5), 0.45))
        cv.paint(Seed((xc - 1.3, 27.8), 0.38))
        cv.paint(Seed((xc + 1.3, 27.8), 0.38))
        cv.paint(Seed((x, 6.5), 0.5))
        cv.paint(Seed((x - 1.6, 7.6), 0.4))
        cv.paint(Seed((x + 1.6, 7.6), 0.4))
    Xg = (np.arange(cv.W) + 0.5) / ppm
    Yg = (np.arange(cv.H) + 0.5) / ppm
    trim = (Yg[:, None] <= edge_y(Xg)[None, :] - 2.6).astype(np.float32)
    trim[: int(2.2 * ppm)] = 0
    fill_gaps(cv, rng, gap_mm=2.6, trim=trim)
    # picots just inside the scallop edge, then the edge cord
    t = np.arange(0, 64, 1.55)
    for x in t:
        cv.paint(Seed((x, edge_y(x) - 1.75), 0.3))
    cv.paint(Cord(edge, 0.78, height=0.3))
    # eyelash fringe: fine loops standing off the edge
    lash = []
    for x in np.arange(0.2, 64, 0.72):
        y = edge_y(x)
        dy = (edge_y(x + 0.05) - edge_y(x - 0.05)) / 0.1
        n = np.array([-dy, 1.0]) / math.hypot(dy, 1.0)
        n = n + rng.normal(0, 0.12, 2)
        n /= np.linalg.norm(n)
        L = rng.uniform(1.0, 2.1)
        p0 = np.array([x, y - 0.3])
        lash.append(Cord([p0, p0 + n * L * 0.5, p0 + n * L], 0.13, height=0.07, twist=0.3))
    for el in lash:
        cv.paint(el)
    # trim: inside the scallop edge, plus the lashes
    X = (np.arange(cv.W) + 0.5) / ppm
    Y = (np.arange(cv.H) + 0.5) / ppm
    inside = (Y[:, None] <= edge_y(X)[None, :] + 0.1).astype(np.float32)
    inside = np.maximum(inside, (cv.cov > 0.02).astype(np.float32))
    return cv, inside, dict(tile_mm=[64.0, 52.0], u0=0.0, v0=-z0_mm / 52.0, z0_mm=z0_mm)


def save(cv, inside, meta, kind, out):
    ppm = cv.ppm
    h = ndimage.gaussian_filter(cv.h * (cv.cov > 0.01), 0.6)
    gy, gx = np.gradient(h, 1.0 / ppm)
    n = np.stack([-gx, -gy, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    nrm = ((n * 0.5 + 0.5) * 255 + 0.5).astype(np.uint8)
    cav = np.clip((ndimage.gaussian_filter(h, 4.0) - h) * 9.0, 0, 1) * cv.cov
    mask = np.stack([cv.cov, np.clip(cv.cord, 0, 1), cav, inside], -1)
    m8 = (np.clip(mask, 0, 1) * 255 + 0.5).astype(np.uint8)
    Image.fromarray(np.flipud(m8), 'RGBA').save(os.path.join(out, f'{kind}_mask.png'), optimize=True)
    Image.fromarray(np.flipud(nrm), 'RGB').save(os.path.join(out, f'{kind}_normal.png'), optimize=True)
    meta = dict(meta, px_per_mm=ppm, size_px=[cv.W, cv.H])
    json.dump(meta, open(os.path.join(out, f'{kind}.json'), 'w'), indent=1)
    # preview: thread over fair skin, lit from the upper left
    L = np.array([-0.4, 0.5, 0.77])
    L /= np.linalg.norm(L)
    shade = np.clip(n @ L, 0, 1)[..., None]
    skin = np.array([0.73, 0.47, 0.36])
    thread = np.array([0.115, 0.012, 0.019]) * (1 - 0.55 * cav[..., None]) * (0.35 + 0.9 * shade)
    rgb = skin * (1 - cv.cov[..., None]) * (0.55 + 0.45 * inside[..., None]) + thread * cv.cov[..., None]
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.clip(rgb, 0, None) ** (1 / 2.4) - 0.055)
    Image.fromarray(np.flipud((np.clip(srgb, 0, 1) * 255).astype(np.uint8))).save(os.path.join(out, f'{kind}_preview.png'))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.path.join(HERE, '..', 'assets', 'lace')
    ppm = 32
    if '--ppm' in sys.argv:
        ppm = int(sys.argv[sys.argv.index('--ppm') + 1])
    os.makedirs(out, exist_ok=True)
    for kind, fn in (('allover', allover), ('edging', edging)):
        cv, inside, meta = fn(ppm)
        save(cv, inside, meta, kind, out)
        print(kind, cv.W, 'x', cv.H, 'coverage %.2f' % cv.cov.mean())


if __name__ == '__main__':
    main()
