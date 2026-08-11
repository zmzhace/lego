import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from lddstudio.gui.convert_page import ConvertPage

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_convert_page_has_widgets(app):
    page = ConvertPage()
    assert page.input_edit is not None
    assert page.output_edit is not None
