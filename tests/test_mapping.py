import os
from lddstudio.mapping import MappingDb

DB = "tmp/mapping_test.db"

def make_db():
    os.makedirs("tmp", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    db = MappingDb(DB)
    ldd_names = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown Thing"}
    bl_parts = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}
    bl_numbers = {"3001", "3002"}
    db.rebuild(ldd_names, bl_parts, bl_numbers)
    return db

def test_rebuild_exact_match():
    db = make_db()
    m = db.lookup("3001")
    assert m.bl_number == "3001"
    assert m.match_type == "exact"

def test_rebuild_unmatched_null():
    db = make_db()
    m = db.lookup("99999")
    assert m.bl_number is None
    assert m.match_type == "unmatched"

def test_set_manual_overrides():
    db = make_db()
    db.set_manual("99999", "3039")
    m = db.lookup("99999")
    assert m.bl_number == "3039"
    assert m.match_type == "manual"

def test_rebuild_preserves_manual_row():
    db = make_db()
    db.set_manual("99999", "3039")
    db.rebuild({"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown"},
               {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}, {"3001", "3002"})
    m = db.lookup("99999")
    assert m.bl_number == "3039"
    assert m.match_type == "manual"

def test_rebuild_still_rebuilds_non_manual_rows():
    db = make_db()
    db.set_manual("99999", "3039")
    db.conn.execute("UPDATE parts SET bl_number='12345' WHERE design_id='3001'")
    db.conn.commit()
    db.rebuild({"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown"},
               {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}, {"3001", "3002"})
    assert db.lookup("3001").bl_number == "3001"
    assert db.lookup("3001").match_type == "exact"
    assert db.lookup("99999").match_type == "manual"

def test_export_import_csv():
    db = make_db()
    db.set_manual("99999", "3039")
    db.export_csv("tmp/map.csv")
    os.remove(DB)
    db2 = MappingDb(DB)
    db2.import_csv("tmp/map.csv")
    assert db2.lookup("99999").bl_number == "3039"
