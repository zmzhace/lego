from lddstudio.lxfml_model import Bone


def aabb_center(bounding: dict) -> tuple:
    return ((float(bounding["minX"]) + float(bounding["maxX"])) / 2,
            (float(bounding["minY"]) + float(bounding["maxY"])) / 2,
            (float(bounding["minZ"]) + float(bounding["maxZ"])) / 2)


def compute_offset(ldd_center, studio_center) -> tuple:
    return (ldd_center[0] - studio_center[0],
            ldd_center[1] - studio_center[1],
            ldd_center[2] - studio_center[2])


class TransformFixer:
    def __init__(self, geo_bounding: dict, manual_offsets: dict):
        self.geo_bounding = geo_bounding
        self.manual_offsets = manual_offsets

    def fix(self, bone, design_id: str):
        if design_id in self.manual_offsets:
            off = self.manual_offsets[design_id]
        elif design_id in self.geo_bounding:
            off = compute_offset(aabb_center(self.geo_bounding[design_id]), (0, 0, 0))
        else:
            return bone
        new_t = list(bone.transformation)
        new_t[9] = new_t[9] + off[0]
        new_t[10] = new_t[10] + off[1]
        new_t[11] = new_t[11] + off[2]
        return Bone(bone.ref_id, new_t)
