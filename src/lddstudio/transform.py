import math

from lddstudio.lxfml_model import Bone


def aabb_center(bounding: dict) -> tuple:
    return ((float(bounding["minX"]) + float(bounding["maxX"])) / 2,
            (float(bounding["minY"]) + float(bounding["maxY"])) / 2,
            (float(bounding["minZ"]) + float(bounding["maxZ"])) / 2)


def compute_offset(ldd_center, studio_center) -> tuple:
    return (ldd_center[0] - studio_center[0],
            ldd_center[1] - studio_center[1],
            ldd_center[2] - studio_center[2])


def rotation_matrix(rx_deg, ry_deg, rz_deg):
    """Build a 3x3 rotation matrix from Euler angles (degrees), order Z*Y*X.

    Returns a tuple of 9 floats in row-major order.
    """
    rx, ry, rz = (math.radians(rx_deg), math.radians(ry_deg),
                  math.radians(rz_deg))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    # R = Rz * Ry * Rx
    a00 = cz * cy
    a01 = cz * sy * sx - sz * cx
    a02 = cz * sy * cx + sz * sx
    a10 = sz * cy
    a11 = sz * sy * sx + cz * cx
    a12 = sz * sy * cx - cz * sx
    a20 = -sy
    a21 = cy * sx
    a22 = cy * cx
    return (a00, a01, a02, a10, a11, a12, a20, a21, a22)


def _mat3_mul(a, b):
    """Multiply two 3x3 row-major tuples."""
    return (
        a[0]*b[0] + a[1]*b[3] + a[2]*b[6],
        a[0]*b[1] + a[1]*b[4] + a[2]*b[7],
        a[0]*b[2] + a[1]*b[5] + a[2]*b[8],
        a[3]*b[0] + a[4]*b[3] + a[5]*b[6],
        a[3]*b[1] + a[4]*b[4] + a[5]*b[7],
        a[3]*b[2] + a[4]*b[5] + a[5]*b[8],
        a[6]*b[0] + a[7]*b[3] + a[8]*b[6],
        a[6]*b[1] + a[7]*b[4] + a[8]*b[7],
        a[6]*b[2] + a[7]*b[5] + a[8]*b[8],
    )


def _mat3_vec(m, v):
    """Multiply a 3x3 row-major matrix by a 3-vector."""
    return (m[0]*v[0] + m[1]*v[1] + m[2]*v[2],
            m[3]*v[0] + m[4]*v[1] + m[5]*v[2],
            m[6]*v[0] + m[7]*v[1] + m[8]*v[2])


class TransformFixer:
    """Fix bone transforms so Studio renders LDD parts in the same place.

    Two correction sources are combined:
      1. ``offsets`` (from ldraw_lxfml_mapping.json): per-designID rotation
         (degrees) + translation (LDU) that converts LDD-local geometry into
         Studio/LDraw geometry.  Applied as
         ``T_studio = M_offset * T_ldd``.
      2. ``geo_bounding`` fallback (from the LDD database): AABB-center offset
         used when no explicit offset exists.
    """

    def __init__(self, geo_bounding=None, manual_offsets=None, offsets=None):
        self.geo_bounding = geo_bounding or {}
        self.manual_offsets = manual_offsets or {}
        self.offsets = offsets or {}

    def fix(self, bone, design_id: str) -> Bone:
        if design_id in self.manual_offsets:
            return self._apply_manual(bone, self.manual_offsets[design_id])
        off = self.offsets.get(design_id)
        if off is not None:
            return self._apply_offset(bone, off)
        if design_id in self.geo_bounding:
            return self._apply_geo(bone, design_id)
        return bone

    def _apply_offset(self, bone, off) -> Bone:
        rot = rotation_matrix(off.rx, off.ry, off.rz)
        t = list(bone.transformation)
        rot_old = tuple(t[0:9])
        trans_old = tuple(t[9:12])
        new_rot = _mat3_mul(rot, rot_old)
        new_trans = tuple(x + y for x, y in zip(
            _mat3_vec(rot, trans_old), (off.tx, off.ty, off.tz)))
        new_t = list(new_rot) + list(new_trans)
        return Bone(bone.ref_id, new_t)

    def _apply_manual(self, bone, offset) -> Bone:
        # manual_offsets entries are (tx, ty, tz) tuples added directly
        if len(offset) == 3:
            new_t = list(bone.transformation)
            new_t[9] += offset[0]
            new_t[10] += offset[1]
            new_t[11] += offset[2]
            return Bone(bone.ref_id, new_t)
        return self._apply_offset(bone, offset)

    def _apply_geo(self, bone, design_id: str) -> Bone:
        off = compute_offset(aabb_center(self.geo_bounding[design_id]), (0, 0, 0))
        new_t = list(bone.transformation)
        new_t[9] += off[0]
        new_t[10] += off[1]
        new_t[11] += off[2]
        return Bone(bone.ref_id, new_t)
