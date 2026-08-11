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

## 已知限制
- 变换偏移补偿使用未校准的 studio_center=(0,0,0)；在真实 Studio 安装上完成校验/校准之前，请不要依赖"修复零件乱飞"的默认结果。
