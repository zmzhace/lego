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
