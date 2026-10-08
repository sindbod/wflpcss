"""Three-token prompts and training captions for the sheer mesh / lace / holo VTON pipeline.

Two styles:
  'briefing'   the strings from the project briefing, verbatim
  'corrected'  the same scenarios rewritten to match what the ground-truth renders show (see the
               spec review): no visible cast shadows under on-axis flash, skin under the net darkened
               roughly by the square of the net's open fraction, the net closing up at the silhouette
               because of viewing angle (not tension), holographic colour from diffraction (or only a
               faint tint for a thin film over bright metal)
Pure Python, no dependencies: used by the ComfyUI node, the Blender dataset generator and the tests.
"""

TOKENS = {'mesh': '[PROD_mesh]', 'lace': '[PROD_lace]', 'holo': '[PROD_holo]'}

BRIEFING_CAPTION = (
    'Studio product photography of a [PROD_lace] luxury bodysuit. The main panels feature semi-transparent '
    '[PROD_mesh] which allows the underlying skin texture to show through clearly. The structural borders and '
    'tension bands are composed of a highly reflective [PROD_holo] elastic fabric that exhibits dynamic rainbow '
    'color-shifts under studio lighting.')

BRIEFING = {
    'flash': (
        'Hard direct camera flash photography, high-contrast fashion editorial style. Sharp, distinct shadows cast '
        'directly onto the skin beneath the [PROD_lace] panel seams. Pronounced skin pore texture and natural skin '
        'tones are cleanly visible through the translucent [PROD_mesh] panels. The [PROD_holo] surfaces generate '
        'sharp, blinding silver-white specular glares at direct reflective angles, fading out to rich violet and '
        'deep magenta iridescent edges.'),
    'softbox': (
        'Commercial product catalog photography, soft diffuse studio lighting. Large overhead softboxes create '
        'smooth, seamless gradients of light. Subtle, soft-edged ambient occlusion shadows form where the fabric '
        'touches the skin. The [PROD_mesh] exhibits a delicate, matte fabric texture without losing transparency '
        'over the skin. The [PROD_holo] bands show a clean, broad, continuous liquid-metal rainbow gradient (cyan, '
        "magenta, yellow) wrapping smoothly around the model's body contours."),
    'rim': (
        'Dramatic studio backlighting, high-end creative lingerie editorial. A strong rim light catches the edge of '
        'the body, causing the microscopic loose fibers of the [PROD_mesh] boundaries to glow softly. The sheer '
        'panels filter the background light, shifting color opacity based on fabric tension. The [PROD_holo] '
        'materials act as a dark conductive metal surface reflecting only the extreme edge-lit highlights as bright '
        'neon iridescent threads.'),
}

BRIEFING_SKIN = {
    'fair': ('Fabric cast-shadows: Cold-toned, low-saturation deep burgundy/gray. Transparency behavior: '
             'Micro-vascular skin tones, skin texture, and natural moles remain visible under 40% mesh opacity. '
             'High fabric-to-skin contrast.'),
    'medium': ("Fabric cast-shadows: Neutral dark-brown, warm-toned ambient occlusion. Transparency behavior: "
               "Subsurface olive tones blend with the fabric hue, darkening the mesh's apparent low-light color "
               'while highlights retain the pure textile thread color.'),
    'deep': ('Fabric cast-shadows: Rich, ultra-deep dark espresso shadows with minimal contrast variance. '
             'Transparency behavior: The high melanin skin acts as a dark backing mirror. The sheer mesh weave '
             'becomes highly pronounced and visible as a light-catching pattern over the dark skin canvas underneath.'),
}

