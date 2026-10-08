"""ComfyUI nodes for the sheer mesh / lace / holo VTON refiner pass.

SheerFrequencyRestore  frequency-separation detail restore (the briefing's post-AI step, made safe)
SheerTokenPrompt       three-token prompts, briefing wording or physics-corrected wording
SheerMaskSplit         token mask image (R mesh, G lace, B holo) -> MASKs
SheerTransmissionQA    checks how much skin shows through the mesh against the double-pass expectation
"""
import numpy as np

from . import freqsep, prompts

CATEGORY = 'sheer_vton'


def _np(t):
    return np.asarray(t.detach().cpu().numpy() if hasattr(t, 'detach') else t, np.float32)


def _torch(a):
    import torch
    return torch.from_numpy(np.ascontiguousarray(a, np.float32))


def _resize(m, h, w):
    """Bilinear resize of a (H, W) array."""
    H, W = m.shape
    if (H, W) == (h, w):
        return m
    ys = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0, H - 1)
    xs = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0, W - 1)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a = m[y0][:, x0] * (1 - fx) + m[y0][:, x1] * fx
    b = m[y1][:, x0] * (1 - fx) + m[y1][:, x1] * fx
    return (a * (1 - fy) + b * fy).astype(np.float32)


def _mask_batch(mask, n, h, w):
    m = _np(mask)
    if m.ndim == 2:
        m = m[None]
    out = [_resize(m[min(i, len(m) - 1)], h, w) for i in range(n)]
    return out


class SheerFrequencyRestore:
    DESCRIPTION = ('Puts the source image\'s fine detail (weave, lace threads) back over the refined image inside '
                   'the mask. Feed the pass-1 output as source (pixel-registered). Keep holographic or other specular '
                   'parts out of the mask or in exclude_mask: their detail is lighting, and restoring it brings the old '
                   'highlights back.')

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'refined': ('IMAGE',),
                'source': ('IMAGE',),
                'mask': ('MASK',),
                'radius_px': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 64.0, 'step': 0.1,
                                        'tooltip': 'Gaussian sigma splitting the bands; 0 = half the weave period found in the source'}),
                'strength': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 2.0, 'step': 0.05}),
                'luminance_only': ('BOOLEAN', {'default': True,
                                               'tooltip': 'carry only luminance detail, keep the refined colour'}),
                'highlight_guard': ('FLOAT', {'default': 3.0, 'min': 0.0, 'max': 10.0, 'step': 0.1,
                                              'tooltip': 'soft-clip the detail band to this many robust std devs (0 = off)'}),
                'feather_px': ('FLOAT', {'default': 2.0, 'min': 0.0, 'max': 32.0, 'step': 0.5}),
                'linear_light': ('BOOLEAN', {'default': False}),
                'mode': (['multiplicative', 'additive'], {'tooltip': 'multiplicative splits log-luminance (lighting-invariant detail); additive is the classic split'}),
            },
            'optional': {'exclude_mask': ('MASK',)},
        }

    RETURN_TYPES = ('IMAGE', 'IMAGE', 'FLOAT')
    RETURN_NAMES = ('image', 'high_pass', 'radius_px')
    FUNCTION = 'run'
    CATEGORY = CATEGORY

    def run(self, refined, source, mask, radius_px, strength, luminance_only, highlight_guard, feather_px,
            linear_light, mode='multiplicative', exclude_mask=None):
        R, S = _np(refined), _np(source)
        if R.ndim == 3:
            R = R[None]
        if S.ndim == 3:
            S = S[None]
        n, h, w = R.shape[0], R.shape[1], R.shape[2]
        if S.shape[1:3] != (h, w):
            raise ValueError(f'source is {S.shape[2]}x{S.shape[1]}, refined is {w}x{h}: the source must be '
                             'pixel-registered to the refined image (use the pass-1 output)')
        masks = _mask_batch(mask, n, h, w)
        excl = _mask_batch(exclude_mask, n, h, w) if exclude_mask is not None else [None] * n
        outs, highs, used = [], [], []
        for i in range(n):
            o, hp, r = freqsep.restore_detail(R[i][..., :3], S[min(i, len(S) - 1)][..., :3], masks[i], radius_px,
                                              strength, luminance_only, highlight_guard, feather_px, linear_light,
                                              excl[i], mode)
            outs.append(o)
            highs.append(freqsep.high_pass_preview(hp))
            used.append(r)
        return _torch(np.stack(outs)), _torch(np.stack(highs)), float(np.mean(used))


