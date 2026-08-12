# LDD↔Studio 互通：映射修正 + conn/col 验证 + 自定义颜色 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 LDD→Studio 映射编号（用 `.dat` 文件名列 + 多候选优先官方件），让客户模型的 76257→22463 正确映射；新增连接点/碰撞体积存在性验证与报告；修正 Studio 自定义颜色路径探测到 `C:\ProgramData\Studio\CustomColors`。

**Architecture:** 基于现有管线三处改动。映射来源 `studio_data.py`（列优先级 + 多候选消歧），转换管线 `converter.py`（收集输出编号验证 conn/col），报告 `report.py` + GUI `convert_page.py`（ProgramData 路径）。全部 TDD 驱动，真实数据（已解包的 Studio pkg 数据 + LDD db.lif + 客户 .lxf）验证。

**Tech Stack:** Python 3.9+、pytest、lxml（未引入新依赖）。

## Global Constraints

- Python 3.9+，禁止 3.10+ 语法（`match`、`|` 类型联合）
- 核心模块（studio_data、converter、report、colors）**禁止 import PySide6**
- 未匹配零件**保底不替换**（保留原 designID），仅列报告
- 数据驱动：所有映射/路径来自 Studio 数据文件，不写死客户目录
- 真实数据测试 fixture 位于解包 Studio 数据（`/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload`）；测试必须能跳过（无数据时 skip），不依赖 CI 环境
- 连接点(.conn)/碰撞体积(.col)只验证存在性，不解析二进制内容

---

### Task 1: 映射编号列修正（.dat 文件名优先）

**Files:**
- Modify: `src/lddstudio/studio_data.py:185-198`（`build_ldd_to_bl_map`）
- Test: `tests/test_studio_data.py`

**Interfaces:**
- Produces: `build_ldd_to_bl_map(rows) -> dict[str, str]` 行为变更：优先 `ldraw_no`（`.dat` 文件名去后缀），fallback `bl_no` → `studio_no`

