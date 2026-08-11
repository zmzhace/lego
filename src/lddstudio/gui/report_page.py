from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTableWidget, \
    QTableWidgetItem, QListWidget


class ReportPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.replaced_table = QTableWidget(0, 2)
        self.replaced_table.setHorizontalHeaderLabels(["原 DesignID", "Studio 编号"])
        self.unmatched_list = QListWidget()
        self.custom_list = QListWidget()
        self.tabs.addTab(self.replaced_table, "替换记录")
        self.tabs.addTab(self.unmatched_list, "未匹配")
        self.tabs.addTab(self.custom_list, "自定义色")
        layout.addWidget(self.tabs)

    def set_report(self, report):
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
