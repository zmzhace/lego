import struct
from lddstudio.ldd_db import (LIFReader, LOCReader, LddDatabase,
                              load_ldd_database, parse_materials_xml,
                              parse_primitive_xml)

def make_lif(entries: dict) -> bytes:
    # 极简 LIFF：跳过目录表解析，直接构造 "LIFF" + 无目录
    return b"LIFF" + b"\x00" * 80 + bytes(0)

def test_loc_reader_parses_names():
    # "2\0" + "Material5\0" + "Red\0" + "0\0"
    data = b"2\x00Material5\x00Red\x00\x00"
    loc = LOCReader(data)
    assert loc.values == {"5": "Red"}

def test_parse_materials_xml():
    xml = b'<Materials><Material MatID="5" Red="196" Green="0" Blue="38" Alpha="255" MaterialType="Solid"/></Materials>'
    mats = parse_materials_xml(xml)
    assert mats["5"].r == 196
    assert mats["5"].material_type == "Solid"
    assert mats["5"].name == ""

def test_parse_primitive_xml():
    xml = b'''<Primitives><Annotation><designname>Brick 2x4</designname></Annotation>
    <Bounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></Bounding>
    <GeometryBounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></GeometryBounding>
    </Primitives>'''
    p = parse_primitive_xml(xml)
    assert p.design_name == "Brick 2x4"
    assert p.bounding["maxX"] == "31.8"

def test_parse_materials_xml_bad_color_falls_back():
    xml = b'<Materials><Material MatID="7" Red="abc" Green="0" Blue="38" Alpha="255" MaterialType="Solid"/></Materials>'
    mats = parse_materials_xml(xml)
    assert mats["7"].r == 0
    assert mats["7"].material_type == "Solid"

def test_load_ldd_database_folder_survives_bad_entries(tmp_path):
    (tmp_path / "Materials.xml").write_bytes(b"<Materials>")
    prim_dir = tmp_path / "Primitives"
    prim_dir.mkdir()
    (prim_dir / "3001.xml").write_bytes(
        b'<Primitives><Annotation><designname>Brick 2x4</designname></Annotation>'
        b'<Bounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></Bounding>'
        b'<GeometryBounding><AABB minX="0" minY="0" minZ="0" maxX="31.8" maxY="15.8" maxZ="7.8"/></GeometryBounding></Primitives>')
    (prim_dir / "bad.xml").write_bytes(b"<Primitives>")
    db = load_ldd_database(str(tmp_path))
    assert isinstance(db, LddDatabase)
    assert db.primitive("/Primitives/3001.xml").design_name == "Brick 2x4"
    assert "/Primitives/bad.xml" not in db._primitives