问题背景：`StudioPartDefinition2.txt` 行 `[Studio号, BL号, LDraw文件名, LDD号, 名称]`。现有逻辑优先 BL 号（第 2 列），但 587 条 BL 号带字母后缀（`30237a`），其中 127 条在 Studio `ldraw/` 无 `.dat` → 变问号。Studio 实际按 `.dat` 文件名渲染，所以必须优先第 4 列。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_studio_data.py 追加
def test_build_ldd_to_bl_map_prefers_ldraw_filename(tmp_path):
    # BL 号带字母后缀(30237a)，.dat 文件名是父编号(30237.dat)
    content = make_partdef([
        "264\t264\t30237a\t264\t30237.dat\t30237\tBrick, Modified 1 x 2 with Split U Clip Thick\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    m = build_ldd_to_bl_map(load_part_definition(str(tmp_path)))
    assert m["30237"] == "30237"      # 用 .dat 文件名，而非 BL 号 30237a


def test_build_ldd_to_bl_map_fallback_order(tmp_path):
    # 无 .dat 文件名时 fallback BL 号，再 fallback Studio 号
    content = make_partdef([
        "5001\t5001\t3001\t5001\t\t3001\tBrick 2 x 4\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
        "5002\t5002\t\t5002\t\t3002\tBrick 2 x 3\to\t13\t1\t1\tFalse\t\tFalse\t5002\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    m = build_ldd_to_bl_map(load_part_definition(str(tmp_path)))
    assert m["3001"] == "3001"      # fallback bl_no
    assert m["3002"] == "5002"      # fallback studio_no
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_studio_data.py::test_build_ldd_to_bl_map_prefers_ldraw_filename tests/test_studio_data.py::test_build_ldd_to_bl_map_fallback_order -v`
Expected: FAIL（`test_build_ldd_to_bl_map_prefers_bl` 现有测试也可能失败，见 Step 3 说明）

- [ ] **Step 3: 修改实现**

`src/lddstudio/studio_data.py` 中 `build_ldd_to_bl_map`：

```python
def build_ldd_to_bl_map(rows):
    """Return dict: ldd_design_id -> render number.

    Studio renders parts by their LDraw .dat filename (col 4).  BL numbers
    (col 2) often carry letter suffixes (30237a) whose .dat does not exist in
    the Studio ldraw/ tree, so preferring the .dat filename avoids parts
    showing as question marks.  Fallback order: ldraw file -> BL -> studio.
    """
    out = {}
    for pd in rows:
        if not pd.ldd_no:
            continue
        target = _ldraw_no_to_bl(pd.ldraw_no) if pd.ldraw_no else ""
        if not target:
            target = pd.bl_no
        if not target:
            target = pd.studio_no
        if target:
            out.setdefault(pd.ldd_no, target)
    return out
```

注意：现有 `test_build_ldd_to_bl_map_prefers_bl`（第 55 行）断言 `m["3001"] == "3001"`——该行 `.dat` 文件名是 `3001.dat`，去后缀后仍为 `3001`，故仍通过。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_studio_data.py -v`
Expected: PASS（全部，含新增 2 个）

- [ ] **Step 5: 用真实数据验证**

Run:
```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from lddstudio.studio_data import load_studio_mapping
SD='/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data'
ldd_to_bl, offsets, filenames = load_studio_mapping(SD)
print('mapped:', len(ldd_to_bl))
print('30237 ->', ldd_to_bl.get('30237'))
"
```
Expected: `30237 -> 30237`（原为 30237a）；映射总数不变（约 5973）

- [ ] **Step 6: 提交**

```bash
git add src/lddstudio/studio_data.py tests/test_studio_data.py
git commit -m "fix: prefer .dat filename column for part mapping to avoid question marks"
```

---

### Task 2: 多候选 .dat 优先官方件（76257→22463）

**Files:**
- Modify: `src/lddstudio/studio_data.py`（`load_studio_mapping`、新增 `build_official_dat_index`、`disambiguate_candidates`）
- Test: `tests/test_studio_data.py`

**Interfaces:**
- Consumes: `load_transform_data(data_dir)`（返回 `(offsets, filenames)`，filenames 是 `{design_id: ldraw_filename}`）
- Produces:
  - `build_official_dat_index(ldraw_dir: str) -> set[str]`：官方 `parts/`（或 `p/`）目录下 `.dat` 文件名的去后缀集合（不含 `UnOfficial`）
  - `disambiguate_candidates(filenames: dict, official_index: set) -> dict`：返回 `{design_id: 消歧后的 .dat 名}`；仅当 designID 有多个不同候选且恰好一个在官方索引中时才消歧，否则保留原值

问题背景：`ldraw_lxfml_mapping.json` 里 830 个 designID 有多个 `.dat` 候选，222 个可通过「优先官方 parts/ 目录」消歧。76257 有 `22463.dat`（官方 parts/）与 `76257.dat`（UnOfficial/parts），应选 22463。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_studio_data.py 追加
def test_build_official_dat_index():
    import os
    root = os.path.join(os.path.dirname(__file__), "fixtures", "ldraw")
    os.makedirs(os.path.join(root, "parts"), exist_ok=True)
    os.makedirs(os.path.join(root, "UnOfficial", "parts"), exist_ok=True)
    open(os.path.join(root, "parts", "22463.dat"), "w").write("")
    open(os.path.join(root, "UnOfficial", "parts", "76257.dat"), "w").write("")
    idx = build_official_dat_index(root)
    assert "22463" in idx
    assert "76257" not in idx


def test_disambiguate_prefers_official():
    # 76257 有两个候选，仅 22463 在官方索引
    filenames = {"76257": "22463.dat", "3001": "3001.dat", "10067": "11010.dat"}
    official = {"22463", "3001", "11010"}
    out = disambiguate_candidates(filenames, official)
    assert out["76257"] == "22463"      # 消歧
    assert out["10067"] == "11010"
    assert out["3001"] == "3001"        # 单一候选不变
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_studio_data.py::test_build_official_dat_index tests/test_studio_data.py::test_disambiguate_prefers_official -v`
Expected: FAIL（`ImportError: cannot import name 'build_official_dat_index'`）

- [ ] **Step 3: 实现消歧函数**

`src/lddstudio/studio_data.py` 新增：

```python
def build_official_dat_index(ldraw_dir):
    """Return set of .dat basenames in official parts dirs (parts/, p/).

    UnOfficial/ and collider/connectivity are excluded.  Returns empty set
    when ldraw_dir is missing.
    """
    out = set()
    if not ldraw_dir or not os.path.isdir(ldraw_dir):
        return out
    for root, _dirs, files in os.walk(ldraw_dir):
        rel = os.path.relpath(root, ldraw_dir).replace("\\", "/")
        parts = rel.split("/")
        if "UnOfficial" in parts or "unofficial" in parts:
            continue
        if not (parts[-1] == "parts" or parts[-1] == "p"):
            continue
        for f in files:
            if f.endswith(".dat"):
                out.add(f[:-4])
    return out


def disambiguate_candidates(filenames, official_index):
    """Pick the official .dat when a designID has multiple candidates.

    filenames: {design_id: ldraw_filename}.  Returns a new dict where
    multi-candidate designIDs with exactly one official candidate resolve to
    that official file; all others keep their original value.
    """
    grouped = {}
    for did, fname in filenames.items():
        grouped.setdefault(did, set()).add(fname)
    out = {}
    for did, fname in filenames.items():
        cands = grouped[did]
        if len(cands) > 1:
            official = [c for c in cands
                        if c[:-4] in official_index and c.endswith(".dat")]
            if len(official) == 1:
                out[did] = official[0]
                continue
        out[did] = fname
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_studio_data.py::test_build_official_dat_index tests/test_studio_data.py::test_disambiguate_prefers_official -v`
Expected: PASS

- [ ] **Step 5: 接入 load_studio_mapping**

`src/lddstudio/studio_data.py` 的 `load_studio_mapping` 中，`from_transform` 构建后调用消歧。修改 `load_studio_mapping`：

```python
    from_transform = build_ldd_to_bl_from_filenames(filenames.items())
    # 多候选优先官方件（76257 -> 22463.dat）
    official_index = build_official_dat_index(
        os.path.join(os.path.dirname(data_dir), "ldraw"))
    if official_index:
        disambiguated = disambiguate_candidates(filenames, official_index)
        from_transform = build_ldd_to_bl_from_filenames(disambiguated.items())
    for did, bl in from_transform.items():
        ldd_to_bl.setdefault(did, bl)
```

注意：`data_dir` 参数是 `<Studio>/data`，`os.path.dirname` 得 `<Studio>`，拼接 `ldraw`。若 `build_official_dat_index` 返回空集（无官方索引），跳过消歧，保持原行为。

- [ ] **Step 6: 运行全部 studio_data 测试 + 真实数据验证**

Run: `python3 -m pytest tests/test_studio_data.py -v`
Expected: PASS

Run:
```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from lddstudio.studio_data import load_studio_mapping
SD='/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data'
ldd_to_bl, offsets, filenames = load_studio_mapping(SD)
print('76257 ->', ldd_to_bl.get('76257'))
print('10067 ->', ldd_to_bl.get('10067'))
"
```
Expected: `76257 -> 22463`、`10067 -> 11010`

- [ ] **Step 7: 提交**

```bash
git add src/lddstudio/studio_data.py tests/test_studio_data.py tests/fixtures/ldraw
git commit -m "feat: disambiguate multi-candidate .dat preferring official parts (76257->22463)"
```

---

### Task 3: 客户真实模型回归测试（含 conn/col 验证）

**Files:**
- Create: `tests/fixtures/models/正确的姿态_客户样例.lxf`（复制自 `~/Downloads/零件颜色+修正/正确的姿态以及需要的自定义颜色.lxf`）
- Modify: `tests/test_real_models.py`

**Interfaces:**
- Consumes: `load_studio_mapping`（Task 1/2）、`build_official_dat_index`（Task 2）、`convert`、`parse_lxfml`
- Produces: 无新接口；验证需求（76257→22463、conn/col 存在）

- [ ] **Step 1: 复制客户模型到 fixtures**

```bash
mkdir -p tests/fixtures/models
cp "/Users/Zhuanz/Downloads/零件颜色+修正/正确的姿态以及需要的自定义颜色.lxf" \
   "tests/fixtures/models/正确的姿态_客户样例.lxf"
```

- [ ] **Step 2: 写回归测试**

`tests/test_real_models.py` 追加一个独立测试（不依赖 `_studio_available` 的 Windows 硬编码，改用 Studio 数据目录探测）：

```python
def _studio_payload_dir():
    """Return the unpacked Studio data dir from env or known mac path."""
    for base in (
        os.environ.get("LDDSTUDIO_STUDIO_DATA_DIR", ""),
        "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload",
    ):
        if base and os.path.isfile(os.path.join(base, "StudioPartDefinition2.txt")):
            return base
    return ""


@pytest.mark.skipif(not _studio_payload_dir(), reason="real Studio data not available")
def test_customer_model_disambiguation_and_conn_col(tmp_path):
    import shutil
    sd = _studio_payload_dir()
    ldraw_dir = os.path.join(os.path.dirname(sd), "ldraw")
    from lddstudio.cli import build_mapping_db
    from lddstudio.resources import data_dir
    from lddstudio.ldd_db import load_ldd_database

    ldd_path = os.path.join(
        os.path.dirname(sd), "..", "db.lif")  # mac unpack path
    ldd_db = load_ldd_database(ldd_path) if os.path.isfile(ldd_path) else \
        load_ldd_database("")
    db_path = str(tmp_path / "map.db")
    db = build_mapping_db(db_path, ldd_db, studio_data_dir=sd, force_rebuild=True)
    studio_colors = studio_colors_for_ldd(load_color_definition(sd))
    cp = ColorProcessor(load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv")),
                        studio_colors, ldd_db.materials, studio_color_map=studio_colors)
    ldd_to_bl, offsets, _ = load_studio_mapping(sd)
    fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)

    inp = "tests/fixtures/models/正确的姿态_客户样例.lxf"
    out = str(tmp_path / "out.lxf")
    rep = convert(inp, out, db, ldd_db, cp, fixer, fix_transform=True)

    out_scene = parse_lxfml(extract_lxfml(open_lxf(out).members))
    ids = {p.design_id for b in out_scene.bricks for p in b.parts}
    # 76257 已消歧为 22463
    assert "22463" in ids, "76257 should disambiguate to 22463"
    assert "76257" not in ids

    # 所有输出编号的 .conn/.col 存在
    conn_dir = os.path.join(ldraw_dir, "connectivity")
    col_dir = os.path.join(ldraw_dir, "collider")
    missing = [i for i in ids
               if not os.path.isfile(os.path.join(conn_dir, i + ".conn")) or
                  not os.path.isfile(os.path.join(col_dir, i + ".col"))]
    assert not missing, "parts missing conn/col: {}".format(missing)

    # 零件数不变
    in_scene = parse_lxfml(extract_lxfml(open_lxf(inp).members))
    n_in = sum(len(b.parts) for b in in_scene.bricks)
    n_out = sum(len(b.parts) for b in out_scene.bricks)
    assert n_in == n_out
    db.close()
```

- [ ] **Step 3: 运行测试**

Run: `python3 -m pytest tests/test_real_models.py::test_customer_model_disambiguation_and_conn_col -v`
Expected: PASS（映射 76257→22463、conn/col 全部存在、零件数不变）

- [ ] **Step 4: 提交**

```bash
git add tests/fixtures/models/正确的姿态_客户样例.lxf tests/test_real_models.py
git commit -m "test: customer model regression - 76257->22463 disambiguation + conn/col presence"
```

---

### Task 4: 报告区分消歧零件 + 缺 conn/col 警告

**Files:**
- Modify: `src/lddstudio/report.py`
- Modify: `src/lddstudio/converter.py`
- Modify: `src/lddstudio/cli.py:94-99`（打印报告）
- Modify: `src/lddstudio/gui/convert_page.py`（report_sink 已存在，无需改）
- Test: `tests/test_converter.py`

**Interfaces:**
- Produces:
  - `ConversionReport` 新增字段：`disambiguated: list[tuple[str, str]]`（原 designID → 消歧后编号）、`missing_conn_collider: list[str]`
  - `convert(..., studio_ldraw_dir: str = "")` 新增参数；非空时收集输出 designID 验证 conn/col
  - `ConversionReport.to_html()` 增加两段

- [ ] **Step 1: 写失败测试**

```python
# tests/test_converter.py 追加
import os
from lddstudio.report import ConversionReport


def test_report_disambiguated_and_missing_conn():
    rep = ConversionReport()
    rep.disambiguated.append(("76257", "22463"))
    rep.missing_conn_collider.append("99999")
    html = rep.to_html()
    assert "76257" in html and "22463" in html
    assert "99999" in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_converter.py::test_report_disambiguated_and_missing_conn -v`
Expected: FAIL（`AttributeError: 'ConversionReport' object has no attribute 'disambiguated'`）

- [ ] **Step 3: 修改 report.py**

```python
class ConversionReport:
    def __init__(self):
        self.replaced = []
        self.unmatched = []
        self.custom_colors = {}
        self.warnings = []
        self.disambiguated = []
        self.missing_conn_collider = []

    def to_html(self) -> str:
        rows = "".join("<tr><td>{}</td><td>{}</td></tr>".format(r[0], r[1])
                       for r in self.replaced[:200])
        um = "".join("<li>{}</li>".format(m.design_id) for m in self.unmatched)
        cc = "".join("<li>{}: {} ({},{},{})</li>".format(
            k, v[0], v[1], v[2], v[3]) for k, v in self.custom_colors.items())
        dis = "".join("<li>{} → {}</li>".format(a, b)
                      for a, b in self.disambiguated[:200])
        mc = "".join("<li>{}</li>".format(i) for i in self.missing_conn_collider)
        return (
            "<html><body><h1>转换报告</h1>"
            "<h2>替换 ({})</h2><table>{}</table>"
            "<h2>消歧 ({})</h2><ul>{}</ul>"
            "<h2>未匹配 ({})</h2><ul>{}</ul>"
            "<h2>自定义色 ({})</h2><ul>{}</ul>"
            "<h2>缺连接点/碰撞体积 ({})</h2><ul>{}</ul>"
            "</body></html>").format(
                len(self.replaced), rows, len(self.disambiguated), dis,
                len(self.unmatched), um, len(self.custom_colors), cc,
                len(self.missing_conn_collider), mc)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_converter.py::test_report_disambiguated_and_missing_conn -v`
Expected: PASS

- [ ] **Step 5: converter.py 收集消歧 + conn/col 验证**

`src/lddstudio/converter.py`：

```python
import os


def convert(input_path, output_path, mapping_db, ldd_db, color_proc, fixer,
            fix_transform=True, studio_ldraw_dir="") -> ConversionReport:
    report = ConversionReport()
    pkg = open_lxf(input_path)
    scene = parse_lxfml(extract_lxfml(pkg.members))

    for brick in scene.bricks:
        for part in brick.parts:
            original_design_id = part.design_id
            mapping = mapping_db.lookup(original_design_id)
            if mapping and mapping.bl_number:
                report.replaced.append((original_design_id, mapping.bl_number))
                if mapping.bl_number != original_design_id and \
                   original_design_id != _ldraw_base(mapping.bl_number):
                    report.disambiguated.append(
                        (original_design_id, mapping.bl_number))
                part.design_id = mapping.bl_number
            else:
                report.unmatched.append(mapping or PartMapping(original_design_id, None, ldd_db.primitive_names.get(original_design_id, ""), "unmatched"))
            resolved = [color_proc.resolve(mat_id) for mat_id in part.materials]
            for res in resolved:
                if res.is_custom and res.bl_color_id not in report.custom_colors:
                    report.custom_colors[res.bl_color_id] = (res.name, res.r, res.g, res.b)
            part.materials = [res.bl_color_id for res in resolved]
            if fix_transform:
                part.bones = [fixer.fix(b, original_design_id) for b in part.bones]

    if studio_ldraw_dir:
        conn_dir = os.path.join(studio_ldraw_dir, "connectivity")
        col_dir = os.path.join(studio_ldraw_dir, "collider")
        if os.path.isdir(conn_dir) and os.path.isdir(col_dir):
            seen = set()
            for b in scene.bricks:
                for p in b.parts:
                    if p.design_id in seen:
                        continue
                    seen.add(p.design_id)
                    if not os.path.isfile(os.path.join(conn_dir, p.design_id + ".conn")) or \
                       not os.path.isfile(os.path.join(col_dir, p.design_id + ".col")):
                        report.missing_conn_collider.append(p.design_id)

    save_lxf(pkg, output_path, {"IMAGE100.LXFML": serialize_lxfml(scene)})
    return report


def _ldraw_base(bl_number):
    return bl_number.split(".")[0]
```

注意：`report.disambiguated` 判定用「mapping.bl_number != original」且非纯粹去后缀（如 `bl_973pb...` 不触发）。简化为：`mapping.bl_number != original_design_id and mapping.bl_number != _ldraw_base(original_design_id)`。若原有测试断言 `replaced` 结构不变，此改动向后兼容。

- [ ] **Step 6: 运行 converter 测试**

Run: `python3 -m pytest tests/test_converter.py -v`
Expected: PASS（现有测试不受影响，replaced 结构未变）

- [ ] **Step 7: cli.py 打印新报告段**

`src/lddstudio/cli.py` 的 `main()` 中，转换后增加：

```python
        print("替换 {} 条，消歧 {} 条，未匹配 {} 条，自定义色 {} 条，缺连接点/碰撞 {} 条".format(
            len(rep.replaced), len(rep.disambiguated), len(rep.unmatched),
            len(rep.custom_colors), len(rep.missing_conn_collider)))
        for a, b in rep.disambiguated:
            print("  消歧: {} -> {}".format(a, b))
        for m in rep.unmatched:
            print("  未匹配: {}".format(m.design_id))
        for i in rep.missing_conn_collider:
            print("  缺连接点/碰撞体积: {}".format(i))
```

同时把 `convert(...)` 调用传入 `studio_ldraw_dir`：

```python
        ldraw_dir = os.path.join(os.path.dirname(studio_data_dir), "ldraw") \
            if studio_data_dir else ""
        rep = convert(args.input, args.output, db, ldd_db, cp, fixer,
                      fix_transform=not args.no_fix_transform,
                      studio_ldraw_dir=ldraw_dir)
```

- [ ] **Step 8: 运行 CLI 测试 + 真实 CLI 转换**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: PASS

Run:
```bash
python3 -m lddstudio.cli convert "/Users/Zhuanz/Downloads/零件颜色+修正/正确的姿态以及需要的自定义颜色.lxf" tmp/req_out2.lxf --rebuild-mapping 2>&1 | head -20
```
Expected: 输出含「消歧 1 条」或显示 76257→22463；若缺 conn/col 列出

- [ ] **Step 9: 提交**

```bash
git add src/lddstudio/report.py src/lddstudio/converter.py src/lddstudio/cli.py tests/test_converter.py
git commit -m "feat: report disambiguated parts and missing connectivity/collider"
```

---

### Task 5: Studio 自定义颜色路径探测（ProgramData）

**Files:**
- Modify: `src/lddstudio/gui/convert_page.py:17-43`（`_studio_custom_definition_path`、`_existing_custom_codes`）
- Test: `tests/test_gui_manual.py`

**Interfaces:**
- Produces: `_studio_custom_definition_path(studio_data_dir, program_data_dir="")` 增加 ProgramData 候选

- [ ] **Step 1: 写失败测试**

`tests/test_gui_manual.py` 追加（先看该文件现有 import 结构再适配）：

```python
def test_custom_definition_path_prefers_program_data(tmp_path):
    from lddstudio.gui.convert_page import _studio_custom_definition_path
    pd = tmp_path / "ProgramData"
    (pd / "Studio" / "CustomColors").mkdir(parents=True)
    (pd / "Studio" / "CustomColors" / "CustomColorDefinition.txt").write_text("", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    p = _studio_custom_definition_path(str(data_dir), str(pd))
    assert "CustomColors" in p
    assert p.endswith("CustomColorDefinition.txt")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python3 -m pytest tests/test_gui_manual.py::test_custom_definition_path_prefers_program_data -v`
Expected: FAIL（`TypeError: _studio_custom_definition_path() got an unexpected keyword argument 'program_data_dir'`）

- [ ] **Step 3: 修改实现**

`src/lddstudio/gui/convert_page.py`：

```python
def _studio_custom_definition_path(studio_data_dir, program_data_dir=""):
    """Locate Studio's CustomColorDefinition.txt to register custom colors.

    Customers' Studio keeps custom colors at
    C:\\ProgramData\\Studio\\CustomColors\\CustomColorDefinition.txt.
    Fall back to the <data>/CustomColors and <data> locations.
    """
    candidates = []
    if program_data_dir:
        candidates.append(os.path.join(program_data_dir, "Studio", "CustomColors",
                                       "CustomColorDefinition.txt"))
    if studio_data_dir:
        candidates += [
            os.path.join(studio_data_dir, "CustomColors", "CustomColorDefinition.txt"),
            os.path.join(studio_data_dir, "CustomColorDefinition.txt"),
        ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return candidates[0] if candidates else ""
```

调用处 `on_convert`（convert_page.py 内）传入 ProgramData：

```python
        program_data = os.environ.get("ProgramData", "C:\\ProgramData")
        custom_def = _studio_custom_definition_path(studio_data_dir, program_data)
```

注意：`_existing_custom_codes` 目前只在 `studio_data_dir` 下扫。保持现状（ProgramData 的现有自定义色由 Studio 管理，我们只追加），或按需同步。本任务仅修正写入路径。

- [ ] **Step 4: 运行测试确认通过**

Run: `python3 -m pytest tests/test_gui_manual.py::test_custom_definition_path_prefers_program_data tests/test_gui_convert.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/lddstudio/gui/convert_page.py tests/test_gui_manual.py
git commit -m "fix: detect Studio custom colors in ProgramData\\Studio\\CustomColors"
```

---

### Task 6: 覆盖率报告（官方/消歧/未匹配/缺 conn-col）

**Files:**
- Modify: `tools/coverage_report.py`
- Modify: `tools/e2e_studio_data.py`（如存在则适配）

**Interfaces:**
- Consumes: `load_studio_mapping`、`build_official_dat_index`、`disambiguate_candidates`
- Produces: 命令行输出统计

- [ ] **Step 1: 修改 coverage_report.py 增加分类**

在现有统计基础上输出：
- 官方零件数（映射命中且 `.dat` 在官方索引）
- 消歧零件数（Task 2 的 disambiguate_candidates 触发数）
- 未匹配零件数
- 输出编号缺 `.conn`/`.col` 的零件数

参考实现骨架（适配现有文件结构）：

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.studio_data import (load_studio_mapping, build_official_dat_index,
                                   disambiguate_candidates)

STUDIO_DATA = os.environ.get("LDDSTUDIO_STUDIO_DATA_DIR",
                            "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data")


def main():
    sd = STUDIO_DATA
    if not os.path.isfile(os.path.join(sd, "StudioPartDefinition2.txt")):
        print("Studio data not found:", sd)
        return 1
    ldd_to_bl, _offsets, filenames = load_studio_mapping(sd)
    ldraw_dir = os.path.join(os.path.dirname(sd), "ldraw")
    official = build_official_dat_index(ldraw_dir)
    dis = disambiguate_candidates(filenames, official)

    n_dis = sum(1 for did, f in dis.items()
                if filenames.get(did) != f and ldd_to_bl.get(did) != did)
    missing_conn = [bl for bl in set(ldd_to_bl.values())
                    if bl and not os.path.isfile(
                        os.path.join(ldraw_dir, "connectivity", bl + ".conn"))]
    print("mapped total:", len(ldd_to_bl))
    print("disambiguated:", n_dis)
    print("official .dat:", sum(1 for bl in set(ldd_to_bl.values())
                                if bl in official))
    print("missing conn/col for mapped:", len(missing_conn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 运行验证**

Run: `python3 tools/coverage_report.py`
Expected: 输出 mapped total ≈ 5973、disambiguated > 0、official .dat 多数、missing conn/col 少量

- [ ] **Step 3: 提交**

```bash
git add tools/coverage_report.py
git commit -m "feat: coverage report classifies official/disambiguated/missing conn-col"
```

---

### Task 7: 全量回归 + 真实模型基线验证

**Files:**
- Modify: `tests/test_real_models.py`（若 `_studio_available` 硬编码 Windows 路径，改为探测，使本机真实数据可跑）
- 无新接口

- [ ] **Step 1: 让真实模型回归在本机可跑**

`tests/test_real_models.py` 的 `_studio_available()` 与 `LDD_DB` 硬编码 `D:\Studio 2.0\data` 与 `%USERPROFILE%`。改为同时接受环境变量与本机解包路径：

```python
def _studio_data_dir():
    for base in (os.environ.get("LDDSTUDIO_STUDIO_DATA_DIR", ""),
                 "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data"):
        if base and os.path.isfile(os.path.join(base, "StudioPartDefinition2.txt")):
            return base
    return ""


def _ldd_db_path():
    for base in (os.environ.get("LDDSTUDIO_LDD_DB", ""),
                 "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/db.lif"):
        if base and os.path.isfile(base):
            return base
    return ""


def _studio_available():
    return bool(_studio_data_dir() and _ldd_db_path())
```

将 pipeline fixture 中 `studio_data_dir = find_studio_data_dir()` 改为 `_studio_data_dir()`；`LDD_DB` 引用改 `_ldd_db_path()`；`ldraw` 遍历路径用 `os.path.join(os.path.dirname(_studio_data_dir()), "ldraw")`。

- [ ] **Step 2: 运行全部真实模型回归**

Run: `python3 -m pytest tests/test_real_models.py -v`
Expected: 8 个 fixture 全部 PASS（含客户样例新增 1 个）；不再 skip

- [ ] **Step 3: 运行全量测试**

Run: `python3 -m pytest tests/ -q`
Expected: PASS（9 个原先 skip 的测试现在在本机跑通或仍按条件 skip）

- [ ] **Step 4: 提交**

```bash
git add tests/test_real_models.py
git commit -m "test: run real-model regression against unpacked Studio+LDD data"
```

---

## 验证清单（全部任务完成后）

```bash
python3 -m pytest tests/ -q
python3 tools/coverage_report.py
python3 -m lddstudio.cli convert "/Users/Zhuanz/Downloads/零件颜色+修正/正确的姿态以及需要的自定义颜色.lxf" tmp/req_final.lxf --rebuild-mapping
```

验收：
1. `76257` 输出为 `22463`（消歧）
2. 输出零件全部有 `.conn`/`.col`（无缺连接点/碰撞体积警告）
3. 颜色映射 151→48、222→104、21→5、26→11（与客户 Studio BOM 一致）
4. 零件数不变、0 未匹配
5. 覆盖率报告输出 official/disambiguated/unmatched 分类