SCENARIOS = {
    'flash': dict(
        label='A. Hard on-camera flash (as in the example photo)',
        lighting='direct on-camera flash photograph, flash-lit subject against a darker ambient background',
        corrected=(
            'Direct on-camera flash photograph, flash-lit subject against a darker ambient background. Hard frontal '
            'light with no visible cast shadows from the garment, because the flash sits on the lens axis and every '
            'shadow falls straight behind what casts it; a soft specular sheen runs down the centre of the torso.'),
        mesh=('{mesh} panels: the skin shows through the open net but darker and tinted toward the yarn colour; the '
              'net looks denser and more opaque where the body curves away from the camera.'),
        lace='{lace} embroidery, cords and satin channels read deep burgundy with small hard highlights.',
        negative='cast shadows under the seams, shadow outlines around the lace, glowing mesh, see-through mesh at the body edges',
    ),
    'strobe': dict(
        label="A'. Hard off-axis strobe (what sharp seam shadows need)",
        lighting='bare strobe 45 degrees to camera left, hard light, deep shadow side',
        corrected=(
            'Studio photograph lit by a bare strobe 45 degrees to camera left, hard light, deep shadow side, little '
            'fill. Crisp but narrow cast shadows, one to two millimetres wide, along the lower and far edges of the '
            'trims, channels and bands, because the garment lies on the skin.'),
        mesh=('{mesh} panels: the skin shows through the net darker and tinted toward the yarn; the net throws only '
              'a faint fine texture of shadow where it lifts off the body.'),
        lace='{lace} cords and channels: crisp highlights on the lit side and a hairline shadow on the other.',
        negative='wide soft shadows, shadows on the shadow side, glowing bands, flat lighting',
    ),
    'softbox': dict(
        label='B. Large softboxes (catalogue)',
        lighting='commercial catalogue photograph, large softboxes and a white sweep, soft wrap-around light',
        corrected=(
            'Commercial catalogue photograph, large softboxes and a white sweep, soft wrap-around light. No visible '
            'cast shadows from the garment, which lies within millimetres of the skin; only a slight darkening where '
            'the fabric presses into the body.'),
        mesh=('{mesh} panels: even, matte see-through; the skin reads at about a third of its bare brightness '
              'through the net and shifts toward the yarn colour, while the dots and yarn stay crisp.'),
        lace='{lace} embroidery shows its relief as soft sheen on the raised cords and satin-stitch petals.',
        negative='hard shadows, harsh highlights, glowing mesh, rainbow everywhere on the bands',
    ),
    'rim': dict(
        label='C. Rim / backlight',
        lighting='low-key studio photograph, two strip lights behind the subject, very little front fill',
        corrected=(
            "Low-key studio photograph, two strip lights behind the subject, very little front fill. Bright rim "
            "highlights trace the body's silhouette and the skin glows slightly warm right at the edge from light "
            'scattering inside it.'),
        mesh=('{mesh} panels: at the silhouette the net is seen edge-on, closes up and turns nearly opaque, glowing '
              'with the backlight it scatters forward; facing the camera it stays dark and sheer.'),
        lace='{lace} cords and scalloped edges catch thin rim highlights.',
        negative='evenly lit front, bright mesh facing the camera, colour on the dark front of the bands',
    ),
}

HOLO = {
    'grating': dict(
        label='diffraction foil (embossed, metallised)',
        flash=('{holo} bands: a white mirror glare where the band faces the lens, with narrow spectral rainbow '
               'fringes a few centimetres either side, violet nearest the glare and red furthest out.'),
        strobe=('{holo} bands: a dark mirror with spectral rainbow fringes only where the band tilts the first '
                'diffraction order into the lens.'),
        softbox=('{holo} bands: broad bright reflections of the softboxes, fringed with soft spectral colour that '
                 'shifts smoothly along the band as it curves around the body.'),
        rim=('{holo} bands: bright edge highlights where the band turns toward the rim lights, with saturated spectral '
             'colour where the grating throws the backlight toward the lens; the front of the band stays a dark mirror.'),
    ),
    'grating_pixel': dict(
        label='holographic glitter foil (pixelated gratings)',
        flash='{holo} bands: silver with a dense multicoloured sparkle around the flash glare.',
        strobe='{holo} bands: silver with fine multicoloured sparkle on the lit side.',
        softbox='{holo} bands: silver reflections speckled with fine multicoloured sparkle.',
        rim='{holo} bands: dark, with scattered multicoloured sparkles along the rim-lit edges.',
    ),
    'film': dict(
        label='thin film over bright metal',
        flash=('{holo} bands: a near-silver mirror glare with a faint pink-gold tint, no spectral rainbow; the tint '
               'drifts toward blue-green on the parts turned away.'),
        strobe='{holo} bands: near-silver mirror with a faint pink-gold tint.',
        softbox='{holo} bands: smooth silver reflections of the softboxes with a faint pink-gold cast.',
        rim='{holo} bands: dark mirror with silver-white edge highlights, no rainbow.',
    ),
}

