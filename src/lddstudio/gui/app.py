from PySide6.QtWidgets import QMainWindow, QTabWidget, QLabel
from .convert_page import ConvertPage
from .report_page import ReportPage
from .library_page import LibraryPage


class MainWindow(QMainWindow):
    def __init__(self, data_dir=""):
        super().__init__()
        self.setWindowTitle("LDD → Studio 转换工具")
        self.tabs = QTabWidget()
        self.report_page = ReportPage()
        self.convert_page = ConvertPage(report_sink=self.report_page.set_report, data_dir=data_dir)
        self.library_page = LibraryPage()
        self.tabs.addTab(self.convert_page, "转换")
        self.tabs.addTab(self.report_page, "报告")
        self.tabs.addTab(self.library_page, "映射库")
        self.setCentralWidget(self.tabs)
        self.resize(760, 520)
