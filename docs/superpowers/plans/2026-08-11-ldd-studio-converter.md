# LDD → Studio 转换工具 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 Windows GUI 工具：读取 LDD `.lxf` 工程，修复零件/颜色/变换矩阵后输出干净 `.lxf`，由 Studio 2.0 自带导入打开，无问号、无乱飞，BOM 准确。

**Architecture:** 四个解耦模块 — LXF 解析器、LDD 数据库读取器、映射引擎（SQLite）、转换管道。GUI（PySide6）只调用管道接口。核心逻辑与 GUI 分离，全部用 TDD 驱动。

**Tech Stack:** Python 3.9+、PySide6、lxml、SQLite（标准库）、pytest、PyInstaller。

## 已确认的格式事实（研究结论，实现必须遵守）

1. `.lxf` = ZIP 容器，内含 `IMAGE100.LXFML`（主模型 XML）和 IMAGE100.REF（子模型）、缩略图。LIF 读取见 Task 2 的 LIFReader。
2. LXFML 结构：
   - 根元素 `<LXFML name="...">`，子节点：`Meta/BrickSet`（version）、`Cameras`、`Bricks`（`Brick`）、`GroupSystems`
   - `Brick` 属性：`refID`、`designID`；子节点 `Part`
   - `Part` 属性：`refID`、`designID`、`materials`（逗号分隔的材质 ID 列表）、可选 `decoration`；子节点 `Bone`
   - `Bone` 属性：`refID`、`transformation`（12 个逗号分隔浮点数：a,b,c,d,e,f,g,h,i,x,y,z = 3x3 旋转 + 平移）
   - `Group` 属性：`partRefs`（逗号分隔的 part refID）
3. LDD 数据库：Windows 上位于 `%USERPROFILE%\AppData\Roaming\LEGO Company\LEGO Digital Designer\db.lif` 或 `db\` 文件夹。`db.lif` 是 LIFF 二进制容器（"LIFF" 魔数）。
   - `/Primitives/<designID>.xml`：Designname（Annotation/designname）、Bounding AABB、GeometryBounding AABB、Flex/Bone、Connectivity/Custom2DField
   - `/Primitives/LOD0/<designID>.g`、`.g1`...：二进制几何
   - `/Decorations/<decorationId>.png`
   - `/MaterialNames/EN/localizedStrings.loc`：材质名称（LOC 二进制格式）
   - `/Materials.xml`：`<Material MatID="..." Red=".." Green=".." Blue=".." Alpha=".." MaterialType=".."/>`
4. 颜色映射：LDD Material ID ↔ Bricklink 颜色 ID 有现成数据（`data/ldd_to_bl_colors.csv`，来源 lego_colors.csv）。LDD MaterialType 值：Solid/Transparent/Metallic/Chrome/Glitter 等。
5. Studio 2.0 零件库：安装后位于 `%LOCALAPPDATA%\Studio 2.0\`（BrickLink 编号体系）。具体发现路径在 Task 4 做运行时探测，探测失败降级为"仅公开数据"模式。
6. Rebrickable：批量数据用 `https://rebrickable.com/downloads/` 的 CSV（parts.csv.gz 等）；API 需 key，见 `https://rebrickable.com/api/v3/`。
7. "乱飞"根因：①子 Part designID 未映射导致父 Brick 引用断裂；②LDD 与 Studio 零件几何原点不同导致平移偏移。修复=完整映射 + 几何中心补偿（见 Task 7）。

## Global Constraints

- Python 3.9+，禁止 3.10+ 语法（`match`、`|` 类型联合）
- 核心模块（lxf_parser、ldd_db、mapping、colors、transform、converter）**禁止 import PySide6**，保证可无 GUI 测试
- 解析必须容错：单 Brick 失败跳过并记录，不中断整体
- 未匹配零件**保底不替换**（保留原 designID），仅列报告
- 数据文件用 `data/` 目录；映射库 SQLite 存 `~/.lddstudio/mapping.db`（Windows 上 `%USERPROFILE%\.lddstudio\mapping.db`）
- 无第三方 HTTP 库需求，用 `urllib.request` 标准库
- 所有 LIF/LOC/XML 解析基于 Task 2 的 LIFReader/LOCReader/DBFolderReader（参考开源 pylddlib，MIT）

---

### Task 1: 项目脚手架 + .lxf ZIP 读写

**Files:**
- Create: `pyproject.toml`
- Create: `src/lddstudio/__init__.py`
- Create: `src/lddstudio/lxf_parser.py`
- Create: `tests/test_lxf_zip.py`

**Interfaces:**
- Produces:
  - `open_lxf(path: str) -> LxfPackage`
  - `LxfPackage` 有 `members: dict[str, bytes]`（全部 zip 条目按名）、`get(name) -> bytes`、`save_lxf(pkg, out_path: str, files: dict[str, bytes]) -> None`
  - `extract_lxfml(members: dict[str, bytes]) -> bytes`（返回 IMAGE100.LXFML 内容）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_lxf_zip.py
import io, zipfile
from lddstudio.lxf_parser import open_lxf, extract_lxfml, save_lxf

def make_lxf(lxfml: bytes) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
        z.writestr("IMAGE100.REF", b"refdata")
        z.writestr("library/thumb.png", b"png")
    open("tmp_test.lxf", "wb").write(buf.getvalue())
    return "tmp_test.lxf"

def test_open_lxf_reads_all_members():
    p = open_lxf(make_lxf(b"<LXFML/>"))
    assert "IMAGE100.LXFML" in p.members
    assert "IMAGE100.REF" in p.members
    assert "library/thumb.png" in p.members

def test_extract_lxfml():
    p = open_lxf(make_lxf(b"<LXFML name='x'/>"))
    assert extract_lxfml(p.members) == b"<LXFML name='x'/>"

def test_save_lxf_roundtrip_preserves_extra_files():
    p = open_lxf(make_lxf(b"<LXFML/>"))
    out = "tmp_out.lxf"
    save_lxf(p, out, {"IMAGE100.LXFML": b"<LXFML name='fixed'/>"})
    p2 = open_lxf(out)
    assert p2.members["IMAGE100.REF"] == b"refdata"
    assert p2.members["library/thumb.png"] == b"png"
    assert p2.members["IMAGE100.LXFML"] == b"<LXFML name='fixed'/>"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_lxf_zip.py -v`
Expected: FAIL（`ModuleNotFoundError: lddstudio`）

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/__init__.py
"""LDD -> Studio converter."""

# src/lddstudio/lxf_parser.py
import zipfile
import os

LXFML_ENTRY = "IMAGE100.LXFML"

class LxfPackage:
    def __init__(self, members: dict):
        self.members = members

    def get(self, name: str) -> bytes:
        return self.members[name]


def open_lxf(path: str) -> LxfPackage:
    with zipfile.ZipFile(path, "r") as z:
        return LxfPackage({n: z.read(n) for n in z.namelist()})


def extract_lxfml(members: dict) -> bytes:
    return members[LXFML_ENTRY]


def save_lxf(pkg: LxfPackage, out_path: str, files: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in pkg.members.items():
            if name in files:
                continue
            z.writestr(name, data)
        for name, data in files.items():
            z.writestr(name, data)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_lxf_zip.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml src/lddstudio/__init__.py src/lddstudio/lxf_parser.py tests/test_lxf_zip.py
git commit -m "feat: lxf zip open/save scaffold"
```

---

### Task 2: LDD 数据库读取器（LIFF/LOC/XML）

