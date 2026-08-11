from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, \
    QLineEdit, QLabel, QInputDialog, QMenu
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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_ctx)
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
