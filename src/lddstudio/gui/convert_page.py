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