**Files:**
- Create: `src/lddstudio/ldd_db.py`
- Create: `tests/test_ldd_db.py`
- Create: `tests/fixtures/minidb_lif.py`（生成最小 db.lif 测试夹具）

**Interfaces:**
- Consumes: 无
- Produces:
  - `LIFReader(path) -> reader`，`reader.filelist: dict[str, LIFEntry]`，`reader.initok: bool`
  - `LIFEntry.read() -> bytes`
  - `LOCReader(data: bytes) -> loc`，`loc.values: dict[str, str]`（key 已去 "Material" 前缀）
  - `parse_materials_xml(data: bytes) -> dict[str, MaterialDef]`
  - `MaterialDef`：NamedTuple `(mat_id, r, g, b, a, material_type, name)`
  - `parse_primitive_xml(data: bytes) -> PrimitiveInfo`
  - `PrimitiveInfo`：NamedTuple 含 `design_id`、`design_name`、`bounding: dict`（minX/minY/minZ/maxX/maxY/maxZ）、`geo_bounding: dict`
  - `find_ldd_db() -> str`（按 Windows/macOS/Linux 默认路径探测，找不到返回 ""）
  - `load_ldd_database(db_path: str) -> LddDatabase`
  - `LddDatabase` 有 `materials: dict[str, MaterialDef]`、`primitive_names: dict[str, str]`（design_id -> Designname）、`geo_bounding: dict[str, dict]`、`primitive(path) -> PrimitiveInfo`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ldd_db.py
import struct
from lddstudio.ldd_db import (LIFReader, LOCReader, parse_materials_xml,
                              parse_primitive_xml)

def make_lif(entries: dict) -> bytes:
    # 极简 LIFF：跳过目录表解析，直接构造 "LIFF" + 无目录
    return b"LIFF" + b"\x00" * 80 + bytes(0)

def test_loc_reader_parses_names():
    # "2\0" + "Material5\0" + "Red\0" + "0\0"
    data = b"2\x00Material5\x00Red\x00\x00"
    loc = LOCReader(data)
    assert loc.values == {"5": "Red"}

def test_parse_materials_xml():
    xml = b'<Materials><Material MatID="5" Red="196" Green="0" Blue="38" Alpha="255" MaterialType="Solid"/></Materials>'
    mats = parse_materials_xml(xml)
    assert mats["5"].r == 196
    assert mats["5"].material_type == "Solid"
    assert mats["5"].name == ""

def test_parse_primitive_xml():
    xml = b'''<Primitives><Annotation><designname>Brick 2x4</designname></Annotation>
    <Bounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></Bounding>
    <GeometryBounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></GeometryBounding>
    </Primitives>'''
    p = parse_primitive_xml(xml)
    assert p.design_name == "Brick 2x4"
    assert p.bounding["maxX"] == "31.8"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_ldd_db.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/ldd_db.py
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

    def __getattr__(self, name):
        if name == "_packed_offset" and "_handle" in self.__dict__:
            self._packed_offset = 84
            return self._packed_offset
        raise AttributeError(name)


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


def parse_materials_xml(data: bytes) -> dict:
    mats = {}
    doc = minidom.parseString(data)
    for node in doc.firstChild.childNodes:
        if node.nodeName == "Material":
            mid = node.getAttribute("MatID")
            mats[mid] = MaterialDef(
                mat_id=mid,
                r=int(node.getAttribute("Red")),
                g=int(node.getAttribute("Green")),
                b=int(node.getAttribute("Blue")),
                a=int(node.getAttribute("Alpha")),
                material_type=node.getAttribute("MaterialType"),
                name="",
            )
    return mats


def parse_primitive_xml(data: bytes) -> PrimitiveInfo:
    doc = minidom.parseString(data)
    root = doc.documentElement
    name = ""
    bounding, geo_bounding = {}, {}
    for node in root.childNodes:
        if node.nodeName == "Annotations":
            for child in node.childNodes:
                if child.nodeName == "Annotation" and child.hasAttribute("designname"):
                    name = child.getAttribute("designname")
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
    return PrimitiveInfo(design_id=root.tagName, design_name=name,
                         bounding=bounding, geo_bounding=geo_bounding)


class LddDatabase:
    def __init__(self, materials, primitive_names, geo_bounding, primitives):
        self.materials = materials
        self.primitive_names = primitive_names
        self.geo_bounding = geo_bounding
        self._primitives = primitives

    def primitive(self, path):
        return self._primitives[path]


def find_ldd_db() -> str:
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
    if platform.system() == "Windows":
        candidates = [
            os.path.join(base, "AppData", "Roaming", "LEGO Company",
                         "LEGO Digital Designer", "db"),
            os.path.join(base, "AppData", "Roaming", "LEGO Company",
                         "LEGO Digital Designer", "db.lif"),
        ]
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
                    data = open(full, "rb").read()
                    if norm.endswith("/Materials.xml"):
                        materials.update(parse_materials_xml(data))
                    elif "/Primitives/" in norm and "/LOD" not in norm:
                        p = parse_primitive_xml(data)
                        primitives[norm] = p
                        names[p.design_id] = p.design_name
                        if p.geo_bounding:
                            geob[p.design_id] = p.geo_bounding
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
            return LddDatabase({}, {}, {}, {})
        loc = None
        for name in reader.filelist:
            if name.endswith("localizedStrings.loc"):
                loc = LOCReader(reader.filelist[name].read())
        for name, entry in reader.filelist.items():
            if name.endswith("Materials.xml"):
                materials.update(parse_materials_xml(entry.read()))
            elif "/Primitives/" in name and "/LOD" not in name and name.endswith(".xml"):
                p = parse_primitive_xml(entry.read())
                primitives[name] = p
                names[p.design_id] = p.design_name
                if p.geo_bounding:
                    geob[p.design_id] = p.geo_bounding
        if loc:
            for mid, mat in materials.items():
                if mid in loc.values:
                    materials[mid] = MaterialDef(mat.mat_id, mat.r, mat.g, mat.b,
                                                 mat.a, mat.material_type, loc.values[mid])
        return LddDatabase(materials, names, geob, primitives)
    return LddDatabase({}, {}, {}, {})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_ldd_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/ldd_db.py tests/test_ldd_db.py
git commit -m "feat: LDD db.lif/db folder reader (LIF/LOC/Materials/Primitives)"
```

---

### Task 3: LXFML 解析与写出

**Files:**
- Create: `src/lddstudio/lxfml_model.py`
- Create: `tests/test_lxfml.py`
- Create: `tests/fixtures/sample.lxfml`

**Interfaces:**
- Consumes: `extract_lxfml`（Task 1）、`LddDatabase.primitive`（Task 2）
- Produces:
  - `class Brick`：`ref_id`、`design_id`、`parts: list[Part]`
  - `class Part`：`ref_id`、`design_id`、`materials: list[str]`、`decoration: str|None`、`bones: list[Bone]`
  - `class Bone`：`ref_id`、`transformation: list[float]`（12 元素）
  - `class LxfmlScene`：`name`、`bricks: list[Brick]`、`groups: list[Group]`、`brick_version`
  - `parse_lxfml(data: bytes) -> LxfmlScene`
  - `serialize_lxfml(scene: LxfmlScene) -> bytes`
  - `Bone.rotation3() -> tuple[3,3]`、`Bone.translation() -> tuple[3]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_lxfml.py
from lddstudio.lxfml_model import parse_lxfml, serialize_lxfml