class SheerTokenPrompt:
    DESCRIPTION = 'Builds the refiner prompt from the three product tokens, a lighting scenario and a skin tone.'

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'scenario': (list(prompts.SCENARIOS),),
                'skin': (list(prompts.SKIN),),
                'holo_model': (list(prompts.HOLO),),
                'view': (list(prompts.VIEWS),),
                'style': (['corrected', 'briefing'],),
                'mesh': ('BOOLEAN', {'default': True}),
                'lace': ('BOOLEAN', {'default': True}),
                'holo': ('BOOLEAN', {'default': True}),
                'subject': ('STRING', {'default': 'luxury bodysuit'}),
                'colour': ('STRING', {'default': 'burgundy'}),
            }
        }

    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('positive', 'negative')
    FUNCTION = 'run'
    CATEGORY = CATEGORY

    def run(self, scenario, skin, holo_model, view, style, mesh, lace, holo, subject, colour):
        return prompts.inference_prompt(scenario, skin, holo_model, view, mesh, lace, holo, style, subject, colour)


class SheerMaskSplit:
    DESCRIPTION = 'Splits a token mask image (R = [PROD_mesh], G = [PROD_lace], B = [PROD_holo]) into masks.'

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'token_mask': ('IMAGE',),
                             'threshold': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.01}),
                             'soft': ('BOOLEAN', {'default': True, 'tooltip': 'keep anti-aliased edges'})}}

    RETURN_TYPES = ('MASK', 'MASK', 'MASK', 'MASK', 'MASK')
    RETURN_NAMES = ('mesh', 'lace', 'holo', 'mesh_or_holo', 'garment')
    FUNCTION = 'run'
    CATEGORY = CATEGORY

    def run(self, token_mask, threshold, soft):
        t = _np(token_mask)
        if t.ndim == 3:
            t = t[None]
        ch = [t[..., c] for c in range(3)]
        if not soft:
            ch = [(c >= threshold).astype(np.float32) for c in ch]
        mesh, lace, holo = ch
        return (_torch(mesh), _torch(lace), _torch(holo), _torch(np.maximum(mesh, holo)),
                _torch(np.maximum(np.maximum(mesh, lace), holo)))


def transmission_report(image, mesh_mask, skin_mask, open_fraction):
    """Compare how much skin shows through the mesh with the alpha-blend (t) and double-pass (t^2) models.
    Uses the green channel, where a red/burgundy yarn contributes almost nothing of its own."""
    lin = freqsep.srgb_to_linear(image[..., :3])
    m, s = mesh_mask > 0.5, skin_mask > 0.5
    if m.sum() < 16 or s.sum() < 16:
        return 'not enough pixels in the masks', float('nan')
    g_mesh = float(np.median(lin[..., 1][m]))
    g_skin = float(np.median(lin[..., 1][s]))
    ratio = g_mesh / max(g_skin, 1e-6)
    t = open_fraction
    near = 'double pass (physical)' if abs(ratio - t * t) < abs(ratio - t) else 'alpha blend (too transparent)'
    rep = (f'green see-through ratio {ratio:.3f}; double-pass prediction t^2 = {t * t:.3f}, '
           f'alpha-blend prediction t = {t:.3f} -> closer to {near}')
    return rep, ratio


class SheerTransmissionQA:
    DESCRIPTION = ('Measures skin seen through the mesh against bare skin. Skin scatters light millimetres under its '
                   'surface, so light crosses the net twice and the skin reads at about t^2 of its bare brightness '
                   '(t = open fraction), not t as an alpha blend would give.')

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'image': ('IMAGE',), 'mesh_mask': ('MASK',), 'skin_mask': ('MASK',),
                             'open_fraction': ('FLOAT', {'default': 0.55, 'min': 0.05, 'max': 0.95, 'step': 0.01})}}

    RETURN_TYPES = ('STRING', 'FLOAT')
    RETURN_NAMES = ('report', 'ratio')
    FUNCTION = 'run'
    CATEGORY = CATEGORY
    OUTPUT_NODE = True

    def run(self, image, mesh_mask, skin_mask, open_fraction):
        img = _np(image)
        if img.ndim == 3:
            img = img[None]
        h, w = img.shape[1:3]
        mm = _mask_batch(mesh_mask, 1, h, w)[0]
        sm = _mask_batch(skin_mask, 1, h, w)[0]
        rep, ratio = transmission_report(img[0], mm, sm, open_fraction)
        return {'ui': {'text': [rep]}, 'result': (rep, ratio)}


NODE_CLASS_MAPPINGS = {
    'SheerFrequencyRestore': SheerFrequencyRestore,
    'SheerTokenPrompt': SheerTokenPrompt,
    'SheerMaskSplit': SheerMaskSplit,
    'SheerTransmissionQA': SheerTransmissionQA,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'SheerFrequencyRestore': 'Sheer VTON: frequency-separation detail restore',
    'SheerTokenPrompt': 'Sheer VTON: token prompt',
    'SheerMaskSplit': 'Sheer VTON: split token mask',
    'SheerTransmissionQA': 'Sheer VTON: see-through QA',
}
