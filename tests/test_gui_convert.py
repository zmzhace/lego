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
    assert page.status_label is not None


def test_custom_color_checkbox_writes_xml(app, tmp_path, monkeypatch):
    import zipfile
    from lddstudio.gui import convert_page
    from lddstudio.ldd_db import LddDatabase

    db_path = str(tmp_path / "seed.db")
    monkeypatch.setattr(convert_page, "default_db_path", lambda: db_path)
    monkeypatch.setattr(convert_page, "find_ldd_db", lambda: str(tmp_path / "fake_db"))
    monkeypatch.setattr(convert_page, "load_ldd_database", lambda p: LddDatabase({}, {"3001": "Brick 2 x 4"}, {}, {}))
    monkeypatch.setattr(convert_page, "find_studio_dir", lambda: "")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with open(str(data_dir / "ldd_to_bl_colors.csv"), "w", encoding="utf-8") as f:
        f.write("LDD_ID,BL_ID,R,G,B,Material\n")
        f.write("5,2,211,188,141,Solid\n")

    lxfml = (b'<LXFML name="t"><Bricks>'
             b'<Brick refID="1" designID="3001"><Part refID="2" designID="3001" '
             b'materials="99"><Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/>'
             b'</Part></Brick></Bricks></LXFML>')
    inp = str(tmp_path / "in.lxf")
    out = str(tmp_path / "out.lxf")
    with zipfile.ZipFile(inp, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)

    page = ConvertPage(report_sink=lambda r: None, data_dir=str(data_dir))
    page.custom_color_chk.setChecked(True)
    page.input_edit.setText(inp)
    page.output_edit.setText(out)
    page.on_convert()

    cc_path = tmp_path / "studio_custom_colors.xml"
    assert cc_path.exists()
    content = cc_path.read_text(encoding="utf-8")
    assert "C99" in content
    assert str(cc_path) in page.status_label.text()