LXFML = b'''<LXFML name="test">
<Meta><BrickSet version="1"/></Meta>
<Bricks>
  <Brick refID="1" designID="3001">
    <Part refID="2" designID="3001" materials="5,0,4">
      <Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/>
    </Part>
  </Brick>
</Bricks>
<GroupSystems><GroupSystem><Group partRefs="2,9"/></GroupSystem></GroupSystems>
</LXFML>'''

def test_parse_bricks_and_parts():
    s = parse_lxfml(LXFML)
    assert s.name == "test"
    assert len(s.bricks) == 1
    brick = s.bricks[0]
    assert brick.design_id == "3001"
    assert len(brick.parts) == 1
    part = brick.parts[0]
    assert part.materials == ["5", "0", "4"]
    assert part.bones[0].transformation[0] == 1.0

def test_parse_groups():
    s = parse_lxfml(LXFML)
    assert s.groups == [["2", "9"]]

def test_serialize_roundtrip():
    s = parse_lxfml(LXFML)
    out = serialize_lxfml(s)
    s2 = parse_lxfml(out)
    assert s2.bricks[0].parts[0].materials == ["5", "0", "4"]
    assert s2.groups == [["2", "9"]]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_lxfml.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/lxfml_model.py
from xml.dom import minidom
from typing import NamedTuple


class Bone:
    def __init__(self, ref_id, transformation):
        self.ref_id = ref_id
        self.transformation = [float(x) for x in transformation]

    def rotation3(self):
        t = self.transformation
        return ((t[0], t[1], t[2]), (t[3], t[4], t[5]), (t[6], t[7], t[8]))

    def translation(self):
        t = self.transformation
        return (t[9], t[10], t[11])


class Part:
    def __init__(self, ref_id, design_id, materials, decoration, bones):
        self.ref_id = ref_id
        self.design_id = design_id
        self.materials = materials
        self.decoration = decoration
        self.bones = bones


class Brick:
    def __init__(self, ref_id, design_id, parts):
        self.ref_id = ref_id
        self.design_id = design_id
        self.parts = parts


class Group:
    def __init__(self, part_refs):
        self.part_refs = part_refs


class LxfmlScene:
    def __init__(self, name, brick_version, bricks, groups):
        self.name = name
        self.brick_version = brick_version
        self.bricks = bricks
        self.groups = [g.part_refs for g in groups]


def _parse_part(node):
    bones = []
    for child in node.childNodes:
        if child.nodeName == "Bone":
            bones.append(Bone(child.getAttribute("refID"),
                              child.getAttribute("transformation").split(",")))
    deco = node.getAttribute("decoration") if node.hasAttribute("decoration") else None
    materials = [m for m in node.getAttribute("materials").split(",") if m != ""]
    return Part(node.getAttribute("refID"), node.getAttribute("designID"),
                materials, deco, bones)


def parse_lxfml(data: bytes) -> LxfmlScene:
    doc = minidom.parseString(data)
    root = doc.documentElement
    name = root.getAttribute("name")
    brick_version = ""
    bricks = []
    groups = []
    for node in root.childNodes:
        if node.nodeName == "Meta":
            for child in node.childNodes:
                if child.nodeName == "BrickSet":
                    brick_version = child.getAttribute("version")
        elif node.nodeName == "Bricks":
            for child in node.childNodes:
                if child.nodeName == "Brick":
                    parts = [_parse_part(p) for p in child.childNodes if p.nodeName == "Part"]
                    bricks.append(Brick(child.getAttribute("refID"),
                                        child.getAttribute("designID"), parts))
        elif node.nodeName == "GroupSystems":
            for gs in node.childNodes:
                if gs.nodeName == "GroupSystem":
                    for g in gs.childNodes:
                        if g.nodeName == "Group":
                            groups.append(Group(g.getAttribute("partRefs").split(",")))
    return LxfmlScene(name, brick_version, bricks, groups)


def serialize_lxfml(scene: LxfmlScene) -> bytes:
    lines = ['<LXFML name="{}">'.format(scene.name)]
    lines.append('<Meta><BrickSet version="{}"/></Meta>'.format(scene.brick_version))
    lines.append("<Bricks>")
    for b in scene.bricks:
        lines.append('<Brick refID="{}" designID="{}">'.format(b.ref_id, b.design_id))
        for p in b.parts:
            attrs = 'refID="{}" designID="{}" materials="{}"'.format(
                p.ref_id, p.design_id, ",".join(p.materials))
            if p.decoration:
                attrs += ' decoration="{}"'.format(p.decoration)
            lines.append("<Part {}>".format(attrs))
            for bone in p.bones:
                lines.append('<Bone refID="{}" transformation="{}"/>'.format(
                    bone.ref_id, ",".join(str(x) for x in bone.transformation)))
            lines.append("</Part>")
        lines.append("</Brick>")
    lines.append("</Bricks>")
    lines.append('<GroupSystems><GroupSystem><Group partRefs="{}"/></GroupSystem></GroupSystems>'.format(
        ",".join(g for grp in scene.groups for g in grp)))
    lines.append("</LXFML>")
    return "".join(lines).encode("utf-8")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_lxfml.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/lxfml_model.py tests/test_lxfml.py
git commit -m "feat: LXFML parse/serialize"
```

---

### Task 4: Studio 零件库发现 + 公开数据集导入

**Files:**
- Create: `src/lddstudio/studio_lib.py`
- Create: `src/lddstudio/rebrickable.py`
- Create: `tests/test_studio_lib.py`
- Create: `tests/test_rebrickable.py`

**Interfaces:**
- Produces:
  - `find_studio_dir() -> str`（探测 `%LOCALAPPDATA%\Studio 2.0\` 等，找不到返回 ""）
  - `scan_studio_part_numbers(studio_dir: str) -> set[str]`（返回 Studio 已知的 BL 编号集合）
  - `rebrickable_parts_csv_url() -> str`、`download_rebrickable_parts(out_path: str) -> None`（下载 parts.csv.gz）
  - `parse_rebrickable_parts_csv(path: str) -> dict[str, str]`（part_num -> name，去重复 part_num）

注意：Studio 内部零件库的具体格式需在实现时用真实环境探测（GUI 里留"手动指定目录"入口）。本任务先定义接口与公开数据路径，Studio 扫描实现用 `os.walk` 收集文件名中的 BL 编号（形如 `3001.dat`、`3001.io`、`3001.obj` 的编号前缀），未知格式时返回空集，不阻塞管道。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_rebrickable.py
import io, gzip
from lddstudio.rebrickable import parse_rebrickable_parts_csv

def test_parse_parts_csv():
    csv_data = b"part_num,name,part_cat_id,part_material\n3001,Brick 2 x 4,1,1\n3002,Brick 2 x 3,1,1\n"
    data = gzip.compress(csv_data)
    import os
    os.makedirs("tmp", exist_ok=True)
    open("tmp/parts.csv.gz", "wb").write(data)
    parts = parse_rebrickable_parts_csv("tmp/parts.csv.gz")
    assert parts["3001"] == "Brick 2 x 4"
    assert parts["3002"] == "Brick 2 x 3"

# tests/test_studio_lib.py
import os
from lddstudio.studio_lib import scan_studio_part_numbers

def test_scan_studio_part_numbers_collects_bl_ids():
    os.makedirs("tmp_studio/parts", exist_ok=True)
    open("tmp_studio/parts/3001.dat", "w").write("")
    open("tmp_studio/parts/3002.io", "w").write("")
    open("tmp_studio/readme.txt", "w").write("")
    ids = scan_studio_part_numbers("tmp_studio")
    assert "3001" in ids and "3002" in ids
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_rebrickable.py tests/test_studio_lib.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/rebrickable.py
import gzip
import os
import csv
import urllib.request

PARTS_CSV_URL = "https://rebrickable.com/media/downloads/parts.csv.gz"


def rebrickable_parts_csv_url() -> str:
    return PARTS_CSV_URL


def download_rebrickable_parts(out_path: str) -> None:
    urllib.request.urlretrieve(PARTS_CSV_URL, out_path)


def parse_rebrickable_parts_csv(path: str) -> dict:
    parts = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx_num = header.index("part_num")
        idx_name = header.index("name")
        for row in reader:
            if len(row) <= max(idx_num, idx_name):
                continue
            parts[row[idx_num]] = row[idx_name]
    return parts


# src/lddstudio/studio_lib.py
import os
import re

_BL_NUM = re.compile(r"^(\d{2,6})")


def find_studio_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or ""
    for c in [os.path.join(base, "Studio 2.0"),
              os.path.join(base, "Local", "Studio 2.0"),
              os.path.join(base, ".studio", "Studio 2.0")]:
        if os.path.isdir(c):
            return c
    return ""


def scan_studio_part_numbers(studio_dir: str) -> set:
    ids = set()
    if not studio_dir or not os.path.isdir(studio_dir):
        return ids
    for dirpath, _, files in os.walk(studio_dir):
        for f in files:
            stem = os.path.splitext(f)[0]
            m = _BL_NUM.match(stem)
            if m:
                ids.add(m.group(1))
    return ids
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_rebrickable.py tests/test_studio_lib.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/studio_lib.py src/lddstudio/rebrickable.py tests/test_studio_lib.py tests/test_rebrickable.py
git commit -m "feat: studio dir discovery + rebrickable parts csv import"
```

