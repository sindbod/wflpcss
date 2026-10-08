import numpy as np

from comfyui_sheer_vton import freqsep as fs


def weave(h, w, period=6.0, angle=0.3):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = x * np.cos(angle) + y * np.sin(angle)
    v = -x * np.sin(angle) + y * np.cos(angle)
    return 0.55 + 0.35 * np.cos(2 * np.pi * u / period) * np.cos(2 * np.pi * v / period)


def scene(h=160, w=160):
    tex = weave(h, w)
    y, x = np.mgrid[0:h, 0:w] / h
    alb = tex[..., None] * np.array([0.8, 0.3, 0.35], np.float32)
    light_old = (0.35 + 0.65 * x)[..., None] * np.array([1.0, 0.88, 0.75], np.float32)  # warm, left to right
    light_new = (1.0 - 0.55 * y)[..., None] * np.array([0.8, 0.9, 1.0], np.float32)    # cool, top to bottom
    enc = fs.linear_to_srgb
    source, target = enc(alb * light_old), enc(alb * light_new)
    refined = fs.blur(target, 3.0)  # right lighting, weave lost
    return source, target, refined


def hp(a, s=3.0):
    y = fs.luma(a)
    return y - fs.blur(y, s)


def corr(a, b):
    return float(np.corrcoef(a.ravel(), b.ravel())[0, 1])


def test_blur_is_normalised_with_the_right_width():
    a = np.zeros((121, 121), np.float32)
    a[60, 60] = 1
    y, x = np.mgrid[0:121, 0:121]
    for s in (1.5, 4.0, 12.0):
        b = fs.blur(a, s)
        assert abs(b.sum() - 1) < 1e-3
        sd = np.sqrt((b * (x - 60) ** 2).sum())
        assert abs(sd - s) / s < 0.05, (s, sd)


def test_estimates_the_weave_period():
    x = np.mgrid[0:256, 0:256][1]
    grating = np.repeat((0.5 + 0.3 * np.cos(2 * np.pi * x / 6.0))[..., None], 3, -1).astype(np.float32)
    assert 5.4 < fs.estimate_period(grating) < 6.6
    # a cos(u) cos(v) weave puts its energy on the diagonals: spectral period 6 / sqrt(2)
    p = fs.estimate_period(np.repeat(weave(256, 256, period=6.0)[..., None], 3, -1))
    assert abs(p - 6 / np.sqrt(2)) < 0.4, p


def test_restores_weave_under_new_lighting():
    source, target, refined = scene()
    mask = np.ones(target.shape[:2], np.float32)
    out, high, r = fs.restore_detail(refined, source, mask, radius=0, guard=0, feather=0)
    assert 1.9 <= r <= 2.4  # half the 4.24 px spectral period
    c_out, c_ref = corr(hp(out), hp(target)), corr(hp(refined), hp(target))
    assert c_out > 0.95 and c_out > c_ref + 0.3, (c_out, c_ref)
    # the refined lighting (low band, colour) is kept
    assert np.abs(fs.blur(out, 8) - fs.blur(refined, 8)).mean() < 0.02
    err_out, err_ref = np.abs(out - target).mean(), np.abs(refined - target).mean()
    assert err_out < 0.5 * err_ref, (err_out, err_ref)


def test_multiplicative_beats_additive_when_lighting_changes():
    """The additive detail band carries the source's lighting level; the log-luminance band does not."""
    source, target, refined = scene()
    mask = np.ones(target.shape[:2], np.float32)
    for linear, factor in ((False, 0.3), (True, 0.1)):
        errs = {}
        for mode in ('multiplicative', 'additive'):
            out, _, _ = fs.restore_detail(refined, source, mask, radius=3.0, guard=0, feather=0, mode=mode,
                                          linear=linear)
            errs[mode] = float(np.sqrt(((hp(out) - hp(target)) ** 2).mean()))
        assert errs['multiplicative'] < factor * errs['additive'], (linear, errs)


def test_guard_suppresses_a_stale_glint():
    source, target, refined = scene()
    glint = source.copy()
    glint[78:83, 78:83] = 1.0
    mask = np.ones(target.shape[:2], np.float32)
    raw, _, _ = fs.restore_detail(refined, glint, mask, radius=3.0, guard=0, feather=0)
    guarded, _, _ = fs.restore_detail(refined, glint, mask, radius=3.0, guard=2.5, feather=0)
    spike = lambda img: fs.luma(img)[78:83, 78:83].mean() - fs.luma(target)[78:83, 78:83].mean()
    assert spike(guarded) < 0.5 * spike(raw), (spike(guarded), spike(raw))


def test_half_period_misregistration_turns_detail_into_ghosting():
    source, target, refined = scene()
    mask = np.ones(target.shape[:2], np.float32)
    shifted = np.roll(source, 3, axis=1)  # half of the 6 px period
    out, _, _ = fs.restore_detail(refined, shifted, mask, radius=3.0, guard=0, feather=0)
    assert corr(hp(out), hp(target)) < 0.0
    assert np.abs(out - target).mean() > np.abs(refined - target).mean()


def test_outside_the_mask_and_in_exclude_the_refined_image_is_untouched():
    source, target, refined = scene()
    mask = np.zeros(target.shape[:2], np.float32)
    mask[:, :80] = 1
    excl = np.zeros_like(mask)
    excl[:40] = 1
    out, _, _ = fs.restore_detail(refined, source, mask, radius=3.0, feather=0, exclude=excl)
    assert np.array_equal(out[:, 80:], np.clip(refined[:, 80:], 0, 1))
    assert np.array_equal(out[:40], np.clip(refined[:40], 0, 1))
    assert not np.allclose(out[40:, :80], refined[40:, :80])


def test_rejects_unregistered_sizes():
    source, target, refined = scene()
    try:
        fs.restore_detail(refined, source[:-2], np.ones(refined.shape[:2]))
    except ValueError as e:
        assert 'register' in str(e)
    else:
        raise AssertionError('expected ValueError')
