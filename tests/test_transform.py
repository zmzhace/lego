from lddstudio.transform import TransformFixer, compute_offset
from lddstudio.lxfml_model import Bone

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
