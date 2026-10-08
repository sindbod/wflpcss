"""Frequency-separation detail restore: numpy core shared by the ComfyUI node and the evaluation.

The refiner pass (low denoise) fixes lighting and skin blending but softens or reinvents the weave. This
puts the source image's fine detail (weave, lace threads) back over the refiner's lighting:

    out = low_pass(refined) + strength * guard(high_pass(source))     inside the (feathered) mask

Choices that matter, all exposed as parameters:
  * mode: how the source detail is carried over when the refined image is lit differently.
      'matched' (default): additive detail scaled per pixel by the ratio of local brightness, refined over
        source, capped at level_cap. Equal to the classic split where the two images agree in level, and it
        cannot paste bright threads into a frame that got darker. On ground-truth renders of sheer mesh
        (3 skin tones x 6 lighting changes) it gained 2.2 dB on average over no restore and never lost more
        than 0.9 dB; the additive split lost 4.8 dB on average (21 dB when the target was darker) and the
        log-luminance split 1.3 dB (5.8 dB when the source was dark).
      'additive': the classic retouching split; its detail band carries the source's lighting level.
      'multiplicative': splits log values, so detail is a ratio; right for an opaque texture under new light,
        but a sheer net's contrast itself changes with the light, and dark sources blow the ratio up.
  * radius: the Gaussian sigma that splits the bands. It must sit between the weave period and the
    lighting scale; sigma ~ period / 2 puts the weave entirely in the high band. estimate_period()
    reads the period from the source's spectrum.
  * luminance_only: carry only the luminance detail and keep the refiner's colour. Off by default: a net's
    detail is colour too (burgundy yarn against skin, alternating at the weave), and dropping it costs
    more than the source's lighting colour it would keep out.
  * guard: soft-clips the high band to a few robust standard deviations so specular glints of the old
    lighting (worst on metallic or holographic parts) are not restored as stale highlights. Glints
    should not be restored at all: keep holographic or other specular regions out of the mask
    (exclude).
  * The source must be registered to the refined image to the pixel; a shift of half a weave period
    turns restored detail into ghosting. Use the pass-1 output (same geometry), not the flat product
    shot, unless it has been warped onto the body.
Images are float arrays (H, W, 3) in [0, 1], sRGB-encoded as in ComfyUI; masks (H, W) in [0, 1].
"""
import math

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def srgb_to_linear(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


def _gauss_axis(a, sigma, axis):
    r = max(int(math.ceil(3.0 * sigma)), 1)
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode='reflect' if a.shape[axis] > r else 'edge')
    out = np.zeros_like(a, dtype=np.float32)
    n = a.shape[axis]
    for i, w in enumerate(k):
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(i, i + n)
        out += w * p[tuple(sl)]
    return out


def _box_axis(a, w, axis):
    """Box filter of odd width w along an axis (cumulative sums, edge-reflected)."""
    r = w // 2
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    p = np.pad(a, pad, mode='reflect' if a.shape[axis] > r + 1 else 'edge')
    c = np.cumsum(p, axis=axis, dtype=np.float64)
    n = a.shape[axis]
    hi = [slice(None)] * a.ndim
    lo = [slice(None)] * a.ndim
    hi[axis] = slice(w, w + n)
    lo[axis] = slice(0, n)
    return ((c[tuple(hi)] - c[tuple(lo)]) / w).astype(np.float32)


def blur(a, sigma):
    """Separable Gaussian blur of an (H, W) or (H, W, C) array. Exact taps up to sigma 8, three box passes
    (within about 3 % of a Gaussian) above that, so large radii stay fast."""
    a = np.asarray(a, np.float32)
    if sigma <= 0:
        return a.copy()
    if sigma <= 8:
        return _gauss_axis(_gauss_axis(a, sigma, 0), sigma, 1)
    n = 3
    wi = math.sqrt(12 * sigma * sigma / n + 1)
    wl = int(math.floor(wi))
    wl -= (wl % 2 == 0)
    wu = wl + 2
    m = round((12 * sigma * sigma - n * wl * wl - 4 * n * wl - 3 * n) / (-4 * wl - 4))
    out = a
    for i in range(n):
        w = wl if i < m else wu
        out = _box_axis(_box_axis(out, w, 0), w, 1)
    return out


def luma(img):
    return np.tensordot(img, LUMA, axes=([-1], [0])).astype(np.float32)


def soft_guard(high, k, mask=None):
    """Soft-clip a high-pass band to k robust standard deviations (MAD), measured inside the mask."""
    if k is None or k <= 0:
        return high
    sel = high if mask is None else high[mask > 0.5]
    if sel.size < 16:
        sel = high
    flat = sel.reshape(-1)
    med = np.median(flat)
    mad = np.median(np.abs(flat - med)) * 1.4826 + 1e-6
    g = k * mad
    return (g * np.tanh(high / g)).astype(np.float32)


