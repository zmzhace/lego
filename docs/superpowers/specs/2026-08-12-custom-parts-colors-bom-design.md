# LDD ↔ Studio 互通：自定义零件修复 + 自定义颜色 + BOM 准确 设计文档

日期：2026-08-12
状态：已确认设计，待实现
前置：`2026-08-11-ldd-studio-converter-design.md`（基础转换管线，已完成实现）

## 1. 背景与目标

客户提供真实需求与验收基准（`~/Downloads/零件颜色+修正/`）：

| 文件 | 用途 |
|------|------|
| `需求.docx` | 5 条需求原文 |
| `正确的姿态以及需要的自定义颜色.lxf` | 源 LDD 模型（验收输入） |
| `36841、36840、762573个零件需要修复.io` | Studio 打开后应达到的正确形态（验收目标，LDraw 导出格式） |
| `LDD BOM表.xlsx` | LDD 侧 BOM（颜色名/数量基准） |
| `studio BOM表.csv` | Studio 侧 BOM（应达成的编号/颜色目标） |

**需求（来自需求.docx）：**
1. 自定义颜色：值 `#193f87` 名称「海军蓝」等 30+ 种且持续增加，LDD 格式 `T01-英文名字`；Studio 打开 LDD 文件能识别
2. LDD 导出 BOM 颜色名要一致；Studio 同理
3. LDD 与 Studio 互通：Studio 打开 LDD 文件时保持所有零件的形状姿态
4. LDD 停更、Studio 持续更新，工具必须适配 Studio 更新（数据驱动，不写死）

**关键验收件：** 模型含 6 种零件（36841、3003、36840、76257、23443、15712），其中 **36841、36840、76257 三个零件用户明确标注"需要修复"**。

## 2. 真实数据验证结论（已完成，本机已获取 Studio + LDD 数据）

在真实数据上跑通该模型，逐项验证：

### 2.1 颜色映射（✅ 已验证 100% 正确）
LDD 材质号 → Studio（BL/LDraw）颜色，与客户 Studio BOM 完全一致：

| LDD | Studio | 名称（Studio BOM） |
|-----|--------|--------------------|
| 151 | 48 | Sand Green |
| 222 | 104 | Bright Pink |
| 21 | 5 | Red |
| 26 | 11 | Black |

### 2.2 零件映射（✅ 已验证，1 个需补规则）
- 36841、36840、3003、23443、15712：转换后编号不变且 Studio 官方 `.dat` 存在，变换偏移已应用（`ldraw_lxfml_mapping.json` 提供）
- **76257**：LDD 的 `OUTER CABLE 152MM`，Studio 正确件是 `22463.dat`（Hose Rigid，`parts/` 官方目录）。`ldraw_lxfml_mapping.json` 里 76257 有两条候选：`22463.dat`（官方）与 `76257.dat`（`UnOfficial/parts`）。客户手动修复的 `.io` 用的就是 22463.dat。**当前管线输出 76257.dat（Unofficial），BOM 名/编号不对。**

### 2.3 变换偏移（✅ 已验证）
36840、36841、15712、23443 均有官方旋转/平移偏移；76257 弹簧含 20+ Bone 子件（柔性件），偏移为 0（LDD 与 Studio 几何一致），无需补偿。输出姿态与客户 `.io` 一致。

### 2.4 映射编号 Bug（⚠️ 需修复）
`StudioPartDefinition2.txt` 行格式 `[Studio号, BL号, LDraw文件名, LDD号, 名称]`。现有 `_parse_part_def_row` 取第 2 列 BL 号做输出编号，但 Studio 实际按第 4 列 `.dat` 文件名渲染：
- 587 条 BL 号带字母后缀（`30237a` 等）
- 其中 **127 条在 Studio `ldraw/` 里无对应 `.dat`** → 输出后变问号
- 改用第 4 列 `.dat` 文件名后：**2451 个映射中 2450 个命中 Studio 真实存在的 `.dat`**，仅 1 个（60602d）缺失

### 2.5 多候选消歧（⚠️ 需实现）
全库 830 个 designID 在 `ldraw_lxfml_mapping.json` 有多个 `.dat` 候选，其中 **222 个**能通过「优先官方 `parts/` 目录」干净消歧（76257→22463、10067→11010、10190→2599 等）。

