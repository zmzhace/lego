"""Convert LDD geometry (.g files + primitive XML) into LDraw .dat parts.

LDD stores per-part triangle meshes under ``<db>/Primitives/LOD0/<id>.g``
plus optional ``.g1``, ``.g2`` sub-meshes.  A ``<id>.xml`` primitive provides
the design name and Flex/Bone transforms for sub-meshes.

Units: 1 LDD unit = 25 LDU (LDraw units).  Axes match (Y up).
The converter emits the LDraw triangle format::

    3 <color> x1 y1 z1 x2 y2 z2 x3 y3 z3

with ``<color>`` = 16 (main colour) unless a per-vertex bone/sub-material
mapping indicates otherwise.
"""

import struct

MAGIC = 1111961649  # '10GB'
LDD_TO_LDU = 25.0


class GMesh:
    """One LDD sub-mesh (a .g or .g1/.g2 file)."""

    def __init__(self, positions, faces):
        self.positions = positions          # list of (x, y, z) in LDD units
        self.faces = faces                  # list of (a, b, c) vertex indices


def _parse_g(data):
    """Parse a .g blob -> GMesh.  Returns None when not a valid mesh."""
    if len(data) < 16:
        return None
    magic = int.from_bytes(data[0:4], "little")
    if magic != MAGIC:
        return None
    value_count = int.from_bytes(data[4:8], "little")
    index_count = int.from_bytes(data[8:12], "little")
    face_count = index_count // 3
    options = int.from_bytes(data[12:16], "little")
    off = 16

    def _read_float():
        nonlocal off
        v = struct.unpack_from("<f", data, off)[0]
        off += 4
        return v

    def _read_int():
        nonlocal off
        v = int.from_bytes(data[off:off + 4], "little")
        off += 4
        return v

    try:
        positions = [(_read_float(), _read_float(), _read_float())
                     for _ in range(value_count)]
        normals = [(_read_float(), _read_float(), _read_float())
                   for _ in range(value_count)]
        if (options & 3) == 3:
            textures = [(_read_float(), _read_float()) for _ in range(value_count)]
        faces = [(_read_int(), _read_int(), _read_int())
                 for _ in range(face_count)]
        if (options & 48) == 48:
            num = _read_int()
            off += (num * 4) + (index_count * 4)
            num = _read_int()
            off += (3 * num * 4) + (index_count * 4)
        bone_length = _read_int()
        if bone_length > value_count or bone_length > face_count:
            off += bone_length
            for _ in range(value_count):
                bone_offset = _read_int() + 4
    except (struct.error, IndexError):
        return None
    return GMesh(positions, faces)


class LddGeometry:
    """Combined geometry for one design id (all sub-meshes, transformed)."""

    def __init__(self, design_id, design_name, meshes):
        self.design_id = design_id
        self.design_name = design_name
        self.meshes = meshes  # list of GMesh, already in final coordinates

    def to_ldraw(self, color=16):
        """Return .dat file content (triangles only)."""
        out = ["0 {}".format(self.design_name or self.design_id),
               "0 Name: {}.dat".format(self.design_id),
               "0 !LDRAW_ORG Unofficial_Part",
               "0 !LDDSTUDIO exported from LEGO Digital Designer",
               ""]
        for mesh in self.meshes:
            for a, b, c in mesh.faces:
                pa, pb, pc = mesh.positions[a], mesh.positions[b], mesh.positions[c]
                line = "3 {} {:g} {:g} {:g} {:g} {:g} {:g} {:g} {:g} {:g}".format(
                    color,
                    pa[0] * LDD_TO_LDU, pa[1] * LDD_TO_LDU, pa[2] * LDD_TO_LDU,
                    pb[0] * LDD_TO_LDU, pb[1] * LDD_TO_LDU, pb[2] * LDD_TO_LDU,
                    pc[0] * LDD_TO_LDU, pc[1] * LDD_TO_LDU, pc[2] * LDD_TO_LDU)
                out.append(line)
        out.append("0")
        return "\n".join(out)


def load_ldd_geometry(db, design_id):
    """Load and return LddGeometry for a design id from an LddDatabase.

    The database object must expose a ``read_entry(name)`` method returning
    bytes (the LIF filelist) — we use ``_primitives`` and ``filelist``.
    """
    primitives = getattr(db, "_primitives", {})
    filelist = getattr(db, "_filelist", None)
    if filelist is None:
        return None
    meshes = []
    idx = 0
    while True:
        base = "/Primitives/LOD0/{}.g{}".format(design_id, idx if idx else "")
        entry = filelist.get(base)
        if entry is None:
            break
        data = entry.read() if hasattr(entry, "read") else entry
        mesh = _parse_g(data)
        if mesh is not None:
            meshes.append(mesh)
        idx += 1
    if not meshes:
        return None
    name = ""
    p = primitives.get("/Primitives/{}.xml".format(design_id))
    if p is not None:
        name = getattr(p, "design_name", "") or ""
    return LddGeometry(design_id, name, meshes)
