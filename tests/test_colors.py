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
    assert r.bl_color_id.startswith("C")

def test_build_custom_color_xml_contains_entries():
    cp = ColorProcessor(make_bl_map(), {}, {})
    xml = cp.build_studio_custom_color_xml({"C1": ("My Red", 200, 10, 10)})
    assert "My Red" in xml
    assert "200" in xml