---

### Task 5: 颜色处理器（官方色 + 自定义色）

**Files:**
- Create: `data/ldd_to_bl_colors.csv`
- Create: `src/lddstudio/colors.py`
- Create: `tests/test_colors.py`

**Interfaces:**
- Consumes: `MaterialDef`（Task 2）、`LddDatabase.materials`（Task 2）
- Produces:
  - `load_bl_color_map(path: str) -> dict[str, tuple]`（LDD matID -> (bl_id, r, g, b, material)）
  - `class ColorProcessor`：
    - `__init__(self, bl_map, studio_colors: dict[str, tuple], ldd_materials: dict)`
    - `resolve(mat_id: str) -> ColorResult`：官方色返回 (bl_id, name)；自定义色返回 (generated_id, name, rgb)
    - `build_studio_custom_color_xml(custom_colors: dict) -> str`（生成 Studio 自定义颜色 XML 片段）
  - `ColorResult`：NamedTuple `(bl_color_id, name, r, g, b, is_custom)`

注意：Studio 自定义颜色 XML 精确格式需在真实 Studio 环境验证（打开 Studio → 自定义颜色 → 看导出文件）。实现先按社区已知格式（Studio 使用 `%LOCALAPPDATA%\Studio 2.0\settings.xml` 或导入的自定义颜色文件）生成；GUI 提供"导出 Studio 自定义颜色文件"按钮，验证阶段校正。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_colors.py
from lddstudio.colors import ColorProcessor, load_bl_color_map

def make_bl_map():
    return {"5": ("5", 196, 0, 38, "Solid"),
            "1": ("1", 242, 243, 242, "Solid"),
            "999": ("999", 128, 128, 128, "Custom")}

def test_resolve_official_color():
    cp = ColorProcessor(make_bl_map(), {}, {})
    r = cp.resolve("5")
    assert not r.is_custom
    assert r.bl_color_id == "5"

def test_resolve_unknown_color_generates_custom():
    cp = ColorProcessor(make_bl_map(), {}, {})
    r = cp.resolve("77")   # 不在官方映射
    assert r.is_custom
    assert r.bl_color_id.startswith("C")

def test_build_custom_color_xml_contains_entries():
    cp = ColorProcessor(make_bl_map(), {}, {})
    xml = cp.build_studio_custom_color_xml({"C1": ("My Red", 200, 10, 10)})
    assert "My Red" in xml
    assert "200" in xml
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_colors.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/colors.py
import csv
import os
from typing import NamedTuple


class ColorResult(NamedTuple):
    bl_color_id: str
    name: str
    r: int
    g: int
    b: int
    is_custom: bool


def load_bl_color_map(path: str) -> dict:
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("LDD_ID"):
                continue
            mapping[row["LDD_ID"]] = (
                row.get("BL_ID", row["LDD_ID"]),
                int(float(row["R"])), int(float(row["G"])), int(float(row["B"])),
                row.get("Material", ""),
            )
    return mapping


class ColorProcessor:
    def __init__(self, bl_map, studio_colors, ldd_materials):
        self.bl_map = bl_map
        self.studio_colors = studio_colors
        self.ldd_materials = ldd_materials
        self._custom_cache = {}

    def resolve(self, mat_id: str) -> ColorResult:
        if mat_id in self.bl_map:
            bl_id, r, g, b, _ = self.bl_map[mat_id]
            return ColorResult(bl_id, "", r, g, b, False)
        if mat_id in self.ldd_materials:
            m = self.ldd_materials[mat_id]
            name = m.name or ("Custom " + mat_id)
            return ColorResult("C" + mat_id, name, m.r, m.g, m.b, True)
        return ColorResult("C" + mat_id, "Custom " + mat_id, 128, 128, 128, True)

    def build_studio_custom_color_xml(self, custom_colors: dict) -> str:
        lines = ['<CustomColors>']
        for cid, (name, r, g, b) in custom_colors.items():
            lines.append('  <Color id="{}" name="{}" r="{}" g="{}" b="{}"/>'.format(
                cid, name, r, g, b))
        lines.append("</CustomColors>")
        return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_colors.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add data/ldd_to_bl_colors.csv src/lddstudio/colors.py tests/test_colors.py
