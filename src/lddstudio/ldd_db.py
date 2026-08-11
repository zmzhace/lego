import os
import platform
import struct
from typing import NamedTuple
from xml.dom import minidom

PRIMITIVE_PATH = "/Primitives/"


class LIFEntry:
    def __init__(self, name, offset, size, handle):
        self.name, self.offset, self.size, self.handle = name, offset, size, handle

    def read(self):
        self.handle.seek(self.offset, 0)
        return self.handle.read(self.size)


class LIFReader:
    def __init__(self, path):
        self.filelist = {}
        self.initok = False
        self._packed_offset = 84
        try:
            self.handle = open(path, "rb")
        except OSError:
            return
        if self.handle.read(4) == b"LIFF":
            self._parse(prefix="", offset=self._read_int(72) + 64)
            self.initok = True

    def _parse(self, prefix="", offset=0):
        offset += 36 if prefix == "" else 4
        count = self._read_int(offset=offset)
        for _ in range(count):
            offset += 4
            entry_type = self._read_short(offset=offset)
            offset += 6
            self.handle.seek(offset + 1, 0)
            name = prefix + "/"
            while True:
                t = self.handle.read(1)
                if not t or t == b"\x00":
                    break
                name += t.decode("latin-1")
                self.handle.seek(1, 1)
                offset += 2
            offset += 6
            self._packed_offset += 20
            if entry_type == 1:
                offset = self._parse(prefix=name, offset=offset)
            elif entry_type == 2:
                size = self._read_int(offset=offset) - 20
                self.filelist[name] = LIFEntry(name, self._packed_offset, size, self.handle)
                offset += 24
                self._packed_offset += size
        return offset

    def _read_int(self, offset=0):
        self.handle.seek(offset, 0)
        return int.from_bytes(self.handle.read(4), byteorder="big")

    def _read_short(self, offset=0):
        self.handle.seek(offset, 0)
        return int.from_bytes(self.handle.read(2), byteorder="big")


class LOCReader:
    def __init__(self, data):
        self.values = {}
        if len(data) > 1 and data[0] == 50 and data[1] == 0:
            off = 2
            while off < len(data):
                key = self._next_string(data, off)
                off += len(key) + 1
                value = self._next_string(data, off)
                off += len(value) + 1
                if not key and not value:
                    break
                self.values[key.replace("Material", "")] = value

    @staticmethod
    def _next_string(data, off):
        out = []
        while off < len(data) and data[off] != 0:
            out.append(chr(data[off]))
            off += 1
        return "".join(out)


class MaterialDef(NamedTuple):
    mat_id: str
    r: int
    g: int
    b: int
    a: int
    material_type: str
    name: str


class PrimitiveInfo(NamedTuple):
    design_id: str
    design_name: str
    bounding: dict
    geo_bounding: dict


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _annotation_name(node):
    if node.hasAttribute("designname"):
        return node.getAttribute("designname")
    for child in node.childNodes:
        if child.nodeName == "designname" and child.firstChild:
            return child.firstChild.data
    return ""


def _annotation_aliases(node):
    if node.hasAttribute("aliases"):
        return node.getAttribute("aliases")
    return ""


def _annotation_value(node, attr):
    if node.hasAttribute(attr):
        return node.getAttribute(attr)
    for child in node.childNodes:
        if child.nodeName == attr and child.firstChild:
            return child.firstChild.data
    return ""


def parse_materials_xml(data: bytes) -> dict:
    mats = {}
    doc = minidom.parseString(data)
    for node in doc.firstChild.childNodes:
        if node.nodeName == "Material":
            mid = node.getAttribute("MatID")
            mats[mid] = MaterialDef(
                mat_id=mid,
                r=_to_int(node.getAttribute("Red")),
                g=_to_int(node.getAttribute("Green")),
                b=_to_int(node.getAttribute("Blue")),
                a=_to_int(node.getAttribute("Alpha")),
                material_type=node.getAttribute("MaterialType"),
                name="",
            )
    return mats


def parse_primitive_xml(data: bytes, fallback_id: str = "") -> PrimitiveInfo:
    doc = minidom.parseString(data)
    root = doc.documentElement
    name = ""
    aliases = ""
    design_id = (root.getAttribute("designID") or root.getAttribute("designid")
                 or fallback_id)
    bounding, geo_bounding = {}, {}
    for node in root.childNodes:
        if node.nodeName in ("Annotations", "Annotation"):
            nodes = node.childNodes if node.nodeName == "Annotations" else [node]
            for child in nodes:
                if child.nodeName == "Annotation":
                    name = _annotation_name(child) or name
                    aliases = _annotation_aliases(child) or aliases
        elif node.nodeName == "Bounding":
            for child in node.childNodes:
                if child.nodeName == "AABB":
                    bounding = {k: child.getAttribute(k) for k in
                                ("minX", "minY", "minZ", "maxX", "maxY", "maxZ")}
        elif node.nodeName == "GeometryBounding":
            for child in node.childNodes:
                if child.nodeName == "AABB":
                    geo_bounding = {k: child.getAttribute(k) for k in
                                    ("minX", "minY", "minZ", "maxX", "maxY", "maxZ")}
    if not design_id and aliases:
        design_id = aliases.split(",")[0].strip()
    return PrimitiveInfo(design_id=design_id, design_name=name,
                         bounding=bounding, geo_bounding=geo_bounding)


