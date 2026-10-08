import numpy as np
import torch

from comfyui_sheer_vton import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from comfyui_sheer_vton.nodes import SheerFrequencyRestore, SheerMaskSplit, SheerTokenPrompt, SheerTransmissionQA

from test_freqsep import scene


def t(a):
    return torch.from_numpy(np.asarray(a, np.float32))


def test_registry_is_complete():
    assert set(NODE_CLASS_MAPPINGS) == set(NODE_DISPLAY_NAME_MAPPINGS)
    for cls in NODE_CLASS_MAPPINGS.values():
        spec = cls.INPUT_TYPES()
        assert 'required' in spec
        assert hasattr(cls, cls.FUNCTION) and len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES)


def test_frequency_restore_batches_and_resizes_the_mask():
    source, target, refined = scene()
    batch_r = t(np.stack([refined, refined]))
    batch_s = t(np.stack([source, source]))
    small_mask = t(np.ones((1, 40, 40)))
    img, high, r = SheerFrequencyRestore().run(batch_r, batch_s, small_mask, 3.0, 1.0, True, 3.0, 2.0, False)
    assert np.asarray(img).shape == (2, 160, 160, 3) and np.asarray(high).shape == (2, 160, 160, 3)
    assert r == 3.0
    assert np.abs(np.asarray(img)[0] - target).mean() < np.abs(refined - target).mean()


def test_frequency_restore_refuses_unregistered_sources():
    source, target, refined = scene()
    try:
        SheerFrequencyRestore().run(t(refined[None]), t(source[None, :120]), t(np.ones((160, 160))), 3.0, 1.0,
                                    True, 3.0, 2.0, False)
    except ValueError as e:
        assert 'pixel-registered' in str(e)
    else:
        raise AssertionError('expected ValueError')


def test_mask_split_and_prompt():
    tm = np.zeros((1, 8, 8, 3), np.float32)
    tm[0, :4, :, 0] = 1
    tm[0, 4:, :4, 1] = 1
    tm[0, 4:, 4:, 2] = 1
    mesh, lace, holo, mh, garment = SheerMaskSplit().run(t(tm), 0.5, False)
    assert np.asarray(mesh).sum() == 32 and np.asarray(mh).sum() == 48 and np.asarray(garment).sum() == 64
    pos, neg = SheerTokenPrompt().run('softbox', 'medium', 'grating', 'front', 'corrected', True, True, True,
                                      'bodysuit', 'burgundy')
    assert '[PROD_mesh]' in pos and 'Medium olive skin' in pos


def test_transmission_qa_tells_double_pass_from_alpha_blend():
    from comfyui_sheer_vton.freqsep import linear_to_srgb
    sm = np.zeros((20, 20), np.float32)
    sm[:10] = 1
    mm = 1 - sm
    for skin, ratio, word in (((0.55, 0.33, 0.24), 0.21, 'physical'),                 # softbox: about t^2
                              ((0.55, 0.33, 0.24), 0.32, 'physical'),                 # flash, scattering skin
                              ((0.55, 0.33, 0.24), 0.55, 'too transparent'),          # alpha blend at t
                              ((0.55, 0.33, 0.24), 0.45, 'borderline'),
                              ((0.09, 0.045, 0.026), 0.25, 'inconclusive')):          # deep skin: yarn dominates
        img = np.zeros((1, 20, 20, 3), np.float32)
        img[0, :10] = linear_to_srgb(np.array(skin))
        img[0, 10:] = linear_to_srgb(np.array(skin) * ratio)
        out = SheerTransmissionQA().run(t(img), t(mm), t(sm), 0.50)
        assert word in out['result'][0], (ratio, out['result'][0])
