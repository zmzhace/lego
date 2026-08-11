import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QCheckBox,
                               QProgressBar, QMessageBox)

from ..cli import build_mapping_db, find_studio_data_dir
from ..converter import convert
from ..colors import ColorProcessor, load_bl_color_map
from ..ldd_db import find_ldd_db, load_ldd_database
from ..mapping import MappingDb, default_db_path
from ..studio_lib import find_studio_dir, scan_studio_part_numbers
from ..studio_data import load_color_definition, load_transform_offsets, \
    studio_colors_for_ldd
from ..transform import TransformFixer


def _studio_custom_definition_path(studio_data_dir):
    """Locate Studio's CustomColorDefinition.txt to register custom colors."""
    if not studio_data_dir:
        return ""
    candidates = [
        os.path.join(studio_data_dir, "CustomColors", "CustomColorDefinition.txt"),
        os.path.join(studio_data_dir, "CustomColorDefinition.txt"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return os.path.join(studio_data_dir, "CustomColors", "CustomColorDefinition.txt")


def _existing_custom_codes(studio_data_dir):
    """Collect Studio color codes already present in the definition files."""
    codes = set()
    for fname in ("StudioColorDefinition.txt", "CustomColorDefinition.txt"):
        p = os.path.join(studio_data_dir, fname)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                cells = line.split("\t")
                if cells and cells[0].strip().isdigit():
                    codes.add(int(cells[0].strip()))
    return codes


class ConvertPage(QWidget):
    def __init__(self, report_sink=None, data_dir="", parent=None):
        super().__init__(parent)
        self.report_sink = report_sink
        self.data_dir = data_dir
        layout = QVBoxLayout(self)

        intro = QLabel(
            "一键迁移：选择 LDD 工程 (.lxf)，自动转换并在 Studio 中正确显示。\n"
            "输出文件会自动生成，无需手动指定。")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.detect_label = QLabel("")
        self.detect_label.setStyleSheet("color: #2a7f2a;")
        layout.addWidget(self.detect_label)
        self._refresh_detect()

        row = QHBoxLayout()
        row.addWidget(QLabel("LDD 工程:"))
        self.input_edit = QLineEdit()
        row.addWidget(self.input_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._pick_input)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        self.fix_transform_chk = QCheckBox("修复零件乱飞")
        self.fix_transform_chk.setChecked(True)
        self.custom_color_chk = QCheckBox("迁移自定义颜色到 Studio")
        self.custom_color_chk.setChecked(True)
        layout.addWidget(self.fix_transform_chk)
        layout.addWidget(self.custom_color_chk)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.run_btn = QPushButton("一键迁移")
        self.run_btn.clicked.connect(self.on_convert)
        layout.addWidget(self.run_btn)

    def _refresh_detect(self):
        parts = []
        ldd = find_ldd_db()
        if ldd:
            parts.append("LDD 数据库 ✓")
        else:
            parts.append("LDD 未找到")
        studio = find_studio_dir()
        if studio:
            parts.append("Studio 2.0 ✓")
        else:
            parts.append("Studio 2.0 未找到")
        self.detect_label.setText("  ".join(parts))

    def _pick_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 LDD 工程", "", "LDD (*.lxf)")
        if path:
            self.input_edit.setText(path)

    def on_convert(self):
        inp = self.input_edit.text().strip()
        if not inp:
            QMessageBox.warning(self, "提示", "请先选择 LDD 工程文件 (.lxf)")
            return
        if not os.path.isfile(inp):
            QMessageBox.warning(self, "提示", "文件不存在: {}".format(inp))
            return
        self.progress.setValue(5)
        base, ext = os.path.splitext(inp)
        out = base + "_studio" + (ext or ".lxf")
        if os.path.abspath(out) == os.path.abspath(inp):
            out = base + "_studio.lxf"

        ldd_path = find_ldd_db()
        ldd_db = load_ldd_database(ldd_path) if ldd_path else None
        if ldd_db is None:
            from ..ldd_db import LddDatabase
            ldd_db = LddDatabase({}, {}, {}, {})
        self.progress.setValue(15)

        studio_dir = find_studio_dir()
        studio_data_dir = find_studio_data_dir()
        try:
            db = self._seed_mapping(ldd_db, studio_data_dir, studio_dir)
        except Exception as e:
            QMessageBox.critical(self, "映射库构建失败", str(e))
            return
        self.progress.setValue(45)

        bl_map = load_bl_color_map(os.path.join(self.data_dir, "ldd_to_bl_colors.csv"))
        studio_colors = studio_colors_for_ldd(
            load_color_definition(studio_data_dir)) if studio_data_dir else {}
        existing_codes = _existing_custom_codes(studio_data_dir)
        cp = ColorProcessor(bl_map, studio_colors, ldd_db.materials,
                            studio_color_map=studio_colors,
                            existing_custom_codes=existing_codes)
        offsets = load_transform_offsets(studio_data_dir) if studio_data_dir else {}
        fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)
        self.progress.setValue(60)

        try:
            rep = convert(inp, out, db, ldd_db, cp, fixer,
                          fix_transform=self.fix_transform_chk.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "转换失败", str(e))
            return
        self.progress.setValue(85)

        msg = "迁移完成，输出文件:\n{}\n\n替换 {} 条零件，未匹配 {} 条".format(
            out, len(rep.replaced), len(rep.unmatched))
        if self.custom_color_chk.isChecked() and rep.custom_colors:
            custom_def = _studio_custom_definition_path(studio_data_dir)
            if custom_def:
                try:
                    n = cp.append_to_custom_definition(rep.custom_colors, custom_def)
                    msg += "\n\n已注册 {} 条自定义颜色到 Studio:\n{}".format(n, custom_def)
                    msg += "\n重启 Studio 后即可看到这些颜色。"
                except OSError as e:
                    msg += "\n\n自定义颜色注册失败: {}".format(e)
            else:
                msg += "\n\n未找到 Studio 自定义颜色定义文件，颜色未注册。"
        self.progress.setValue(100)
        self.status_label.setText(msg)
        if self.report_sink:
            self.report_sink(rep)

    def _seed_mapping(self, ldd_db=None, studio_data_dir="", studio_dir=""):
        if ldd_db is None:
            ldd_path = find_ldd_db()
            ldd_db = load_ldd_database(ldd_path) if ldd_path else None
            if ldd_db is None:
                from ..ldd_db import LddDatabase
                ldd_db = LddDatabase({}, {}, {}, {})
        csv_path = os.path.join(self.data_dir, "parts.csv.gz")
        rebrickable_csv = csv_path if os.path.exists(csv_path) else None
        studio_numbers = scan_studio_part_numbers(studio_dir or find_studio_dir())
        build_mapping_db(default_db_path(), ldd_db, rebrickable_csv=rebrickable_csv,
                         studio_numbers=studio_numbers,
                         studio_data_dir=studio_data_dir or find_studio_data_dir())
        return MappingDb(default_db_path())
