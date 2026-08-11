from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, \
    QTableWidgetItem, QListWidget, QInputDialog, QMenu
from ..mapping import MappingDb, default_db_path


class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._report = None
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.replaced_table = QTableWidget(0, 2)
        self.replaced_table.setHorizontalHeaderLabels(["原 DesignID", "Studio 编号"])
        self.unmatched_list = QListWidget()
        self.unmatched_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.unmatched_list.customContextMenuRequested.connect(self._on_ctx)
        self.custom_list = QListWidget()
        self.tabs.addTab(self.replaced_table, "替换记录")
        self.tabs.addTab(self.unmatched_list, "未匹配")
        self.tabs.addTab(self.custom_list, "自定义色")
        layout.addWidget(self.tabs)

    def set_report(self, report):
        self._report = report
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

    def _refresh_unmatched(self):
        if not self._report:
            return
        db = MappingDb(default_db_path())
        self.unmatched_list.clear()
        for m in self._report.unmatched:
            cur = db.lookup(m.design_id)
            if cur and cur.bl_number:
                continue
            self.unmatched_list.addItem("{} ({})".format(m.design_id, m.name))