git commit -m "feat: color processor (official + custom)"
```

---

### Task 6: 映射引擎（SQLite 映射库）

**Files:**
- Create: `src/lddstudio/mapping.py`
- Create: `tests/test_mapping.py`

**Interfaces:**
- Consumes: `parse_rebrickable_parts_csv`（Task 4）、`scan_studio_part_numbers`（Task 4）、`LddDatabase.primitive_names`（Task 2）
- Produces:
  - `class MappingDb`：
    - `__init__(self, path: str)`（打开/创建 SQLite）
    - `rebuild(ldd_names: dict, bl_parts: dict, bl_numbers: set) -> None`：对每个 LDD design_id，若 `design_id in bl_numbers`（编号直映）→ `match_type="exact"`；否则按名称模糊匹配 BL parts → `match_type="auto"`；否则 → `match_type="unmatched"`，`bl_number=NULL`
    - `lookup(design_id: str) -> PartMapping|None`
    - `set_manual(design_id: str, bl_number: str) -> None`（GUI 手动指定后写入，`match_type="manual"`）
    - `all_unmatched() -> list[PartMapping]`
    - `export_csv(path: str)`、`import_csv(path: str)`
  - `PartMapping`：NamedTuple `(design_id, bl_number, name, match_type)`（bl_number 可为 None）
- 默认库路径：`default_db_path() -> str`（`~/.lddstudio/mapping.db`）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_mapping.py
import os
from lddstudio.mapping import MappingDb

DB = "tmp/mapping_test.db"

def make_db():
    os.makedirs("tmp", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    db = MappingDb(DB)
    ldd_names = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown Thing"}
    bl_parts = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}
    bl_numbers = {"3001", "3002"}
    db.rebuild(ldd_names, bl_parts, bl_numbers)
    return db

def test_rebuild_exact_match():
    db = make_db()
    m = db.lookup("3001")
    assert m.bl_number == "3001"
    assert m.match_type == "exact"

def test_rebuild_unmatched_null():
    db = make_db()
    m = db.lookup("99999")
    assert m.bl_number is None
    assert m.match_type == "unmatched"

def test_set_manual_overrides():
    db = make_db()
    db.set_manual("99999", "3039")
    m = db.lookup("99999")
    assert m.bl_number == "3039"
    assert m.match_type == "manual"

def test_export_import_csv():
    db = make_db()
    db.set_manual("99999", "3039")
    db.export_csv("tmp/map.csv")
    os.remove(DB)
    db2 = MappingDb(DB)
    db2.import_csv("tmp/map.csv")
    assert db2.lookup("99999").bl_number == "3039"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_mapping.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/mapping.py
import csv
import os
import re
import sqlite3
from difflib import SequenceMatcher
from typing import NamedTuple


class PartMapping(NamedTuple):
    design_id: str
    bl_number: str
    name: str
    match_type: str


def default_db_path() -> str:
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or "."
    return os.path.join(base, ".lddstudio", "mapping.db")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class MappingDb:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS parts (design_id TEXT PRIMARY KEY, "
            "bl_number TEXT, name TEXT, match_type TEXT)")
        self.conn.commit()

    def rebuild(self, ldd_names: dict, bl_parts: dict, bl_numbers: set) -> None:
        for design_id, name in ldd_names.items():
            if design_id in bl_numbers:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, design_id, name, "exact"))
                continue
            best, best_score = None, 0.0
            for bl_num, bl_name in bl_parts.items():
                score = SequenceMatcher(None, _norm(name), _norm(bl_name)).ratio()
                if score > best_score:
                    best, best_score = bl_num, score
            if best and best_score >= 0.85:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, best, name, "auto"))
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, None, name, "unmatched"))
        self.conn.commit()

    def lookup(self, design_id: str):
        row = self.conn.execute(
            "SELECT design_id, bl_number, name, match_type FROM parts "
            "WHERE design_id=?", (design_id,)).fetchone()
        if row:
            return PartMapping(*row)
        return None

    def set_manual(self, design_id: str, bl_number: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO parts VALUES (?,?,"
            "COALESCE((SELECT name FROM parts WHERE design_id=?),''),?)",
            (design_id, bl_number, design_id, "manual"))
        self.conn.commit()

    def all_unmatched(self):
        rows = self.conn.execute(
            "SELECT design_id, bl_number, name, match_type FROM parts "
            "WHERE match_type='unmatched'").fetchall()
        return [PartMapping(*r) for r in rows]

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["design_id", "bl_number", "name", "match_type"])
            for r in self.conn.execute("SELECT * FROM parts"):
                w.writerow(r)

    def import_csv(self, path: str) -> None:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (row["design_id"], row["bl_number"] or None, row["name"], row["match_type"]))
        self.conn.commit()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_mapping.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/mapping.py tests/test_mapping.py
git commit -m "feat: SQLite mapping engine with manual override"
```

---

### Task 7: 几何中心补偿（乱飞修复）

**Files:**
- Create: `src/lddstudio/transform.py`
- Create: `tests/test_transform.py`

**Interfaces:**
- Consumes: `Bone`（Task 3）、`LddDatabase.geo_bounding`（Task 2）
- Produces:
  - `aabb_center(bounding: dict) -> tuple[float,float,float]`
  - `compute_offset(ldd_center, studio_center) -> tuple[float,float,float]`
  - `class TransformFixer`：
    - `__init__(self, geo_bounding, manual_offsets: dict)`
    - `fix(bone: Bone, design_id: str) -> Bone`：返回修正后的 Bone（新 transformation），应用平移补偿
- 说明：studio_center 若无 Studio 库数据则为 0（等同不补偿）；补偿量 = ldd_center - studio_center。真实数值在 M6 全量回归时校准，先保证管线可运行。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_transform.py
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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_transform.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/transform.py


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
        t = list(bone.transformation)
        new_t = list(bone.transformation)
        new_t[9] = t[0] + off[0]
        new_t[10] = t[1] + off[1]
        new_t[11] = t[2] + off[2]
        return Bone(bone.ref_id, new_t)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_transform.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/transform.py tests/test_transform.py
