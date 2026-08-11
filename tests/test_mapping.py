import os
import pytest

from lddstudio.mapping import MappingDb

DB = "tmp/mapping_test.db"


@pytest.fixture
def db():
    os.makedirs("tmp", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    d = MappingDb(DB)
    ldd_names = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown Thing"}
    bl_parts = {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}
    bl_numbers = {"3001", "3002"}
    d.rebuild(ldd_names, bl_parts, bl_numbers)
    yield d
    d.close()
    if os.path.exists(DB):
        os.remove(DB)


def test_rebuild_exact_match(db):
    m = db.lookup("3001")
    assert m.bl_number == "3001"
    assert m.match_type == "exact"


def test_rebuild_unmatched_null(db):
    m = db.lookup("99999")
    assert m.bl_number is None
    assert m.match_type == "unmatched"


def test_set_manual_overrides(db):
    db.set_manual("99999", "3039")
    m = db.lookup("99999")
    assert m.bl_number == "3039"
    assert m.match_type == "manual"


def test_rebuild_preserves_manual_row(db):
    db.set_manual("99999", "3039")
    db.rebuild({"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown"},
               {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}, {"3001", "3002"})
    m = db.lookup("99999")
    assert m.bl_number == "3039"
    assert m.match_type == "manual"


def test_rebuild_still_rebuilds_non_manual_rows(db):
    db.set_manual("99999", "3039")
    db.conn.execute("UPDATE parts SET bl_number='12345' WHERE design_id='3001'")
    db.conn.commit()
    db.rebuild({"3001": "Brick 2 x 4", "3002": "Brick 2 x 3", "99999": "Unknown"},
               {"3001": "Brick 2 x 4", "3002": "Brick 2 x 3"}, {"3001", "3002"})
    assert db.lookup("3001").bl_number == "3001"
    assert db.lookup("3001").match_type == "exact"
    assert db.lookup("99999").match_type == "manual"


def test_export_import_csv(db):
    db.set_manual("99999", "3039")
    db.export_csv("tmp/map.csv")
    db.close()
    if os.path.exists(DB):
        os.remove(DB)
    db2 = MappingDb(DB)
    db2.import_csv("tmp/map.csv")
    try:
        assert db2.lookup("99999").bl_number == "3039"
    finally:
        db2.close()


def test_seed_from_studio_sets_exact(tmp_path):
    d = MappingDb(str(tmp_path / "s.db"))
    try:
        d.seed_from_studio({"3001": "3001", "10048": "10048"})
        m = d.lookup("3001")
        assert m.bl_number == "3001"
        assert m.match_type == "exact"
        assert d.lookup("10048").bl_number == "10048"
    finally:
        d.close()


def test_seed_from_studio_preserves_manual(tmp_path):
    d = MappingDb(str(tmp_path / "s.db"))
    try:
        d.set_manual("3001", "9999")
        d.seed_from_studio({"3001": "3001"})
        assert d.lookup("3001").bl_number == "9999"
        assert d.lookup("3001").match_type == "manual"
    finally:
        d.close()


def test_seed_from_studio_keeps_exact_without_force(tmp_path):
    d = MappingDb(str(tmp_path / "s.db"))
    try:
        d.seed_from_studio({"3001": "3001"})
        # change the bl_number manually, rebuild without force should not clobber
        d.conn.execute("UPDATE parts SET bl_number='7777' WHERE design_id='3001'")
        d.conn.commit()
        d.seed_from_studio({"3001": "3001"})
        assert d.lookup("3001").bl_number == "7777"
        d.seed_from_studio({"3001": "3001"}, force=True)
        assert d.lookup("3001").bl_number == "3001"
    finally:
        d.close()


def test_fill_fuzzy_gaps_preserves_exact(tmp_path):
    d = MappingDb(str(tmp_path / "f.db"))
    try:
        d.seed_from_studio({"3001": "3001"})
        d.fill_fuzzy_gaps({"3001": "Brick 2 x 4", "3002": "Brick 2 x 3",
                           "99999": "Unknown Thing"},
                          {"3002": "Brick 2 x 3"}, {"3002"})
        assert d.lookup("3001").bl_number == "3001"
        assert d.lookup("3001").match_type == "exact"
        assert d.lookup("3002").bl_number == "3002"
        assert d.lookup("3002").match_type == "exact"
        assert d.lookup("99999").bl_number is None
    finally:
        d.close()
