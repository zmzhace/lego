# LDD → Studio 一键迁移工具

给客户的 Windows 桌面工具：**一个按钮**把 LDD `.lxf` 工程转成 Studio 2.0 能正确打开的文件——
无问号零件、无乱飞、自定义颜色自动迁移、BOM 准确。

## 客户使用方法（一键）
1. 双击打开程序（无需配置，自动探测本机 LDD 与 Studio 2.0）
2. 点"浏览"选择 LDD 工程 `.lxf`
3. 点"一键迁移"
4. 输出文件（`原文件名_studio.lxf`）生成在源文件旁；自定义颜色自动注册到 Studio
5. **重启 Studio 2.0** → 用 Studio 打开输出文件（Studio 会自动应用已注册的自定义颜色）

## 核心原理：使用 Studio 官方数据做精确映射

转换基于 Studio 2.0 自带的权威数据文件（`<StudioDir>/data/`），而非猜测：

| 文件 | 内容 | 解决的问题 |
|------|------|-----------|
| `StudioPartDefinition2.txt` | LDD designID → Studio/BL/LDraw 编号 + 名称（2414 条） | 零件变问号、BOM 编号准确 |
| `ldraw_lxfml_mapping.json` | 每个零件的旋转（度）+ 平移（LDU）修正量（5349 条） | 零件乱飞（几何原点不同） |
| `StudioColorDefinition.txt` | LDD 颜色代码 → Studio/BL/LDraw 颜色 + RGB（260 条） | 颜色互通、BOM 颜色准确 |
| `ldraw_new.xml` | Assembly 组装件映射（93 条） | 填补轮子/人仔等组装件缺口 |

实测覆盖（真实环境验证）：
- **零件**：LDD 数据库全部 2586 个零件中 **2584 个（99.92%）精确映射**。
  仅 2 个为 LDD 独有、Studio 无对应物的零件（DUPLO 轴 71956、设计辅助点 73914），
  按"未匹配不猜"原则保留原编号并列入报告；LDD 调色板 2154 个零件 100% 映射
- **变换**：2487 个零件有 Studio 官方旋转/平移修正量（1101 个含旋转）
- **颜色**：198 个 LDD 色码精确对应 Studio 颜色
- **自定义颜色**：LDD 自定义材料自动分配 Studio 色码（520xxx 高位区），
  写入 Studio 的 `CustomColorDefinition.txt`，重启后 Studio 即可识别

真实模型回归（`tests/fixtures/models/`）：
- 21 个从 GitHub 下载的真实 LDD 模型全部转换通过（含 15000 件马赛克、4608 件蒙娜丽莎、2136 件 Grand Emporium、1318 件福特野马）
- 每项断言：零件数不变、0 未匹配、输出编号全部存在于 Studio 零件库
- 批量压力测试见 `pytest tests/test_real_models.py`

随机极限压力测试（`pytest tests/test_stress.py`）：
- 用真实 LDD 零件 + 随机旋转/平移矩阵生成 120 个随机模型，覆盖多材质（含 `0` 槽）、
  变换偏移零件、自定义颜色、未匹配编号注入、1~600 件各种规模
- 断言：0 崩溃、零件数不变、仅预期的孤儿/注入编号未匹配、输出编号全部被 Studio 识别
- 一次性跑过 300 个模型 / 16 万零件验证（100% 通过）

## 开发
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest PySide6 lxml
pytest tests/

打包给客户：
pyinstaller build.spec

## 已知限制
- LDD 数据库 `db.lif` 在 LDD 运行时被独占锁定，此时只能使用 Studio 数据做映射；
  关闭 LDD 后可读取全部零件名/几何数据（覆盖率 99.92%）。
- 2 个 LDD 独有零件（DUPLO 轴 71956、设计辅助点 73914）在 Studio 无对应物，
  保留原编号列入报告；其余零件 100% 映射。
- 变换偏移的旋转约定（XYZ 欧拉角顺序）已按 Studio 数据实现，
  但仍建议在真实 Studio 中导入一次输出文件做最终校准。