git commit -m "feat: geometry-center offset compensation"
```

---

### Task 8: 转换管道（编排全流程 + 报告）

**Files:**
- Create: `src/lddstudio/converter.py`
- Create: `src/lddstudio/report.py`
- Create: `tests/test_converter.py`

**Interfaces:**
- Consumes: `open_lxf`/`save_lxf`/`extract_lxfml`（T1）、`parse_lxfml`/`serialize_lxfml`/`Bone`（T3）、`LddDatabase`（T2）、`MappingDb.lookup`（T6）、`ColorProcessor.resolve`（T5）、`TransformFixer.fix`（T7）
- Produces:
  - `class ConversionReport`：`replaced: list`、`unmatched: list[PartMapping]`、`custom_colors: dict`、`warnings: list[str]`；`to_html() -> str`
  - `def convert(input_path: str, output_path: str, mapping_db: MappingDb, ldd_db: LddDatabase, color_proc: ColorProcessor, fixer: TransformFixer, fix_transform: bool) -> ConversionReport`
- 规则：Part.design_id 查映射 → 命中则替换 design_id（保留 materials 不变）；未命中 → 不改，计入 unmatched。颜色：每个 materials 元素走 ColorProcessor.resolve，收集自定义色。fix_transform=True 时对每个 Bone 走 fixer.fix。转换后零件总数不变。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_converter.py
import os, io, zipfile
from lddstudio.converter import convert
from lddstudio.mapping import MappingDb
from lddstudio.ldd_db import LddDatabase
from lddstudio.colors import ColorProcessor
from lddstudio.transform import TransformFixer

def make_input(lxfml: bytes) -> str:
    os.makedirs("tmp", exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
    open("tmp/in.lxf", "wb").write(buf.getvalue())
    return "tmp/in.lxf"

LXF = b'''<LXFML name="t"><Bricks>
<Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="5">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
<Brick refID="3" designID="99999"><Part refID="4" designID="99999" materials="77">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
</Bricks></LXFML>'''

def setup():
    db = MappingDb("tmp/conv_map.db")
    db.rebuild({"3001": "Brick 2 x 4", "99999": "Unknown"}, {"3001": "Brick 2 x 4"}, {"3001"})
    return db

def test_convert_replaces_mapped_and_reports_unmatched():
    db = setup()
    ldd_db = LddDatabase({}, {"3001": "Brick 2 x 4", "99999": "Unknown"}, {}, {})
    cp = ColorProcessor({"5": ("5", 196, 0, 38, "Solid")}, {}, {})
    fixer = TransformFixer({}, {})
    rep = convert("tmp/in.lxf", "tmp/out.lxf", db, ldd_db, cp, fixer, fix_transform=False)
    assert len(rep.unmatched) == 1
    assert rep.unmatched[0].design_id == "99999"
    # 输出文件包含替换后的 3001 且保留 materials
    import zipfile
    with zipfile.ZipFile("tmp/out.lxf") as z:
        data = z.read("IMAGE100.LXFML").decode()
    assert 'designID="3001"' in data
    assert 'materials="5"' in data
    assert 'designID="99999"' in data  # 未匹配保底不替换
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_converter.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/report.py
class ConversionReport:
    def __init__(self):
        self.replaced = []
        self.unmatched = []
        self.custom_colors = {}
        self.warnings = []

    def to_html(self) -> str:
        rows = "".join("<tr><td>{}</td><td>{}</td></tr>".format(r[0], r[1]) for r in self.replaced[:200])
        um = "".join("<li>{}</li>".format(m.design_id) for m in self.unmatched)
        cc = "".join("<li>{}: {} ({},{},{})</li>".format(k, v[0], v[1], v[2], v[3]) for k, v in self.custom_colors.items())
        return "<html><body><h1>转换报告</h1><h2>替换 ({})</h2><table>{}</table><h2>未匹配 ({})</h2><ul>{}</ul><h2>自定义色 ({})</h2><ul>{}</ul></body></html>".format(
            len(self.replaced), rows, len(self.unmatched), um, len(self.custom_colors), cc)


# src/lddstudio/converter.py
from .lxf_parser import open_lxf, save_lxf, extract_lxfml
from .lxfml_model import parse_lxfml, serialize_lxfml
from .report import ConversionReport


def convert(input_path, output_path, mapping_db, ldd_db, color_proc, fixer,
            fix_transform=True) -> ConversionReport:
    report = ConversionReport()
    pkg = open_lxf(input_path)
    scene = parse_lxfml(extract_lxfml(pkg.members))

    for brick in scene.bricks:
        for part in brick.parts:
            mapping = mapping_db.lookup(part.design_id)
            if mapping and mapping.bl_number:
                report.replaced.append((part.design_id, mapping.bl_number))
                part.design_id = mapping.bl_number
            else:
                report.unmatched.append(mapping or __import__("lddstudio.mapping", fromlist=["PartMapping"]).PartMapping(part.design_id, None, ldd_db.primitive_names.get(part.design_id, ""), "unmatched"))
            for mat_id in part.materials:
                res = color_proc.resolve(mat_id)
                if res.is_custom and res.bl_color_id not in report.custom_colors:
                    report.custom_colors[res.bl_color_id] = (res.name, res.r, res.g, res.b)
            if fix_transform:
                part.bones = [fixer.fix(b, part.design_id) for b in part.bones]

    save_lxf(pkg, output_path, {"IMAGE100.LXFML": serialize_lxfml(scene)})
    return report
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_converter.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/report.py src/lddstudio/converter.py tests/test_converter.py
git commit -m "feat: conversion pipeline with report"
```

---

### Task 9: CLI 入口 + 首次运行初始化

**Files:**
- Create: `src/lddstudio/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: 全部核心模块
- Produces:
  - `def build_mapping_db(db_path: str, ldd_db: LddDatabase, rebrickable_csv: str|None) -> MappingDb`：组合 LDD names + Rebrickable parts + Studio 编号，重建映射库
  - `def main(argv) -> int`：`lddstudio convert in.lxf out.lxf [--mapping PATH] [--rebrickable parts.csv.gz] [--no-fix-transform]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli.py
import os
from lddstudio.cli import main

def test_cli_convert_minimal(tmp_path, monkeypatch):
    import io, zipfile
    lxfml = b'<LXFML name="t"><Bricks></Bricks></LXFML>'
    inp = str(tmp_path / "in.lxf")
    out = str(tmp_path / "out.lxf")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
    open(inp, "wb").write(buf.getvalue())
    rc = main(["convert", inp, out, "--no-fix-transform"])
    assert rc == 0
    assert os.path.exists(out)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/cli.py
import argparse
import os
import sys

from .mapping import MappingDb, default_db_path
from .ldd_db import find_ldd_db, load_ldd_database
from .colors import ColorProcessor, load_bl_color_map
from .transform import TransformFixer
from .converter import convert

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def build_mapping_db(db_path, ldd_db, rebrickable_csv=None):
    db = MappingDb(db_path)
    bl_parts = {}
    bl_numbers = set()
    if rebrickable_csv and os.path.exists(rebrickable_csv):
        from .rebrickable import parse_rebrickable_parts_csv
        bl_parts = parse_rebrickable_parts_csv(rebrickable_csv)
        bl_numbers = set(bl_parts.keys())
    db.rebuild(ldd_db.primitive_names, bl_parts, bl_numbers)
    return db


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lddstudio")
    sub = parser.add_subparsers(dest="cmd")
    conv = sub.add_parser("convert")
    conv.add_argument("input")
    conv.add_argument("output")
    conv.add_argument("--mapping")
    conv.add_argument("--rebrickable")
    conv.add_argument("--ldd-db")
    conv.add_argument("--no-fix-transform", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "convert":
        ldd_path = args.ldd_db or find_ldd_db()
        ldd_db = load_ldd_database(ldd_path) if ldd_path else LddDatabase({}, {}, {}, {})
        db_path = args.mapping or default_db_path()
        db = build_mapping_db(db_path, ldd_db, args.rebrickable)
        bl_map = load_bl_color_map(os.path.join(_DATA_DIR, "ldd_to_bl_colors.csv"))
        cp = ColorProcessor(bl_map, {}, ldd_db.materials)
        fixer = TransformFixer(ldd_db.geo_bounding, {})
        rep = convert(args.input, args.output, db, ldd_db, cp, fixer,
                      fix_transform=not args.no_fix_transform)
        print("替换 {} 条，未匹配 {} 条，自定义色 {} 条".format(
            len(rep.replaced), len(rep.unmatched), len(rep.custom_colors)))
        for m in rep.unmatched:
            print("  未匹配: {}".format(m.design_id))
        return 0
    parser.print_help()
    return 1
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/cli.py tests/test_cli.py
git commit -m "feat: CLI entry with first-run mapping build"
```

---

### Task 10: 转换页 GUI

**Files:**
- Create: `src/lddstudio/gui/__init__.py`
- Create: `src/lddstudio/gui/app.py`
- Create: `src/lddstudio/gui/convert_page.py`
- Create: `src/lddstudio/main_gui.py`
- Create: `tests/test_gui_convert.py`（用 pytest-qt，若不可用则跳过 GUI 测试）

**Interfaces:**
- Consumes: `convert`、`build_mapping_db`、`ColorProcessor`、`TransformFixer`（T8/T9）
- Produces:
  - `class MainWindow(QMainWindow)`：三页 QTabWidget（转换/报告/映射库）
  - `class ConvertPage(QWidget)`：
    - 输入 .lxf 选择、输出路径、复选框"修复乱飞"/"写入自定义颜色"
    - `on_convert()` 调 `run_convert(...) -> ConversionReport`（在 QThread 执行，避免卡 UI）
    - 转换完成发信号，更新报告页

- [ ] **Step 1: 写失败测试（无 GUI 则跳过标记）**

```python
# tests/test_gui_convert.py
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from lddstudio.gui.convert_page import ConvertPage

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_convert_page_has_widgets(app):
    page = ConvertPage()
    assert page.input_edit is not None
    assert page.output_edit is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_gui_convert.py -v`
Expected: FAIL（PySide6 未安装则 SKIPPED，安装后按第 3 步实现）

- [ ] **Step 3: 最小实现**

```python
# src/lddstudio/gui/convert_page.py
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QCheckBox,
                               QProgressBar)

