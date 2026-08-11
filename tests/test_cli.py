import os
from lddstudio.cli import main, build_mapping_db
from lddstudio.ldd_db import LddDatabase


def test_cli_convert_minimal(tmp_path, monkeypatch):
    import io, zipfile
    lxfml = b'<LXFML name="t"><Bricks></Bricks></LXFML>'
    inp = str(tmp_path / "in.lxf")
    out = str(tmp_path / "out.lxf")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
    open(inp, "wb").write(buf.getvalue())
    rc = main(["convert", inp, out, "--no-fix-transform"])
    assert rc == 0
    assert os.path.exists(out)


def _ldd(names):
    return LddDatabase({}, names, {}, {})


def test_build_mapping_db_with_studio_numbers_exact_match(tmp_path):
    db = build_mapping_db(str(tmp_path / "m.db"), _ldd({"3001": "Brick 2 x 4"}),
                          studio_numbers={"3001"})
    m = db.lookup("3001")
    assert m is not None
    assert m.bl_number == "3001"
    assert m.match_type == "exact"


def test_build_mapping_db_idempotent_and_manual_rows_survive(tmp_path):
    db_path = str(tmp_path / "m.db")
    ldd = _ldd({"3001": "Brick 2 x 4"})
    db1 = build_mapping_db(db_path, ldd, studio_numbers={"3001"})
    assert db1.lookup("3001").match_type == "exact"
    db1.set_manual("99999", "3039")

    db2 = build_mapping_db(db_path, ldd, studio_numbers={"3001"})
    assert db2.lookup("3001").match_type == "exact"
    assert db2.lookup("99999").match_type == "manual"
    assert db2.lookup("99999").bl_number == "3039"

    db3 = build_mapping_db(db_path, ldd, studio_numbers={"3001"}, force_rebuild=True)
    assert db3.lookup("3001").match_type == "exact"
    assert db3.lookup("99999").match_type == "manual"
