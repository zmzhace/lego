from lddstudio.colors import ColorProcessor, load_bl_color_map

def make_bl_map():
    return {"5": ("5", 196, 0, 38, "Solid"),
            "1": ("1", 242, 243, 242, "Solid"),
            "999": ("999", 128, 128, 128, "Custom")}

def test_resolve_official_color():
    cp = ColorProcessor(make_bl_map(), {}, {})
    r = cp.resolve("5")
    assert not r.is_custom
    assert r.bl_color_id == "5"

def test_resolve_unknown_color_generates_custom():
    cp = ColorProcessor(make_bl_map(), {}, {})
    r = cp.resolve("77")   # 不在官方映射
    assert r.is_custom
    assert r.bl_color_id.isdigit()
    assert int(r.bl_color_id) >= 520000


def test_resolve_known_ldd_material_gets_real_rgb():
    from lddstudio.ldd_db import MaterialDef
    mats = {"77": MaterialDef("77", 10, 20, 30, 255, "Solid", "My Custom")}
    cp = ColorProcessor({}, {}, mats)
    r = cp.resolve("77")
    assert r.is_custom
    assert r.r == 10 and r.g == 20 and r.b == 30
    assert r.name == "My Custom"
    assert r.bl_color_id.isdigit()


def test_custom_codes_do_not_collide_with_existing():
    cp = ColorProcessor({}, {}, {}, existing_custom_codes={520000})
    r1 = cp.resolve("77")
    r2 = cp.resolve("78")
    assert r1.bl_color_id == "520001"
    assert r2.bl_color_id == "520002"

def test_build_custom_color_xml_contains_entries():
    cp = ColorProcessor(make_bl_map(), {}, {})
    xml = cp.build_studio_custom_color_xml({"C1": ("My Red", 200, 10, 10)})
    assert "My Red" in xml
    assert "200" in xml

def test_resolve_prefers_studio_color_map():
    studio_map = {"21": ("5", (200, 25, 8), "Red")}
    cp = ColorProcessor({}, {}, {}, studio_color_map=studio_map)
    r = cp.resolve("21")
    assert not r.is_custom
    assert r.bl_color_id == "5"
    assert r.name == "Red"
    assert r.r == 200

def test_resolve_studio_map_takes_priority_over_bl_map():
    studio_map = {"5": ("99", (1, 2, 3), "FromStudio")}
    cp = ColorProcessor(make_bl_map(), {}, {}, studio_color_map=studio_map)
    r = cp.resolve("5")
    assert r.bl_color_id == "99"

def test_build_custom_color_csv(tmp_path):
    cp = ColorProcessor({}, {}, {})
    out = str(tmp_path / "custom_colors.txt")
    cp.build_studio_custom_color_csv({"C1": ("My Red", 200, 10, 10)}, out)
    with open(out, encoding="utf-8") as f:
        content = f.read()
    assert "My Red" in content
    assert "#C80A0A" in content
    assert "Custom Colors" in content