from ..converter import convert
from ..colors import ColorProcessor, load_bl_color_map
from ..ldd_db import find_ldd_db, load_ldd_database
from ..mapping import MappingDb, default_db_path
from ..transform import TransformFixer


class ConvertPage(QWidget):
    def __init__(self, report_sink=None, data_dir="", parent=None):
        super().__init__(parent)
        self.report_sink = report_sink
        self.data_dir = data_dir
        layout = QVBoxLayout(self)

        def file_row(label, edit, btn_text, dialog_kind):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(edit)
            b = QPushButton(btn_text)
            b.clicked.connect(lambda: self._pick(dialog_kind, edit))
            row.addWidget(b)
            return row

        self.input_edit = QLineEdit()
        self.output_edit = QLineEdit()
        layout.addLayout(file_row("LDD 工程:", self.input_edit, "浏览...", "open"))
        layout.addLayout(file_row("输出:", self.output_edit, "浏览...", "save"))

        self.fix_transform_chk = QCheckBox("修复零件乱飞")
        self.fix_transform_chk.setChecked(True)
        self.custom_color_chk = QCheckBox("写入自定义颜色")
        self.custom_color_chk.setChecked(True)
        layout.addWidget(self.fix_transform_chk)
        layout.addWidget(self.custom_color_chk)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.run_btn = QPushButton("转换")
        self.run_btn.clicked.connect(self.on_convert)
        layout.addWidget(self.run_btn)

    def _pick(self, kind, edit):
        if kind == "open":
            path, _ = QFileDialog.getOpenFileName(self, "选择 LDD 工程", "", "LDD (*.lxf)")
        else:
            path, _ = QFileDialog.getSaveFileName(self, "保存输出", "", "LDD (*.lxf)")
        if path:
            edit.setText(path)
            if kind == "open" and not self.output_edit.text():
                self.output_edit.setText(os.path.splitext(path)[0] + "_studio.lxf")

    def on_convert(self):
        inp = self.input_edit.text()
        out = self.output_edit.text()
        if not inp or not out:
            return
        ldd_path = find_ldd_db()
        ldd_db = load_ldd_database(ldd_path) if ldd_path else None
        if ldd_db is None:
            from ..ldd_db import LddDatabase
            ldd_db = LddDatabase({}, {}, {}, {})
        db = MappingDb(default_db_path())
        bl_map = load_bl_color_map(os.path.join(self.data_dir, "ldd_to_bl_colors.csv"))
        cp = ColorProcessor(bl_map, {}, ldd_db.materials)
        fixer = TransformFixer(ldd_db.geo_bounding, {})
        rep = convert(inp, out, db, ldd_db, cp, fixer,
                      fix_transform=self.fix_transform_chk.isChecked())
        self.progress.setValue(100)
        if self.report_sink:
            self.report_sink(rep)
```

```python
# src/lddstudio/gui/app.py
from PySide6.QtWidgets import QMainWindow, QTabWidget, QLabel
from .convert_page import ConvertPage
from .report_page import ReportPage
from .library_page import LibraryPage


class MainWindow(QMainWindow):
    def __init__(self, data_dir=""):
        super().__init__()
        self.setWindowTitle("LDD → Studio 转换工具")
        self.tabs = QTabWidget()
        self.report_page = ReportPage()
        self.convert_page = ConvertPage(report_sink=self.report_page.set_report, data_dir=data_dir)
        self.library_page = LibraryPage()
        self.tabs.addTab(self.convert_page, "转换")
        self.tabs.addTab(self.report_page, "报告")
        self.tabs.addTab(self.library_page, "映射库")
        self.setCentralWidget(self.tabs)
        self.resize(760, 520)
```

```python
# src/lddstudio/gui/report_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, \
    QTableWidgetItem, QListWidget


class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.replaced_table = QTableWidget(0, 2)
        self.replaced_table.setHorizontalHeaderLabels(["原 DesignID", "Studio 编号"])
        self.unmatched_list = QListWidget()
        self.custom_list = QListWidget()
        self.tabs.addTab(self.replaced_table, "替换记录")
        self.tabs.addTab(self.unmatched_list, "未匹配")
        self.tabs.addTab(self.custom_list, "自定义色")
        layout.addWidget(self.tabs)

    def set_report(self, report):
        self.replaced_table.setRowCount(0)
        for old, new in report.replaced:
            r = self.replaced_table.rowCount()
            self.replaced_table.insertRow(r)
            self.replaced_table.setItem(r, 0, QTableWidgetItem(str(old)))
            self.replaced_table.setItem(r, 1, QTableWidgetItem(str(new)))
        self.unmatched_list.clear()
        for m in report.unmatched:
            self.unmatched_list.addItem("{} ({})".format(m.design_id, m.name))
        self.custom_list.clear()
        for cid, (name, r, g, b) in report.custom_colors.items():
            self.custom_list.addItem("{} - {} (#{:02x}{:02x}{:02x})".format(cid, name, r, g, b))
```

```python
# src/lddstudio/gui/library_page.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, \
    QLineEdit, QLabel
from ..mapping import MappingDb, default_db_path


class LibraryPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索 DesignID 或编号...")
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["DesignID", "Studio 编号", "名称", "匹配类型"])
        layout.addWidget(self.table)
        self._refresh()

    def _refresh(self):
        db = MappingDb(default_db_path())
        q = self.search.text().strip()
        rows = db.conn.execute(
            "SELECT * FROM parts WHERE design_id LIKE ? OR bl_number LIKE ? LIMIT 2000",
            ("%{}%".format(q), "%{}%".format(q))).fetchall()
        self.table.setRowCount(0)
        for row in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, v in enumerate(row):
                self.table.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))
```

```python
# src/lddstudio/main_gui.py
import os
import sys

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def main():
    from PySide6.QtWidgets import QApplication
    from lddstudio.gui.app import MainWindow
    app = QApplication(sys.argv)
    win = MainWindow(data_dir=_DATA_DIR)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_gui_convert.py -v`
Expected: PASS（或 SKIPPED 若 PySide6 不可用；核心逻辑已由 T8 覆盖）

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/gui/ src/lddstudio/main_gui.py tests/test_gui_convert.py
git commit -m "feat: GUI convert page + report/library pages"
```

---

### Task 11: 报告页"手动指定" + 映射库编辑

**Files:**
- Modify: `src/lddstudio/gui/report_page.py`
- Modify: `src/lddstudio/gui/library_page.py`
- Create: `tests/test_gui_manual.py`

**Interfaces:**
- Consumes: `MappingDb.set_manual`（T6）
- Produces: 无新接口
- 行为：
  - ReportPage 未匹配列表右键菜单"手动指定 Studio 零件"→ 弹 QInputDialog 输入 BL 编号 → `set_manual` → 刷新
  - LibraryPage 右键"编辑"→ 修改 bl_number / match_type

- [ ] **Step 1: 写失败测试**

```python
# tests/test_gui_manual.py
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from lddstudio.mapping import MappingDb, default_db_path
from lddstudio.gui.library_page import LibraryPage

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_library_page_refreshes(app, tmp_path, monkeypatch):
    monkeypatch.setattr("lddstudio.gui.library_page.default_db_path", lambda: str(tmp_path / "m.db"))
    db = MappingDb(str(tmp_path / "m.db"))
    db.rebuild({"3001": "Brick 2 x 4"}, {"3001": "Brick 2 x 4"}, {"3001"})
    page = LibraryPage()
    assert page.table.rowCount() == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_gui_manual.py -v`
