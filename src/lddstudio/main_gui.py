import sys

from .resources import data_dir


def main():
    from PySide6.QtWidgets import QApplication
    from lddstudio.gui.app import MainWindow
    app = QApplication(sys.argv)
    win = MainWindow(data_dir=data_dir())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