## 3. 设计

### 3.1 目标
在现有管线（`convert()`）上做三处改动，达成客户验收：编号映射列修正 + 多候选优先官方件 + 自定义颜色命名保留。自定义零件的 `.g→.dat` 生成（方案 A）作为后续里程碑，本次先处理官方数据即可覆盖客户模型。

### 3.2 改动一：映射编号列修正（`studio_data.py`）

`build_ldd_to_bl_map` 输出目标改为**优先第 4 列 `.dat` 文件名**，fallback 顺序：
1. `.dat` 文件名去后缀（`30237.dat` → `30237`）
2. BL 号（第 2 列）
3. Studio 号（第 1 列）

保留 `StudioPartDef` 全部列，新增 `render_no` 概念（输出编号）。

### 3.3 改动二：多候选优先官方件（`studio_data.py`）

`load_studio_mapping` 组合映射时：
- 先收集 `ldraw_lxfml_mapping.json` 全部候选 `{designID: [.dat 列表]}`
- 加载 Studio `ldraw/` 目录索引（`.dat` → 所属目录，仅一次）
- 对有多候选的 designID：选**位于官方 `parts/`（或 `p/`）目录**的候选；官方唯一则采用；否则保留原（报告标记）
- `76257 → 22463.dat` 即由此规则得出

### 3.4 改动三：颜色命名与自定义色（`colors.py`）

- **官方色**：保持现状（`studio_color_map` 已正确）
- **自定义色**：`resolve()` 命名**保留 LDD 原名**（`m.name`），不生成 `T01-` 前缀；色值用 LDD 材质 RGB；写入 Studio `CustomColorDefinition.txt`（现有 `append_to_custom_definition` 已实现）
- 适配客户「持续增加 30+ 种」：色码分配从 520000 高位起、去重、幂等追加（已实现）

### 3.5 报告与覆盖率（`report.py` / `tools/coverage_report.py`）

转换报告区分：
- 官方零件（mapped official）
- 多候选消歧零件（disambiguated，如 76257→22463）
- 未匹配（unmatched，保留原编号并列出）

### 3.6 数据流

```
convert()
  逐 Part:
    designID → 映射库 lookup
    命中 → 输出编号取 render_no（列修正后的 .dat 名）
       │  变换偏移照旧（fixer）
    多候选 → 优先官方 .dat（76257→22463）
    未命中 → 保留原编号 + 报告 unmatched
    materials → ColorProcessor.resolve()
      官方色 → Studio 色码
      自定义色 → 保留 LDD 原名 + RGB → 写入 Studio 自定义色表
  输出 .lxf + 报告
```

## 4. 测试策略

### 4.1 新增测试（真实数据）
- `tests/test_studio_data.py`：列优先级（`30237`→用 `.dat` 名而非 BL 号）；多候选消歧（76257→22463）
- 真实模型回归：客户 `正确的姿态...lxf` 加入 fixtures，断言输出 designID 全部存在于 Studio `ldraw/`、76257 映射为 22463、颜色映射与 Studio BOM 一致
- `tools/coverage_report.py`：输出官方/消歧/未匹配零件统计

### 4.2 数据来源
- Studio 数据目录：本机解包所得（`data/` + `ldraw/`），作为测试 fixture 的权威来源
- LDD 数据库：`Assets.lif` 内嵌 `db.lif`（含 4186 primitive、5064 `.g`）

## 5. 里程碑

1. M1：映射列修正 + 多候选消歧 → 客户模型 76257→22463、0 unknown
2. M2：自定义色命名保留 + Studio 写入验证
3. M3：报告区分 + 覆盖率报告
4. M4（后续）：自定义零件 `.g→.dat` 生成装入 Studio（方案 A，超出本模型需求时启动）

## 6. 已知限制

- 本机为 macOS，Studio 数据来自解包 pkg，未在真实 Windows Studio 打开验证（需客户机复验 `.lxf` 打开效果）
- 60602d 等极少数映射无官方 `.dat`，需 `.g→.dat` 生成兜底（M4）
- 76257 柔性件含多 Bone，几何与 Studio 一致故无需补偿；其他柔性件需按模型复验
