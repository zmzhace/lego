"""Stress test with randomized models built from real LDD part data.

Generates many pseudo-random .lxf models (varied sizes, transforms,
multi-materials with the '0' slot, offset parts, injected unknown ids,
fake custom colors) and asserts the conversion pipeline never crashes,
always preserves part counts, reports only expected unmatched parts, and
emits only Studio-recognized part numbers.
"""
import math
import os
import random
import sys
import zipfile

import pytest

from lddstudio.cli import build_mapping_db
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

DATA = r"D:\Studio 2.0\data"
LDD_DB = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming",
                      "LEGO Company", "LEGO Digital Designer", "db.lif")
KNOWN_ORPHANS = ("71956", "73914")   # LDD-only, no Studio equivalent


def _available():
    return os.path.isfile(DATA + r"\StudioPartDefinition2.txt") and os.path.isfile(LDD_DB)


def _rand_transform(rng):
    rx, ry, rz = [rng.uniform(-math.pi, math.pi) for _ in range(3)]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    a00, a01, a02 = cz*cy, cz*sy*sx - sz*cx, cz*sy*cx + sz*sx
    a10, a11, a12 = sz*cy, sz*sy*sx + cz*cx, sz*sy*cx - cz*sx
    a20, a21, a22 = -sy, cy*sx, cy*cx
    t = [rng.uniform(-60, 60) for _ in range(3)]
    return "{},{},{},{},{},{},{},{},{},{},{},{}".format(
        a00, a01, a02, a10, a11, a12, a20, a21, a22, *t)


@pytest.fixture(scope="module")
def stress_pipeline():
    if not _available():
        pytest.skip("real Studio/LDD data not available")
    ldd_db = load_ldd_database(LDD_DB)
    ldd_to_bl, offsets, _f = load_studio_mapping(DATA)
    db_path = os.path.join(os.environ.get("TEMP", "."), "lddstudio_stress.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    db = build_mapping_db(db_path, ldd_db, studio_data_dir=DATA, force_rebuild=True)
    studio_colors = studio_colors_for_ldd(load_color_definition(DATA))
    bl_map = load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv"))
    cp = ColorProcessor(bl_map, studio_colors, ldd_db.materials,
                        studio_color_map=studio_colors)
    fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)
    # Studio-recognized numbers = any id referenced in Studio's own mapping data
    recognized = set()
    rows = open(os.path.join(DATA, "StudioPartDefinition2.txt"),
                encoding="utf-8").read().splitlines()
    for r in rows[1:]:
        for c in r.split("\t")[:5]:
            if c.strip():
                recognized.add(c.strip())
    for fn in ("ldraw_new.xml", "ldraw_lxfv56.xml"):
        xml = open(os.path.join(DATA, fn), encoding="utf-8", errors="replace").read()
        import re
        for m in re.finditer(r'(?:ldraw|filename)="([^"]+\.dat)"', xml):
            recognized.add(os.path.splitext(m.group(1))[0])
    yield ldd_db, db, cp, fixer, recognized
    db.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def _build_model(rng, all_ids, offset_ids, official_colors, idx):
    mode = idx % 4
    if mode == 0:
        n = rng.randint(1, 20)
    elif mode == 1:
        n = rng.randint(20, 150)
    elif mode == 2:
        n = rng.randint(150, 600)
    else:
        n = rng.randint(1, 150)

    bricks = []
    rid = 1
    for _ in range(n):
        roll = rng.random()
        if mode == 3 and roll < 0.2:
            did = str(rng.randint(999900, 999999))
        elif roll < 0.3 and offset_ids:
            did = rng.choice(offset_ids)
        else:
            did = rng.choice(all_ids)
        if mode == 2 and roll < 0.4:
            mat = str(rng.randint(2000, 2999))
        elif mode in (1, 2) and rng.random() < 0.4:
            mat = "{},{}".format(rng.choice(official_colors),
                                 ",".join(rng.choice(official_colors)
                                          for _ in range(rng.randint(1, 3))))
        else:
            mat = rng.choice(official_colors)
        t = _rand_transform(rng)
        bricks.append(
            '<Brick refID="{}" designID="{}"><Part refID="{}" designID="{}" '
            'materials="{}"><Bone refID="{}" transformation="{}"/></Part></Brick>'
            .format(rid, did, rid + 1, did, mat, rid + 1, t))
        rid += 2
    lxfml = ('<LXFML name="stress{}"><Meta><BrickSet version="2"/></Meta><Bricks>'
             .format(idx) + "".join(bricks) + "</Bricks></LXFML>").encode()
    return lxfml


def _run_batch(rng, all_ids, offset_ids, official_colors, ldd_db, db, cp,
               fixer, recognized, tmp_path, count):
    results = {"ok": 0, "crashes": [], "count_mismatch": 0,
               "unexpected_unmatched": 0, "missing": 0, "parts": 0}
    for idx in range(count):
        lxfml = _build_model(rng, all_ids, offset_ids, official_colors, idx)
        inp = str(tmp_path / ("m{:03d}.lxf".format(idx)))
        out = str(tmp_path / ("m{:03d}_o.lxf".format(idx)))
        with zipfile.ZipFile(inp, "w") as z:
            z.writestr("IMAGE100.LXFML", lxfml)
        in_scene = parse_lxfml(extract_lxfml(open_lxf(inp).members))
        try:
            rep = convert(inp, out, db, ldd_db, cp, fixer, fix_transform=True)
        except Exception as e:                      # pragma: no cover
            results["crashes"].append(str(e))
            continue
        out_scene = parse_lxfml(extract_lxfml(open_lxf(out).members))
        n_in = sum(len(b.parts) for b in in_scene.bricks)
        n_out = sum(len(b.parts) for b in out_scene.bricks)
        results["parts"] += n_in
        if n_in != n_out:
            results["count_mismatch"] += 1
            continue
        for m in rep.unmatched:
            if m.design_id not in KNOWN_ORPHANS and not m.design_id.startswith("9999"):
                results["unexpected_unmatched"] += 1
        for b in out_scene.bricks:
            for p in b.parts:
                if p.design_id not in recognized and \
                   not p.design_id.startswith("bl_") and \
                   not p.design_id.startswith("9999") and \
                   p.design_id not in KNOWN_ORPHANS:
                    results["missing"] += 1
        results["ok"] += 1
    return results


def test_stress_120_random_models(stress_pipeline, tmp_path):
    rng = random.Random(20260811)
    ldd_db, db, cp, fixer, recognized = stress_pipeline
    all_ids = list(ldd_db.primitive_names)
    offset_ids = [i for i in all_ids if i in getattr(fixer, "offsets", {})]
    official_colors = sorted(set(ldd_db.materials)) if ldd_db.materials else ["21"]
    res = _run_batch(rng, all_ids, offset_ids, official_colors, ldd_db, db, cp,
                     fixer, recognized, tmp_path, 120)
    assert res["crashes"] == []
    assert res["count_mismatch"] == 0
    assert res["unexpected_unmatched"] == 0
    assert res["missing"] == 0
    assert res["ok"] == 120
