from lddstudio.transform import (TransformFixer, compute_offset, rotation_matrix)
from lddstudio.lxfml_model import Bone
from lddstudio.studio_data import TransformOffset


def test_aabb_center():
    b = {"minX": "0", "minY": "0", "minZ": "0", "maxX": "31.8", "maxY": "15.8", "maxZ": "7.8"}
    from lddstudio.transform import aabb_center
    c = aabb_center(b)
    assert abs(c[0] - 15.9) < 1e-6
    assert abs(c[2] - 3.9) < 1e-6


def test_fix_translation_offset():
    geo = {"3001": {"minX": "0", "minY": "0", "minZ": "0",
                    "maxX": "31.8", "maxY": "15.8", "maxZ": "7.8"}}
    fixer = TransformFixer(geo, {})
    bone = Bone("0", [1, 0, 0, 0, 1, 0, 0, 0, 1, 10, 20, 30])
    fixed = fixer.fix(bone, "3001")
    t = fixed.translation()
    # 中心补偿后平移应改变（10,20,30 加上偏移）
    assert t != (10.0, 20.0, 30.0)


def test_rotation_matrix_identity_for_zero():
    r = rotation_matrix(0, 0, 0)
    assert r == (1, 0, 0, 0, 1, 0, 0, 0, 1)


def test_rotation_matrix_90y():
    r = rotation_matrix(0, 90, 0)
    # Standard Y rotation: [cos 0 sin; 0 1 0; -sin 0 cos] with theta=90
    assert abs(r[0]) < 1e-9
    assert abs(r[2] - 1) < 1e-9
    assert abs(r[6] + 1) < 1e-9
    assert abs(r[4] - 1) < 1e-9


def test_apply_transform_offset_translation_only():
    off = TransformOffset(0, 0, 0, 10, -48, 50)
    fixer = TransformFixer({}, {}, {"41823": off})
    bone = Bone("0", [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    fixed = fixer.fix(bone, "41823")
    assert fixed.translation() == (10.0, -48.0, 50.0)


def test_apply_transform_offset_rotation_only_changes_rotation():
    off = TransformOffset(0, 90, 0, 0, 0, 0)
    fixer = TransformFixer({}, {}, {"44740": off})
    bone = Bone("0", [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    fixed = fixer.fix(bone, "44740")
    assert fixed.rotation3() != ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def test_unknown_part_unchanged():
    fixer = TransformFixer({}, {}, {})
    bone = Bone("0", [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    assert fixer.fix(bone, "99999").translation() == (0.0, 0.0, 0.0)


def test_offset_overrides_geo_bounding():
    off = TransformOffset(0, 0, 0, 5, 5, 5)
    geo = {"41823": {"minX": "0", "minY": "0", "minZ": "0",
                     "maxX": "10", "maxY": "10", "maxZ": "10"}}
    fixer = TransformFixer(geo, {}, {"41823": off})
    bone = Bone("0", [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0])
    assert fixer.fix(bone, "41823").translation() == (5.0, 5.0, 5.0)
