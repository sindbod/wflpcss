"""Writes the dual-pass refiner graph in ComfyUI's API format (workflows/sheer_vton_refiner.api.json).

Pass 1 (any VTON model: CatVTON, IDM-VTON, Leffa, FLUX fill + Redux ...) is an input image here, because
the briefing leaves the base VTON node open and every VTON model ships as a different custom node. Its
output and a token mask (R = [PROD_mesh], G = [PROD_lace], B = [PROD_holo], alpha = body) go in; the graph
then follows the briefing's pass 2 with the fixes from the review:

  token LoRA      the [PROD_*] tokens mean nothing to a base model until a LoRA (or embeddings) is trained
                  on token-captioned images, so the graph loads one
  refiner         SDXL img2img on the pass-1 latent, denoise 0.28, noise only inside mesh + holo
                  (SetLatentNoiseMask), ControlNet canny 0.75 + tile 0.6 from the pass-1 image
  composite       the refined region is pasted back over pass 1 so everything outside the mask stays
                  byte-identical (the VAE round trip would otherwise soften it)
  detail restore  SheerFrequencyRestore on the mesh only, holo excluded (its detail is lighting),
                  multiplicative (log-luminance) split, radius from the weave period
  QA              SheerTransmissionQA reports whether the skin under the mesh reads physically (between
                  about t^2 and 0.85 t) or like an alpha blend (t)
Run with run_workflow.py, or open the JSON in ComfyUI (it converts API-format files when loaded).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = dict(
    pass1_image='vton_pass1.png',
    token_mask='token_mask.png',
    checkpoint='sd_xl_base_1.0.safetensors',
    token_lora='sheer_tokens_sdxl.safetensors',
    lora_strength=0.8,
    canny_controlnet='controlnet-canny-sdxl-1.0.safetensors',
    tile_controlnet='controlnet-tile-sdxl-1.0.safetensors',
    scenario='flash', skin='fair', holo_model='grating', view='front',
    seed=20261008, steps=30, cfg=5.0, sampler='dpmpp_2m', scheduler='karras',
    denoise=0.28, canny_strength=0.75, tile_strength=0.6,
    open_fraction=0.50,  # the product net face-on, flocked dots included
)


def graph(p=DEFAULTS):
    p = dict(DEFAULTS, **p)
    g = {
        '1': ('LoadImage', {'image': p['pass1_image']}, 'Pass 1: VTON output'),
        '2': ('LoadImage', {'image': p['token_mask']}, 'Token mask (R mesh, G lace, B holo, alpha body)'),
        '3': ('SheerMaskSplit', {'token_mask': ['2', 0], 'threshold': 0.5, 'soft': True}, 'Split token mask'),
        '4': ('SheerTokenPrompt', {'scenario': p['scenario'], 'skin': p['skin'], 'holo_model': p['holo_model'],
                                   'view': p['view'], 'style': 'corrected', 'mesh': True, 'lace': True, 'holo': True,
                                   'subject': 'luxury bodysuit', 'colour': 'burgundy'}, 'Token prompt'),
        '5': ('CheckpointLoaderSimple', {'ckpt_name': p['checkpoint']}, 'SDXL checkpoint'),
        '6': ('LoraLoader', {'model': ['5', 0], 'clip': ['5', 1], 'lora_name': p['token_lora'],
                             'strength_model': p['lora_strength'], 'strength_clip': p['lora_strength']},
              'Token LoRA ([PROD_mesh] / [PROD_lace] / [PROD_holo])'),
        '7': ('CLIPTextEncode', {'text': ['4', 0], 'clip': ['6', 1]}, 'Positive'),
        '8': ('CLIPTextEncode', {'text': ['4', 1], 'clip': ['6', 1]}, 'Negative'),
        '9': ('ControlNetLoader', {'control_net_name': p['canny_controlnet']}, 'ControlNet canny'),
        '10': ('ControlNetLoader', {'control_net_name': p['tile_controlnet']}, 'ControlNet tile'),
        '11': ('Canny', {'image': ['1', 0], 'low_threshold': 0.15, 'high_threshold': 0.45}, 'Lace edges'),
        '12': ('ControlNetApplyAdvanced', {'positive': ['7', 0], 'negative': ['8', 0], 'control_net': ['9', 0],
                                           'image': ['11', 0], 'strength': p['canny_strength'],
                                           'start_percent': 0.0, 'end_percent': 1.0}, 'Canny 0.75'),
        '13': ('ControlNetApplyAdvanced', {'positive': ['12', 0], 'negative': ['12', 1], 'control_net': ['10', 0],
                                           'image': ['1', 0], 'strength': p['tile_strength'],
                                           'start_percent': 0.0, 'end_percent': 1.0}, 'Tile 0.6'),
        '14': ('VAEEncode', {'pixels': ['1', 0], 'vae': ['5', 2]}, 'Encode pass 1'),
        '15': ('SetLatentNoiseMask', {'samples': ['14', 0], 'mask': ['3', 3]}, 'Noise only in mesh + holo'),
        '16': ('KSampler', {'model': ['6', 0], 'seed': p['seed'], 'steps': p['steps'], 'cfg': p['cfg'],
                            'sampler_name': p['sampler'], 'scheduler': p['scheduler'], 'positive': ['13', 0],
                            'negative': ['13', 1], 'latent_image': ['15', 0], 'denoise': p['denoise']},
               'Pass 2: refiner (denoise 0.28)'),
        '17': ('VAEDecode', {'samples': ['16', 0], 'vae': ['5', 2]}, 'Decode'),
        '18': ('ImageCompositeMasked', {'destination': ['1', 0], 'source': ['17', 0], 'x': 0, 'y': 0,
                                        'resize_source': False, 'mask': ['3', 3]}, 'Paste refined region over pass 1'),
        '19': ('SheerFrequencyRestore', {'refined': ['18', 0], 'source': ['1', 0], 'mask': ['3', 0],
                                         'exclude_mask': ['3', 2], 'radius_px': 0.0, 'strength': 1.0,
                                         'luminance_only': True, 'highlight_guard': 3.0, 'feather_px': 2.0,
                                         'linear_light': False, 'mode': 'multiplicative'},
               'Restore weave detail (mesh only, holo excluded)'),
        '20': ('SaveImage', {'images': ['19', 0], 'filename_prefix': 'sheer_vton/refined'}, 'Save'),
        '21': ('PreviewImage', {'images': ['19', 1]}, 'Restored detail band'),
        '22': ('InvertMask', {'mask': ['2', 1]}, 'Body (LoadImage returns 1 - alpha)'),
        '23': ('MaskComposite', {'destination': ['22', 0], 'source': ['3', 4], 'x': 0, 'y': 0,
                                 'operation': 'subtract'}, 'Bare skin = body - garment'),
        '24': ('SheerTransmissionQA', {'image': ['19', 0], 'mesh_mask': ['3', 0], 'skin_mask': ['23', 0],
                                       'open_fraction': p['open_fraction']}, 'See-through QA'),
    }
    return {k: {'class_type': c, 'inputs': i, '_meta': {'title': t}} for k, (c, i, t) in g.items()}


def main():
    out = os.path.join(HERE, 'workflows')
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, 'sheer_vton_refiner.api.json')
    json.dump(graph(), open(path, 'w'), indent=1)
    print('wrote', path)


if __name__ == '__main__':
    main()