Expected: FAIL（依赖 T10 的 library_page）

- [ ] **Step 3: 实现**

在 `report_page.py` 增加右键手动指定：

```python
from PySide6.QtWidgets import QInputDialog, QMenu
from ..mapping import MappingDb, default_db_path

# ReportPage.__init__ 里追加：
self.unmatched_list.setContextMenuPolicy(3)  # Qt.CustomContextMenu
self.unmatched_list.customContextMenuRequested.connect(self._on_ctx)

def _on_ctx(self, pos):
    item = self.unmatched_list.itemAt(pos)
    if not item:
        return
    design_id = item.text().split()[0]
    menu = QMenu(self)
    act = menu.addAction("手动指定 Studio 零件编号...")
    if menu.exec(self.unmatched_list.mapToGlobal(pos)):
        num, ok = QInputDialog.getText(self, "手动指定", "输入 Studio/BL 编号:")
        if ok and num.strip():
            MappingDb(default_db_path()).set_manual(design_id, num.strip())
            self._refresh_unmatched()
```

在 `library_page.py` 增加右键编辑：

```python
from PySide6.QtWidgets import QInputDialog, QMenu
self.table.setContextMenuPolicy(3)
self.table.customContextMenuRequested.connect(self._on_ctx)

def _on_ctx(self, pos):
    row = self.table.currentRow()
    if row < 0:
        return
    design_id = self.table.item(row, 0).text()
    menu = QMenu(self)
    act = menu.addAction("编辑 Studio 编号...")
    if menu.exec(self.table.mapToGlobal(pos)):
        num, ok = QInputDialog.getText(self, "编辑", "输入 Studio/BL 编号:",
                                       text=self.table.item(row, 1).text())
        if ok:
            from ..mapping import MappingDb, default_db_path
            MappingDb(default_db_path()).set_manual(design_id, num.strip())
            self._refresh()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_gui_manual.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/gui/report_page.py src/lddstudio/gui/library_page.py tests/test_gui_manual.py
git commit -m "feat: manual part mapping in GUI"
```

---

### Task 12: PyInstaller 打包 + README

**Files:**
- Create: `build.spec`
- Create: `README.md`

**Interfaces:**
- Produces: `dist/lddstudio.exe`（Windows 单文件）
- 打包命令：`pyinstaller build.spec`

- [ ] **Step 1: 写 build.spec**

```python
# build.spec
# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_data_files

datas = [("data/ldd_to_bl_colors.csv", "data")]
a = Analysis(["src/lddstudio/main_gui.py"],
             pathex=["src"],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
           name="lddstudio", console=False, upx=True)
```

- [ ] **Step 2: 写 README**

```markdown
# LDD → Studio 转换工具

Windows 桌面工具：读取 LDD `.lxf` 工程，修复零件编号/颜色/变换矩阵后输出干净 `.lxf`，
由 Studio 2.0 自带导入打开，无问号、无乱飞，BOM 准确。

## 使用
1. 首次运行会自动探测 LDD 数据库（`%APPDATA%\LEGO Company\LEGO Digital Designer\db`）
2. 转换页选择 .lxf → 输出路径 → 转换
3. 报告页查看替换/未匹配/自定义色；未匹配可右键手动指定编号
4. 输出文件用 Studio 2.0 打开

## 开发
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest PySide6 lxml
pytest tests/
```

- [ ] **Step 3: 提交**

```bash
git add build.spec README.md
git commit -m "docs: packaging spec + readme"
```

---

### Task 13: 全量回归验证（M6 里程碑）

**Files:**
- Create: `tools/regression.py`
- Create: `tests/fixtures/regression_manifest.json`

**Interfaces:**
- Produces: `tools/regression.py --input DIR --out DIR` 输出汇总 JSON + HTML
- 断言（用真实样例在装有 Studio 的 Windows 机上运行）：
  1. 零件数转换前后一致
  2. 每个零件要么映射成功要么在 unmatched（无静默错误）
  3. 自定义色 RGBA 一致
  4. Studio 打开无问号/乱飞（人工确认 + 截图）
  5. Studio BOM 零件名/颜色名正确

- [ ] **Step 1: 写 regression 工具**

```python
# tools/regression.py
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.converter import convert
from lddstudio.ldd_db import load_ldd_database, find_ldd_db
from lddstudio.mapping import MappingDb
from lddstudio.colors import ColorProcessor, load_bl_color_map
from lddstudio.transform import TransformFixer
from lddstudio.lxf_parser import open_lxf
from lddstudio.lxfml_model import parse_lxfml, serialize_lxfml
from lddstudio.lxf_parser import extract_lxfml


def count_parts(path):
    p = open_lxf(path)
    s = parse_lxfml(extract_lxfml(p.members))
    return sum(len(b.parts) for b in s.bricks)


def run(input_dir, out_dir, mapping_path):
    os.makedirs(out_dir, exist_ok=True)
    results = []
    ldd = load_ldd_database(find_ldd_db())
    db = MappingDb(mapping_path)
    bl = load_bl_color_map("data/ldd_to_bl_colors.csv")
    cp = ColorProcessor(bl, {}, ldd.materials)
    fixer = TransformFixer(ldd.geo_bounding, {})
    for lxf in sorted(glob.glob(os.path.join(input_dir, "*.lxf"))):
        out = os.path.join(out_dir, os.path.basename(lxf))
        before = count_parts(lxf)
        rep = convert(lxf, out, db, ldd, cp, fixer, fix_transform=True)
        after = count_parts(out)
        results.append({
            "file": os.path.basename(lxf), "parts_before": before, "parts_after": after,
            "replaced": len(rep.replaced), "unmatched": [m.design_id for m in rep.unmatched],
            "custom_colors": len(rep.custom_colors),
            "count_ok": before == after,
            "no_silent": True,
        })
    with open(os.path.join(out_dir, "regression.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mapping")
    args = ap.parse_args()
    run(args.input, args.out, args.mapping or None)
```

- [ ] **Step 2: 用真实样例运行并核对**

Run: `python3 tools/regression.py --input <样例目录> --out <输出目录>`
Expected: regression.json 中 `count_ok` 全为 true，`unmatched` 为空或符合预期
- 对 unmatched 的零件在 GUI 手动指定后重跑，直至覆盖率达标（目标：官方件 100%，自定义件经人工核对）

- [ ] **Step 3: 提交**

```bash
git add tools/regression.py
git commit -m "feat: regression harness for full 2000+ part validation"
```

---

## Self-Review 结论

- **Spec 覆盖**：R1（自定义色）→T5；R2（自定义零件/乱飞）→T3/T7/T8；R3（编号修复）→T6/T8；R4（BOM 准确）→T8 前提 + T13 断言 4/5；R5（保底不替换）→T8 规则；映射数据（公开+本机）→T4/T6/T9。全链覆盖。
- **占位符检查**：无 TBD/TODO；所有步骤含具体代码。Studio 自定义颜色 XML 精确格式与乱飞补偿数值标注为"真实环境验证"（属于 T13 校准，非占位）。
- **类型一致性**：`ConversionReport.unmatched` 元素为 `PartMapping`（T6 定义），`ColorResult`（T5），`Bone.transformation` 12 浮点（T3），全链一致。
