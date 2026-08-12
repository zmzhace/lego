import csv
import gzip
import io
import os
import zipfile
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from lddstudio.mapping import MappingDb, default_db_path
from lddstudio.gui.library_page import LibraryPage

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

def test_library_page_refreshes(app, tmp_path, monkeypatch):
    monkeypatch.setattr("lddstudio.gui.library_page.default_db_path", lambda: str(tmp_path / "m.db"))
    db = MappingDb(str(tmp_path / "m.db"))
    db.rebuild({"3001": "Brick 2 x 4"}, {"3001": "Brick 2 x 4"}, {"3001"})
    page = LibraryPage()
    assert page.table.rowCount() == 1


def _make_ldd_db():
    from lddstudio.ldd_db import LddDatabase
    return LddDatabase({}, {"3001": "Brick 2 x 4"}, {}, {})


def _make_input_lxf(path):
    lxfml = (b'<LXFML name="t"><Bricks>'
             b'<Brick refID="1" designID="3001"><Part refID="2" designID="3001" '
             b'materials="5"><Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/>'
             b'</Part></Brick></Bricks></LXFML>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)


def _make_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with open(str(data_dir / "ldd_to_bl_colors.csv"), "w", encoding="utf-8") as f:
        f.write("LDD_ID,BL_ID,R,G,B,Material\n")
        f.write("5,2,211,188,141,Solid\n")
    buf = io.BytesIO()
    with gzip.open(buf, "wt", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["part_num", "name"])
        w.writerow(["3001", "Brick 2 x 4"])
    open(str(data_dir / "parts.csv.gz"), "wb").write(buf.getvalue())
    return data_dir


def test_gui_seed_mapping_matches_known_part(app, tmp_path, monkeypatch):
    from lddstudio.gui import convert_page
    from lddstudio.gui.convert_page import ConvertPage
    db_path = str(tmp_path / "seed.db")
    monkeypatch.setattr(convert_page, "default_db_path", lambda: db_path)
    monkeypatch.setattr(convert_page, "find_ldd_db", lambda: str(tmp_path / "fake_db"))
    monkeypatch.setattr(convert_page, "load_ldd_database", lambda p: _make_ldd_db())
    data_dir = _make_data_dir(tmp_path)
    page = ConvertPage(report_sink=lambda r: None, data_dir=str(data_dir))

    db = page._seed_mapping()
    m = db.lookup("3001")
    assert m is not None and m.bl_number == "3001" and m.match_type == "exact"

    inp = str(tmp_path / "in.lxf")
    out = str(tmp_path / "in_studio.lxf")
    _make_input_lxf(inp)
    reports = []
    page.report_sink = reports.append
    page.input_edit.setText(inp)
    page.on_convert()
    assert reports
    assert all(m.design_id != "3001" for m in reports[0].unmatched)
    assert os.path.exists(out)


def test_custom_definition_path_prefers_program_data(tmp_path):
    from lddstudio.gui.convert_page import _studio_custom_definition_path
    pd = tmp_path / "ProgramData"
    (pd / "Studio" / "CustomColors").mkdir(parents=True)
    (pd / "Studio" / "CustomColors" / "CustomColorDefinition.txt").write_text("", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    p = _studio_custom_definition_path(str(data_dir), str(pd))
    assert "CustomColors" in p
    assert p.endswith("CustomColorDefinition.txt")


def test_existing_custom_codes_includes_program_data_write_file(tmp_path):
    from lddstudio.gui.convert_page import (_existing_custom_codes,
                                            _studio_custom_definition_path)
    pd = tmp_path / "ProgramData"
    pd_dir = pd / "Studio" / "CustomColors"
    pd_dir.mkdir(parents=True)
    (pd_dir / "CustomColorDefinition.txt").write_text(
        "Studio Color Code\tBL Color Code\tStudio Color Name\n"
        "520000\t\t\tMy Red\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "CustomColorDefinition.txt").write_text(
        "520001\t\t\tMy Blue\n", encoding="utf-8")
    (data_dir / "StudioColorDefinition.txt").write_text(
        "520002\t\t\tMy Green\n", encoding="utf-8")

    write_file = _studio_custom_definition_path(str(data_dir), str(pd))
    codes = _existing_custom_codes(
        write_file,
        os.path.join(str(data_dir), "StudioColorDefinition.txt"),
        os.path.join(str(data_dir), "CustomColorDefinition.txt"))
    assert 520000 in codes
    assert 520001 in codes
    assert 520002 in codes
