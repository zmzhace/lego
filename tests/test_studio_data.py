import json
import os

from lddstudio.studio_data import (
    load_part_definition,
    build_ldd_to_bl_map,
    load_transform_offsets,
    load_color_definition,
    build_ldd_color_map,
    studio_colors_for_ldd,
    rgb_tuple,
    _ldraw_no_to_bl,
    load_studio_mapping,
    build_ldd_to_bl_from_filenames,
    load_assembly_mapping,
    load_transformation_mapping,
    load_alternate_design_ids,
    build_official_dat_index,
    disambiguate_candidates,
)

PARTDEF_HEADER = (
    "Studio ItemNo\tBaseStudioItemNo\tBL ItemNo\tBL ItemKey\tLDraw ItemNo\t"
    "LDD ItemNo\tDescription\tisPerfectForCulling\tBLCatalogIndex\t"
    "BLCatalogSubIndex\tEasyModeIndex\tIsAssembly?\tflexible type\tIsDecorated\t"
    "XPCatalogIndex\tXPCatalogSubIndex"
)


def make_partdef(rows):
    lines = [PARTDEF_HEADER]
    lines.extend(rows)
    return "\n".join(lines)


def test_parse_part_definition(tmp_path):
    content = make_partdef([
        "264\t264\t3001\t264\t3001.dat\t3001\tBrick 2 x 4\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
        "999\t999\t3002\t999\t3002.dat\t3002\tBrick 2 x 3\to\t13\t1\t1\tFalse\t\tFalse\t5002\t",
        "110125\t110125\t10048\t110125\t10048.dat\t10048\tMinifigure, Hair Tousled\to\t0\t0\t0\tFalse\t\tFalse\t\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    rows = load_part_definition(str(tmp_path))
    assert len(rows) == 3
    assert rows[0].ldd_no == "3001"
    assert rows[0].bl_no == "3001"
    assert rows[0].description == "Brick 2 x 4"


def test_parse_part_definition_skips_header_and_empty(tmp_path):
    content = PARTDEF_HEADER + "\n\n" + "only\tone\tcol\n"
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    rows = load_part_definition(str(tmp_path))
    assert rows == []


def test_build_ldd_to_bl_map_prefers_bl(tmp_path):
    content = make_partdef([
        "264\t264\t3001\t264\t3001.dat\t3001\tBrick 2 x 4\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    m = build_ldd_to_bl_map(load_part_definition(str(tmp_path)))
    assert m["3001"] == "3001"


def test_ldraw_no_to_bl():
    assert _ldraw_no_to_bl("3001.dat") == "3001"
    assert _ldraw_no_to_bl("bl_973pb1234c01.dat") == "bl_973pb1234c01"


def test_load_transform_offsets(tmp_path):
    data = [
        {"type": "transformation",
         "ldraw": {"filename": "41823.dat", "colors": []},
         "ldd": {"designId": 41823},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 10.0, "y": -48.0, "z": 50.0}},
        {"type": "transformation",
         "ldraw": {"filename": "44740.dat", "colors": []},
         "ldd": {"designId": 44740},
         "rotation": {"unit": "degree", "x": 0.0, "y": 90.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": -5.0, "z": 0.0}},
        {"type": "decoration",
         "ldraw": {"filename": "3001.dat", "colors": []},
         "ldd": {"designId": 3001},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": 0.0, "z": 0.0}},
    ]
    (tmp_path / "ldraw_lxfml_mapping.json").write_text(json.dumps(data), encoding="utf-8")
    offsets = load_transform_offsets(str(tmp_path))
    assert len(offsets) == 2  # decoration skipped
    assert offsets["41823"].tx == 10.0
    assert offsets["41823"].ty == -48.0
    assert offsets["41823"].tz == 50.0
    assert offsets["44740"].ry == 90.0
    assert "3001" not in offsets


def test_load_transform_offsets_bad_file(tmp_path):
    (tmp_path / "ldraw_lxfml_mapping.json").write_text("not json", encoding="utf-8")
    assert load_transform_offsets(str(tmp_path)) == {}
    assert load_transform_offsets(str(tmp_path / "missing")) == {}


COLORDEF_HEADER = (
    "Studio Color Code\tBL Color Code\tLDraw Color Code\tLDD color code\t"
    "Studio Color Name\tBL Color Name\tLDraw Color Name\tLDD Color Name\t"
    "RGB value\tAlpha\tCategoryName\tColor Group Index\tnote\tIns_RGB\tIns_CMYK"
)


def test_load_color_definition(tmp_path):
    content = "\n".join([
        COLORDEF_HEADER,
        "11\t11\t0\t26\tBlack\tBlack\tBlack\tBlack\t#04121C\t1\tSolid Colors\t-1\to\t\t86,36,0,89",
        "7\t7\t1\t23\tBlue\tBlue\tBlue\tBright Blue\t#0054BE\t1\tSolid Colors\t17\to\t\t100,56,0,25",
    ])
    (tmp_path / "StudioColorDefinition.txt").write_text(content, encoding="utf-8")
    colors = load_color_definition(str(tmp_path))
    assert len(colors) == 2
    assert colors[0].ldd_code == "26"
    assert colors[0].studio_code == "11"
    assert colors[0].rgb == "#04121C"


def test_build_ldd_color_map_prefers_official(tmp_path):
    content = "\n".join([
        COLORDEF_HEADER,
        "11\t11\t0\t26\tBlack\tBlack\tBlack\tBlack\t#04121C\t1\tSolid Colors\t-1\to\t\t86,36,0,89",
        "11\t\t0\t1012\tBlack\t\tBlack\tCONDUCT.Black\t#04121C\t1\tSolid Colors\t-1\tfrom_lego\t\t",
    ])
    (tmp_path / "StudioColorDefinition.txt").write_text(content, encoding="utf-8")
    m = build_ldd_color_map(load_color_definition(str(tmp_path)))
    assert m["26"].studio_code == "11"
    assert m["26"].note == "o"
    assert m["1012"].studio_code == "11"


def test_studio_colors_for_ldd(tmp_path):
    content = "\n".join([
        COLORDEF_HEADER,
        "5\t5\t4\t21\tRed\tRed\tRed\tBright red\t#C81908\t1\tSolid Colors\t1\to\t\t0,88,96,22",
    ])
    (tmp_path / "StudioColorDefinition.txt").write_text(content, encoding="utf-8")
    m = studio_colors_for_ldd(load_color_definition(str(tmp_path)))
    assert m["21"] == ("5", (200, 25, 8), "Red")


def test_rgb_tuple():
    assert rgb_tuple("#04121C") == (4, 18, 28)
    assert rgb_tuple("04121C") == (4, 18, 28)
    assert rgb_tuple("garbage") == (0, 0, 0)
    assert rgb_tuple("") == (0, 0, 0)


def test_missing_files_return_empty(tmp_path):
    assert load_part_definition(str(tmp_path)) == []
    assert load_transform_offsets(str(tmp_path)) == {}
    assert load_color_definition(str(tmp_path)) == []


def test_build_ldd_to_bl_from_filenames():
    pairs = [("41823", "41823.dat"), ("44740", "44740.dat"),
             ("25375", "25375-f1.dat"), ("76382", "bl_973c94.dat")]
    m = build_ldd_to_bl_from_filenames(pairs)
    assert m["41823"] == "41823"
    assert m["44740"] == "44740"
    assert m["25375"] == "25375-f1"
    assert m["76382"] == "bl_973c94"


def test_load_studio_mapping_combines_sources(tmp_path):
    content = make_partdef([
        "264\t264\t3001\t264\t3001.dat\t3001\tBrick 2 x 4\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    data = [
        {"type": "transformation",
         "ldraw": {"filename": "41823.dat", "colors": []},
         "ldd": {"designId": 41823},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 10.0, "y": -48.0, "z": 50.0}},
        {"type": "transformation",
         "ldraw": {"filename": "44740.dat", "colors": []},
         "ldd": {"designId": 44740},
         "rotation": {"unit": "degree", "x": 0.0, "y": 90.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": -5.0, "z": 0.0}},
    ]
    (tmp_path / "ldraw_lxfml_mapping.json").write_text(json.dumps(data), encoding="utf-8")
    ldd_to_bl, offsets, filenames = load_studio_mapping(str(tmp_path))
    assert ldd_to_bl["3001"] == "3001"      # from part definition
    assert ldd_to_bl["41823"] == "41823"    # from transform filenames
    assert ldd_to_bl["44740"] == "44740"
    assert offsets["44740"].ry == 90.0
    assert filenames["41823"] == ["41823.dat"]


def test_load_assembly_mapping(tmp_path):
    (tmp_path / "ldraw_new.xml").write_text(
        '<LDrawMapping><Assembly ldraw="2429c01.dat" lego="73983" type=""/>'
        '<Assembly ldraw="4719c01.dat" lego="73537" type=""/></LDrawMapping>',
        encoding="utf-8")
    m = load_assembly_mapping(str(tmp_path))
    assert m["73983"] == "2429c01"
    assert m["73537"] == "4719c01"


def test_load_studio_mapping_includes_assembly(tmp_path):
    data = [
        {"type": "transformation",
         "ldraw": {"filename": "41823.dat", "colors": []},
         "ldd": {"designId": 41823},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 10.0, "y": -48.0, "z": 50.0}},
    ]
    (tmp_path / "ldraw_lxfml_mapping.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "ldraw_new.xml").write_text(
        '<LDrawMapping><Assembly ldraw="4719c01.dat" lego="73537" type=""/></LDrawMapping>',
        encoding="utf-8")
    ldd_to_bl, offsets, _ = load_studio_mapping(str(tmp_path))
    assert ldd_to_bl["73537"] == "4719c01"   # assembly fills the gap
    assert ldd_to_bl["41823"] == "41823"


def test_load_transformation_mapping(tmp_path):
    (tmp_path / "ldraw_new.xml").write_text(
        '<LDrawMapping>'
        '<Transformation ldraw="86209.dat" lego="60601" type="to_lego"/>'
        '<Transformation ldraw="61252.dat" lego="61252" type=""/>'
        '</LDrawMapping>', encoding="utf-8")
    m = load_transformation_mapping(str(tmp_path))
    assert m["60601"] == "86209"
    assert m["61252"] == "61252"


def test_load_studio_mapping_includes_transformation(tmp_path):
    (tmp_path / "ldraw_new.xml").write_text(
        '<LDrawMapping>'
        '<Transformation ldraw="86209.dat" lego="60601" type="to_lego"/>'
        '</LDrawMapping>', encoding="utf-8")
    ldd_to_bl, _, _ = load_studio_mapping(str(tmp_path))
    assert ldd_to_bl["60601"] == "86209"


def test_build_ldd_to_bl_map_prefers_ldraw_filename(tmp_path):
    # BL 号带字母后缀(30237a)，.dat 文件名是父编号(30237.dat)
    content = make_partdef([
        "264\t264\t30237a\t264\t30237.dat\t30237\tBrick, Modified 1 x 2 with Split U Clip Thick\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    m = build_ldd_to_bl_map(load_part_definition(str(tmp_path)))
    assert m["30237"] == "30237"      # 用 .dat 文件名，而非 BL 号 30237a


def test_build_ldd_to_bl_map_fallback_order(tmp_path):
    # 无 .dat 文件名时 fallback BL 号，再 fallback Studio 号
    content = make_partdef([
        "5001\t5001\t3001\t5001\t\t3001\tBrick 2 x 4\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
        "5002\t5002\t\t5002\t\t3002\tBrick 2 x 3\to\t13\t1\t1\tFalse\t\tFalse\t5002\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    m = build_ldd_to_bl_map(load_part_definition(str(tmp_path)))
    assert m["3001"] == "3001"      # fallback bl_no
    assert m["3002"] == "5002"      # fallback studio_no


def test_load_alternate_design_ids(tmp_path):
    (tmp_path / "designid.xml").write_text(
        '<DesignIdMapping>'
        '<Part designID="60601" alternateDesignIDs="86209, 35315" />'
        '<Part designID="4006" alternateDesignIDs="88631" />'
        '</DesignIdMapping>', encoding="utf-8")
    alts = load_alternate_design_ids(str(tmp_path))
    assert alts["86209"] == "60601"
    assert alts["35315"] == "60601"
    assert alts["88631"] == "4006"


def test_alternate_id_resolves_to_main_bl(tmp_path):
    content = make_partdef([
        "264\t264\t60601\t264\t60601.dat\t60601\tGlass for Window 1 x 2 x 2 Flat Front\to\t13\t1\t1\tFalse\t\tFalse\t5001\t",
    ])
    (tmp_path / "StudioPartDefinition2.txt").write_text(content, encoding="utf-8")
    (tmp_path / "designid.xml").write_text(
        '<DesignIdMapping><Part designID="60601" alternateDesignIDs="86209" />'
        '</DesignIdMapping>', encoding="utf-8")
    ldd_to_bl, _, _ = load_studio_mapping(str(tmp_path))
    assert ldd_to_bl["60601"] == "60601"
    assert ldd_to_bl["86209"] == "60601"   # old number -> main's BL


def test_build_official_dat_index():
    import os
    root = os.path.join(os.path.dirname(__file__), "fixtures", "ldraw")
    os.makedirs(os.path.join(root, "parts"), exist_ok=True)
    os.makedirs(os.path.join(root, "UnOfficial", "parts"), exist_ok=True)
    open(os.path.join(root, "parts", "22463.dat"), "w").write("")
    open(os.path.join(root, "UnOfficial", "parts", "76257.dat"), "w").write("")
    idx = build_official_dat_index(root)
    assert "22463" in idx
    assert "76257" not in idx


def test_disambiguate_prefers_official():
    # 76257 有两个候选，仅 22463 在官方索引
    filenames = {"76257": "22463.dat", "3001": "3001.dat", "10067": "11010.dat"}
    official = {"22463", "3001", "11010"}
    out = disambiguate_candidates(filenames, official)
    assert out["76257"] == "22463.dat"  # 消歧（返回 .dat 文件名，下游剥离后缀）
    assert out["10067"] == "11010.dat"
    assert out["3001"] == "3001.dat"    # 单一候选不变


def test_disambiguate_multiple_candidates_picks_official():
    # 每个 designID 对应多个候选文件名，仅一个在官方索引时消歧
    filenames = {"76257": ["22463.dat", "76257.dat"],
                 "10067": ["11010.dat", "10067.dat"],
                 "2001": ["x.dat", "y.dat"]}
    official = {"22463", "11010"}
    out = disambiguate_candidates(filenames, official)
    assert out["76257"] == "22463.dat"   # 官方候选胜出
    assert out["10067"] == "11010.dat"
    assert out["2001"] == "y.dat"        # 无唯一官方候选，保留原值(最后候选)


def test_load_studio_mapping_disambiguates_multi_candidate(tmp_path):
    data = [
        {"type": "transformation", "ldraw": {"filename": "22463.dat", "colors": []},
         "ldd": {"designId": 76257},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": 0.0, "z": 0.0}},
        {"type": "transformation", "ldraw": {"filename": "76257.dat", "colors": []},
         "ldd": {"designId": 76257},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": 0.0, "z": 0.0}},
    ]
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "ldraw_lxfml_mapping.json").write_text(json.dumps(data), encoding="utf-8")
    ldraw = tmp_path / "ldraw" / "parts"
    ldraw.mkdir(parents=True)
    (ldraw / "22463.dat").write_text("")
    uno = tmp_path / "ldraw" / "UnOfficial" / "parts"
    uno.mkdir(parents=True)
    (uno / "76257.dat").write_text("")
    ldd_to_bl, _, _ = load_studio_mapping(str(tmp_path / "data"))
    assert ldd_to_bl["76257"] == "22463"   # 官方 parts/ 优先


def test_load_studio_mapping_skips_disambiguation_without_ldraw(tmp_path):
    # 无官方索引(无 ldraw 目录)时跳过消歧，保留 JSON 最后候选(原行为)
    data = [
        {"type": "transformation", "ldraw": {"filename": "22463.dat", "colors": []},
         "ldd": {"designId": 76257},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": 0.0, "z": 0.0}},
        {"type": "transformation", "ldraw": {"filename": "76257.dat", "colors": []},
         "ldd": {"designId": 76257},
         "rotation": {"unit": "degree", "x": 0.0, "y": 0.0, "z": 0.0},
         "translation": {"unit": "LDU", "x": 0.0, "y": 0.0, "z": 0.0}},
    ]
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "ldraw_lxfml_mapping.json").write_text(json.dumps(data), encoding="utf-8")
    ldd_to_bl, _, _ = load_studio_mapping(str(tmp_path / "data"))
    assert ldd_to_bl["76257"] == "76257"   # 无 ldraw 目录，保留原行为
