# LDD → Studio 转换工具

Windows 桌面工具：读取 LDD `.lxf` 工程，修复零件编号/颜色/变换矩阵后输出干净 `.lxf`，
由 Studio 2.0 自带导入打开，无问号、无乱飞，BOM 准确。

## 核心原理：使用 Studio 官方数据做精确映射

转换基于 Studio 2.0 自带的权威数据文件（`<StudioDir>/data/`），而非猜测：

| 文件 | 内容 | 解决的问题 |
|------|------|-----------|
| `StudioPartDefinition2.txt` | LDD designID → Studio/BL/LDraw 编号 + 名称（2414 条） | 零件变问号、BOM 编号准确 |
| `ldraw_lxfml_mapping.json` | 每个零件的旋转（度）+ 平移（LDU）修正量（5349 条） | 零件乱飞（几何原点不同） |
| `StudioColorDefinition.txt` | LDD 颜色代码 → Studio/BL/LDraw 颜色 + RGB（260 条） | 颜色互通、BOM 颜色准确 |
| `ldraw_new.xml` | Assembly 组装件映射（93 条） | 填补轮子/人仔等组装件缺口 |

实测覆盖：LDD 调色板 2154 个零件中 **2154 个全部精确映射（100%）**，
颜色 198 个 LDD 色码精确对应 Studio 颜色。

## 使用
1. 首次运行自动探测 LDD 数据库与 Studio 2.0 目录
   （也可用环境变量 `LDDSTUDIO_LDD_DB` / `LDDSTUDIO_STUDIO_DIR` 指定）
2. 转换页选择 .lxf → 输出路径 → 转换
3. 报告页查看替换/未匹配/自定义色；未匹配可右键手动指定编号
4. 输出文件用 Studio 2.0 打开

## 开发
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest PySide6 lxml
pytest tests/

## 已知限制
- LDD 数据库 `db.lif` 在 LDD 运行时被独占锁定，此时只能使用 Studio 数据做映射；
  零件名称/几何数据需关闭 LDD 后才能读取（未匹配项会保留原编号并在报告中列出）。
- 变换偏移的旋转约定（XYZ 欧拉角顺序）已按 Studio 数据实现，
  但仍建议在真实 Studio 中导入一次输出文件做最终校准。
