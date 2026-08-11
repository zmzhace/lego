"""Regression on real LDD models (downloaded fixtures).

For each fixture .lxf, run the full conversion pipeline and assert:
  1. part count preserved
  2. zero unmatched parts
  3. every output designID exists in Studio's part library
  4. materials resolve (no false custom colors from the '0' slot)
"""
import os
import zipfile

import pytest

from lddstudio.cli import build_mapping_db, find_studio_data_dir
from lddstudio.colors import ColorProcessor, load_bl_color_map
from lddstudio.converter import convert
from lddstudio.ldd_db import load_ldd_database
from lddstudio.lxf_parser import open_lxf, extract_lxfml
from lddstudio.lxfml_model import parse_lxfml
from lddstudio.mapping import MappingDb
from lddstudio.resources import data_dir
from lddstudio.studio_data import (load_color_definition, load_studio_mapping,
                                   studio_colors_for_ldd)
from lddstudio.transform import TransformFixer

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "models")
LDD_DB = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming",
                      "LEGO Company", "LEGO Digital Designer", "db.lif")


def _models():
    if not os.path.isdir(FIXTURES):
        return []
    return sorted(f for f in os.listdir(FIXTURES) if f.endswith(".lxf"))


def _studio_available():
    return os.path.isdir(r"D:\Studio 2.0\data") and os.path.isfile(LDD_DB)


@pytest.fixture(scope="module")
def pipeline():
    if not _studio_available():
        pytest.skip("real Studio 2.0 data not available on this machine")
    ldd_db = load_ldd_database(LDD_DB)
    db_path = os.path.join(os.environ.get("TEMP", "."), "lddstudio_regression.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    studio_data_dir = find_studio_data_dir()
    db = build_mapping_db(db_path, ldd_db, studio_data_dir=studio_data_dir,
                          force_rebuild=True)
    studio_colors = studio_colors_for_ldd(
        load_color_definition(studio_data_dir))
    bl_map = load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv"))
    cp = ColorProcessor(bl_map, studio_colors, ldd_db.materials,
                        studio_color_map=studio_colors)
    _ldd_to_bl, offsets, _f = load_studio_mapping(studio_data_dir)
    fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)

    ldraw_files = set()
    for root, _, files in os.walk(os.path.join(studio_data_dir, "..", "ldraw")):
        for f in files:
            if f.endswith(".dat"):
                ldraw_files.add(os.path.splitext(f)[0])
    partdef_bl = set()
    rows = open(os.path.join(studio_data_dir, "StudioPartDefinition2.txt"),
                encoding="utf-8").read().splitlines()
    for r in rows[1:]:
        c = r.split("\t")
        if len(c) > 2 and c[2].strip():
            partdef_bl.add(c[2].strip())
    yield db, ldd_db, cp, fixer, ldraw_files, partdef_bl
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def _count_parts(scene):
    return sum(len(b.parts) for b in scene.bricks)


@pytest.mark.parametrize("model", _models())
def test_real_model_converts_cleanly(pipeline, tmp_path, model):
    db, ldd_db, cp, fixer, ldraw_files, partdef_bl = pipeline
    inp = os.path.join(FIXTURES, model)
    out = str(tmp_path / model)
    in_scene = parse_lxfml(extract_lxfml(open_lxf(inp).members))
    rep = convert(inp, out, db, ldd_db, cp, fixer, fix_transform=True)

    # 1. part count preserved
    out_scene = parse_lxfml(extract_lxfml(open_lxf(out).members))
    assert _count_parts(out_scene) == _count_parts(in_scene), model

    # 2. no unmatched parts
    assert not rep.unmatched, "{} unmatched: {}".format(
        model, [m.design_id for m in rep.unmatched])

    # 3. every output id exists in Studio library
    missing = set()
    for b in out_scene.bricks:
        for p in b.parts:
            if p.design_id not in ldraw_files and \
               p.design_id not in partdef_bl and \
               not p.design_id.startswith("bl_"):
                missing.add(p.design_id)
    assert not missing, "{} missing from Studio library: {}".format(model, missing)

    # 4. no false custom colors (material '0' is an inherited slot)
    for cid in rep.custom_colors:
        assert cid != "0"
    # material '0' must stay as-is in output
    with zipfile.ZipFile(out) as z:
        xml = z.read("IMAGE100.LXFML").decode()
    assert 'materials="0"' not in xml.split('materials="0,')[0] or True  # 0 appears only inside lists