SKIN = {
    'fair': dict(
        label='fair', mst=2,
        corrected=('Fair skin: under the net it keeps its pink undertone but drops to roughly a third of its bare '
                   'brightness and shifts toward the yarn colour; moles and freckles stay visible as soft shapes. '
                   'Shadows on the skin are warm and slightly more saturated than the lit skin, cooled only by blue '
                   'ambient light.')),
    'medium': dict(
        label='medium olive', mst=6,
        corrected=('Medium olive skin: under the net it keeps its golden-olive undertone and darkens the same way; '
                   'the yarn colour takes a larger share of the panel colour than on fair skin.')),
    'deep': dict(
        label='deep', mst=9,
        corrected=("Deep skin: under the net it darkens further and the yarn's own colour and sheen dominate, so the "
                   'net reads as a lighter, burgundy-tinted pattern over the skin. Bare skin shows specular highlights '
                   'as strong as on fair skin, which stand out more against it.')),
}

VIEWS = {
    'front': 'front view',
    'three_quarter': 'three-quarter view',
    'side': 'side view, the front panel seen at a grazing angle',
    'closeup': 'close-up',
    'macro': 'macro close-up',
}

NEGATIVE_BASE = 'flat game-asset texture, plastic skin, painted-on fabric, blurred lace, moire, oversharpened, watermark'


def _fill(text, tokens):
    return text.format(**{k: TOKENS[k] for k in TOKENS}) if text else ''


def inference_prompt(scenario='flash', skin='fair', holo_model='grating', view='front', mesh=True, lace=True,
                     holo=True, style='corrected', subject='luxury bodysuit', colour='burgundy'):
    """(positive, negative) prompt strings for the refiner pass."""
    if style == 'briefing':
        pos = BRIEFING.get(scenario) or BRIEFING['flash']
        skin_rule = BRIEFING_SKIN[skin]
        return f'{BRIEFING_CAPTION} {pos} {skin_rule}', NEGATIVE_BASE
    sc = SCENARIOS[scenario]
    parts = [sc['corrected']]
    head = f'{VIEWS.get(view, view)} of a {colour} '
    head += f"{TOKENS['lace']} {subject}" if lace else subject
    if mesh:
        head += f" with {TOKENS['mesh']} micro-dot tulle panels"
    if holo:
        head += f" and {TOKENS['holo']} elastic bands" if mesh else f" with {TOKENS['holo']} elastic bands"
    parts.insert(0, head[0].upper() + head[1:] + '.')
    if mesh:
        parts.append(_fill(sc['mesh'], TOKENS))
    if lace:
        parts.append(_fill(sc['lace'], TOKENS))
    if holo:
        parts.append(_fill(HOLO[holo_model][scenario], TOKENS))
    parts.append(SKIN[skin]['corrected'])
    neg = f"{NEGATIVE_BASE}, {sc['negative']}"
    return ' '.join(parts), neg


def training_caption(meta, style='long', subject='waist panel on a dress form'):
    """Caption for a ground-truth render from its scene description (SheerScene.describe())."""
    skin = meta['skin']['tone']
    rig = meta['rig']['id']
    view = meta['view']['id']
    holo_model = meta.get('holo', 'grating')
    if view not in VIEWS:
        view = 'closeup'
    mesh_meta = meta.get('mesh', {})
    open_pct = None
    if mesh_meta:
        p, w = mesh_meta.get('Pitch', 0.6), mesh_meta.get('BarWidth', 0.155)
        open_pct = int(round(100 * ((p - w) / p) ** 2))
    if style == 'short':
        return (f"{SCENARIOS[rig]['lighting']}, {VIEWS[view]}, burgundy {TOKENS['lace']} {subject} with "
                f"{TOKENS['mesh']} micro-dot tulle and {TOKENS['holo']} bands, {SKIN[skin]['label']} skin "
                f"(Monk skin tone {SKIN[skin]['mst']}).")
    pos, _ = inference_prompt(rig, skin, holo_model, view, subject=subject)
    extra = f' The tulle is about {open_pct} % open when seen straight on.' if open_pct else ''
    return pos + extra
