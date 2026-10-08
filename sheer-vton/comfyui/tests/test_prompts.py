from comfyui_sheer_vton import prompts as P


def test_every_combination_names_the_tokens_it_uses():
    for sc in P.SCENARIOS:
        for skin in P.SKIN:
            for holo in P.HOLO:
                pos, neg = P.inference_prompt(sc, skin, holo, 'front')
                for t in P.TOKENS.values():
                    assert t in pos, (sc, skin, holo, t)
                assert neg.startswith(P.NEGATIVE_BASE)


def test_disabled_tokens_are_left_out():
    pos, _ = P.inference_prompt('softbox', 'deep', 'film', 'side', mesh=False, holo=False)
    assert '[PROD_mesh]' not in pos and '[PROD_holo]' not in pos and '[PROD_lace]' in pos


def test_briefing_style_is_verbatim():
    pos, _ = P.inference_prompt('rim', 'medium', style='briefing')
    assert P.BRIEFING['rim'] in pos and P.BRIEFING_SKIN['medium'] in pos and P.BRIEFING_CAPTION in pos


def test_corrected_flash_prompt_drops_the_seam_shadows():
    pos, neg = P.inference_prompt('flash', 'fair')
    assert 'no visible cast shadows' in pos and 'cast shadows under the seams' in neg


def test_training_caption_from_scene_metadata():
    meta = dict(skin=dict(tone='deep'), rig=dict(id='rim'), view=dict(id='side'), holo='grating',
                mesh=dict(Pitch=0.6, BarWidth=0.155))
    long = P.training_caption(meta)
    short = P.training_caption(meta, style='short')
    assert all(t in long for t in P.TOKENS.values()) and '55 % open' in long
    assert 'Monk skin tone 9' in short and 'side view' in short
