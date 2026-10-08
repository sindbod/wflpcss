"""Static check of an API-format workflow against ComfyUI node definitions, without running ComfyUI.

    python -I validate_workflow.py <comfyui_source_dir> workflows/sheer_vton_refiner.api.json

Core node schemas are read from the ComfyUI source with the ast module (nothing from it is imported or
executed); the Sheer VTON nodes come from this folder. For every node it checks that the class exists,
every required input is given, no unknown input is passed, links point at existing nodes and outputs,
and the linked output type matches the input type (where the source declares it).
"""
import ast
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _literal_type(v):
    if isinstance(v, ast.Tuple) and v.elts:
        first = v.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return 'COMBO'
    return 'UNKNOWN'


def _input_dict(d, fn):
    if isinstance(d, ast.Name):  # INPUT_TYPES builds a dict in a variable first
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == d.id for t in n.targets):
                if isinstance(n.value, ast.Dict):
                    d = n.value
                    break
    if not isinstance(d, ast.Dict):
        return None
    out = {}
    for k, v in zip(d.keys, d.values):
        if isinstance(k, ast.Constant) and k.value in ('required', 'optional', 'hidden'):
            if isinstance(v, ast.Dict):
                out[k.value] = {kk.value: _literal_type(vv) for kk, vv in zip(v.keys, v.values)
                                if isinstance(kk, ast.Constant)}
            else:
                out[k.value] = None  # built dynamically
    return out


def schemas_from_source(root):
    classes, mappings = {}, {}
    for dirpath, _, files in os.walk(root):
        if any(part in dirpath for part in ('tests', 'node_modules')):
            continue
        for f in files:
            if not f.endswith('.py'):
                continue
            try:
                tree = ast.parse(open(os.path.join(dirpath, f), encoding='utf-8').read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    info = {}
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == 'INPUT_TYPES':
                            rets = [n for n in ast.walk(item) if isinstance(n, ast.Return) and n.value is not None]
                            if rets:
                                info['inputs'] = _input_dict(rets[-1].value, item)
                        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'RETURN_TYPES' for t in item.targets):
                            if isinstance(item.value, (ast.Tuple, ast.List)):
                                info['outputs'] = [e.value if isinstance(e, ast.Constant) else 'COMBO' for e in item.value.elts]
                    if 'inputs' in info:
                        classes.setdefault(node.name, info)
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NODE_CLASS_MAPPINGS' for t in node.targets):
                    if isinstance(node.value, ast.Dict):
                        for k, v in zip(node.value.keys, node.value.values):
                            if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                                mappings[k.value] = v.id
    return {name: classes[cls] for name, cls in mappings.items() if cls in classes}


def schemas_from_package():
    sys.path.insert(0, HERE)
    try:
        import torch  # noqa: F401
    except ImportError:
        import types
        sys.modules['torch'] = types.ModuleType('torch')
    from comfyui_sheer_vton import NODE_CLASS_MAPPINGS
    out = {}
    for name, cls in NODE_CLASS_MAPPINGS.items():
        spec = cls.INPUT_TYPES()
        out[name] = dict(inputs={sec: {k: (v[0] if isinstance(v[0], str) else 'COMBO') for k, v in d.items()}
                                 for sec, d in spec.items()}, outputs=list(cls.RETURN_TYPES))
    return out


def validate(wf, schemas):
    errors, notes = [], []
    for nid, node in wf.items():
        ct = node['class_type']
        sch = schemas.get(ct)
        if sch is None:
            errors.append(f'{nid} {ct}: unknown node class')
            continue
        req = (sch['inputs'] or {}).get('required') or {}
        opt = (sch['inputs'] or {}).get('optional') or {}
        dynamic = (sch['inputs'] or {}).get('required') is None
        for k in req:
            if k not in node['inputs']:
                errors.append(f'{nid} {ct}: missing required input {k!r}')
        for k, v in node['inputs'].items():
            if k not in req and k not in opt and not dynamic:
                errors.append(f'{nid} {ct}: unknown input {k!r}')
                continue
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                src = wf.get(v[0])
                if src is None:
                    errors.append(f'{nid} {ct}.{k}: link to missing node {v[0]}')
                    continue
                ssch = schemas.get(src['class_type'])
                if ssch is None or ssch.get('outputs') is None:
                    continue
                if v[1] >= len(ssch['outputs']):
                    errors.append(f'{nid} {ct}.{k}: {src["class_type"]} has no output {v[1]}')
                    continue
                have = ssch['outputs'][v[1]]
                want = req.get(k) or opt.get(k)
                if want in ('COMBO', 'UNKNOWN', None) or have in ('COMBO', 'UNKNOWN', '*'):
                    continue
                if want != have and not (want == 'STRING' and have == 'STRING'):
                    errors.append(f'{nid} {ct}.{k}: expects {want}, gets {have} from {src["class_type"]}[{v[1]}]')
    return errors, notes


def main():
    src, wf_path = sys.argv[1], sys.argv[2]
    core = schemas_from_source(src)
    own = schemas_from_package()
    schemas = dict(core, **own)
    wf = json.load(open(wf_path))
    errors, _ = validate(wf, schemas)
    used = sorted({n['class_type'] for n in wf.values()})
    print(f'{len(core)} core node schemas read from {src}; {len(own)} Sheer VTON nodes')
    print('node classes used:', ', '.join(used))
    if errors:
        print('\n'.join('ERROR ' + e for e in errors))
        sys.exit(1)
    print(f'OK: {len(wf)} nodes, all inputs and links consistent')


if __name__ == '__main__':
    main()