def estimate_period(img, mask=None, min_px=2.0, max_px=64.0):
    """Dominant texture period (pixels) of an image region from its radially averaged power spectrum."""
    y = luma(img) if img.ndim == 3 else np.asarray(img, np.float32)
    if mask is not None and (mask > 0.5).any():
        rows = np.where((mask > 0.5).any(1))[0]
        cols = np.where((mask > 0.5).any(0))[0]
        y = y[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
        m = mask[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1] > 0.5
        y = np.where(m, y, y[m].mean())
    h, w = y.shape
    s = min(h, w, 512)
    y = y[(h - s) // 2:(h - s) // 2 + s, (w - s) // 2:(w - s) // 2 + s]
    y = y - blur(y, 8.0)
    win = np.outer(np.hanning(s), np.hanning(s))
    P = np.abs(np.fft.fftshift(np.fft.fft2(y * win))) ** 2
    fy, fx = np.indices(P.shape) - s // 2
    r = np.hypot(fx, fy)
    rmin, rmax = s / max_px, s / min_px
    bins = np.arange(int(rmin), int(rmax) + 1)
    if len(bins) < 3:
        return None
    prof = np.array([P[(r >= b) & (r < b + 1)].mean() if ((r >= b) & (r < b + 1)).any() else 0.0 for b in bins])
    prof = prof * bins  # whiten the 1/f falloff a little
    b = bins[int(np.argmax(prof))] + 0.5
    return float(s / b)


def restore_detail(refined, source, mask, radius=0.0, strength=1.0, luminance_only=False, guard=3.0,
                   feather=2.0, linear=False, exclude=None, mode='matched', level_cap=1.5):
    """Put the source's high band back over the refined image inside mask. Returns (image, high, radius)."""
    R = np.asarray(refined, np.float32)
    S = np.asarray(source, np.float32)
    if R.shape != S.shape:
        raise ValueError(f'refined {R.shape} and source {S.shape} differ: register the source first')
    m = np.clip(np.asarray(mask, np.float32), 0, 1)
    if exclude is not None:
        m = m * (1.0 - np.clip(np.asarray(exclude, np.float32), 0, 1))
    if radius <= 0:
        p = estimate_period(S, m)
        radius = max(0.6, 0.5 * p) if p else 2.0
    if linear:
        R, S = srgb_to_linear(R), srgb_to_linear(S)
    eps = 1e-3 if linear else 4e-3
    if luminance_only:
        ys, yr = luma(S), luma(R)
        if mode == 'multiplicative':
            ls, lr = np.log(ys + eps), np.log(yr + eps)
            hs = soft_guard(ls - blur(ls, radius), guard, m)
            target = np.exp(blur(lr, radius) + strength * hs) - eps
        else:
            low_s, low_r = blur(ys, radius), blur(yr, radius)
            hs = soft_guard(ys - low_s, guard, m)
            if mode == 'matched':
                hs = hs * np.clip((low_r + 0.01) / (low_s + 0.01), 0.0, level_cap)
            target = low_r + strength * hs
        gain = np.clip((target + eps) / (yr + eps), 0.0, 4.0)
        out = R * gain[..., None]
        high = np.repeat(hs[..., None], 3, -1)
    else:
        if mode == 'multiplicative':
            ls, lr = np.log(S + eps), np.log(R + eps)
            hs = ls - blur(ls, radius)
            hs = np.stack([soft_guard(hs[..., c], guard, m) for c in range(hs.shape[-1])], -1)
            out = np.exp(blur(lr, radius) + strength * hs) - eps
        else:
            low_s, low_r = blur(S, radius), blur(R, radius)
            hs = S - low_s
            hs = np.stack([soft_guard(hs[..., c], guard, m) for c in range(hs.shape[-1])], -1)
            if mode == 'matched':
                hs = hs * np.clip((low_r + 0.01) / (low_s + 0.01), 0.0, level_cap)
            out = low_r + strength * hs
        high = hs
    mf = blur(m, feather) if feather > 0 else m
    mf = np.clip(mf, 0, 1)[..., None]
    out = mf * out + (1 - mf) * R
    if linear:
        out = linear_to_srgb(out)
    return np.clip(out, 0, 1).astype(np.float32), high.astype(np.float32), float(radius)


def high_pass_preview(high, gain=2.0):
    """Mid-grey visualisation of a high band."""
    return np.clip(0.5 + gain * high, 0, 1).astype(np.float32)
