"""The refiner graph against ComfyUI's node definitions. Needs a ComfyUI source tree: set COMFYUI_SRC."""
import copy
import json
import os

import pytest

import build_workflow
import validate_workflow as V

SRC = os.environ.get('COMFYUI_SRC')
pytestmark = pytest.mark.skipif(not SRC, reason='set COMFYUI_SRC to a ComfyUI source tree')


@pytest.fixture(scope='module')
def schemas():
    return dict(V.schemas_from_source(SRC), **V.schemas_from_package())


def test_graph_is_consistent(schemas):
    errors, _ = V.validate(build_workflow.graph(), schemas)
    assert errors == []


def test_checked_in_json_matches_the_builder():
    path = os.path.join(os.path.dirname(build_workflow.__file__), 'workflows', 'sheer_vton_refiner.api.json')
    assert json.load(open(path)) == json.loads(json.dumps(build_workflow.graph()))


@pytest.mark.parametrize('break_it, expect', [
    (lambda g: g['16']['inputs'].pop('denoise'), "missing required input 'denoise'"),
    (lambda g: g['16']['inputs'].__setitem__('noise', 1), "unknown input 'noise'"),
    (lambda g: g['15']['inputs'].__setitem__('mask', ['1', 0]), 'expects MASK, gets IMAGE'),
    (lambda g: g['12']['inputs'].__setitem__('control_net', ['5', 0]), 'expects CONTROL_NET, gets MODEL'),
    (lambda g: g['3'].__setitem__('class_type', 'SheerMaskSplitt'), 'unknown node class'),
    (lambda g: g['19']['inputs'].__setitem__('source', ['99', 0]), 'link to missing node'),
])
def test_validator_catches_mistakes(schemas, break_it, expect):
    g = copy.deepcopy(build_workflow.graph())
    break_it(g)
    errors, _ = V.validate(g, schemas)
    assert any(expect in e for e in errors), errors
