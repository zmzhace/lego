import os
import sys

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")


def main():
    from PySide6.QtWidgets import QApplication
    from lddstudio.gui.app import MainWindow
    app = QApplication(sys.argv)
    win = MainWindow(data_dir=_DATA_DIR)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