class LddDatabase:
    def __init__(self, materials, primitive_names, geo_bounding, primitives,
                 filelist=None):
        self.materials = materials
        self.primitive_names = primitive_names
        self.geo_bounding = geo_bounding
        self._primitives = primitives
        self._filelist = filelist or {}

    def primitive(self, path):
        return self._primitives[path]


def find_ldd_db() -> str:
    override = os.environ.get("LDDSTUDIO_LDD_DB")
    if override and os.path.exists(override):
        return override
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    if platform.system() == "Windows":
        candidates = [
            os.path.join(base, "AppData", "Roaming", "LEGO Company",
                         "LEGO Digital Designer", "db"),
            os.path.join(base, "AppData", "Roaming", "LEGO Company",
                         "LEGO Digital Designer", "db.lif"),
        ]
        # portable install on drive roots
        for drive in ("D:", "E:"):
            root = drive + os.sep
            candidates.append(os.path.join(root, "LEGO Digital Designer", "Assets.lif"))
            candidates.append(os.path.join(root, "LEGO Digital Designer", "db"))
            candidates.append(os.path.join(root, "LEGO Digital Designer", "db.lif"))
    elif platform.system() == "Darwin":
        candidates = [
            os.path.join(base, "Library", "Application Support",
                         "LEGO Company", "LEGO Digital Designer", "db"),
            os.path.join(base, "Library", "Application Support",
                         "LEGO Company", "LEGO Digital Designer", "db.lif"),
        ]
    else:
        candidates = []
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def _design_id_from_path(norm_path: str) -> str:
    """'.../Primitives/10058.xml' -> '10058'."""
    base = os.path.basename(norm_path)
    stem, _ext = os.path.splitext(base)
    return stem


def load_ldd_database(db_path: str) -> LddDatabase:
    primitives = {}
    materials = {}
    names = {}
    geob = {}
    if os.path.isdir(db_path):
        for dirpath, _, files in os.walk(db_path):
            for f in files:
                full = os.path.join(dirpath, f)
                norm = "/" + os.path.relpath(full, db_path).replace("\\", "/")
                if f.endswith(".xml"):
                    try:
                        data = open(full, "rb").read()
                        if norm.endswith("/Materials.xml"):
                            materials.update(parse_materials_xml(data))
                        elif "/Primitives/" in norm and "/LOD" not in norm:
                            p = parse_primitive_xml(data, _design_id_from_path(norm))
                            primitives[norm] = p
                            names[p.design_id] = p.design_name
                            if p.geo_bounding:
                                geob[p.design_id] = p.geo_bounding
                    except Exception:
                        continue
        loc = None
        for dirpath, _, files in os.walk(db_path):
            for f in files:
                if f == "localizedStrings.loc":
                    loc = LOCReader(open(os.path.join(dirpath, f), "rb").read())
        if loc:
            for mid, mat in materials.items():
                if mid in loc.values:
                    materials[mid] = MaterialDef(mat.mat_id, mat.r, mat.g, mat.b,
                                                 mat.a, mat.material_type, loc.values[mid])
        return LddDatabase(materials, names, geob, primitives)
    elif os.path.isfile(db_path):
        reader = LIFReader(db_path)
        if not reader.initok:
            return LddDatabase({}, {}, {}, {}, filelist={})
        loc = None
        for name in reader.filelist:
            if name.endswith("localizedStrings.loc"):
                loc = LOCReader(reader.filelist[name].read())
        for name, entry in reader.filelist.items():
            if name.endswith("Materials.xml"):
                try:
                    materials.update(parse_materials_xml(entry.read()))
                except Exception:
                    continue
            elif "/Primitives/" in name and "/LOD" not in name and name.endswith(".xml"):
                try:
                    p = parse_primitive_xml(entry.read(), _design_id_from_path(name))
                    primitives[name] = p
                    names[p.design_id] = p.design_name
                    if p.geo_bounding:
                        geob[p.design_id] = p.geo_bounding
                except Exception:
                    continue
        if loc:
            for mid, mat in materials.items():
                if mid in loc.values:
                    materials[mid] = MaterialDef(mat.mat_id, mat.r, mat.g, mat.b,
                                                 mat.a, mat.material_type, loc.values[mid])
        return LddDatabase(materials, names, geob, primitives)
    return LddDatabase({}, {}, {}, {})
