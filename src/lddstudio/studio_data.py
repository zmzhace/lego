"""Reader for Studio 2.0 authoritative data files.

Studio 2.0 ships several data files under ``<StudioDir>/data`` that define the
exact mapping between LDD part/color identifiers and Studio (BrickLink) ones:

- ``StudioPartDefinition2.txt``: rows with an LDD ItemNo column giving the
  LDD designID -> BL/LDraw/Studio part-number correspondence (~2400 rows).
- ``ldraw_lxfml_mapping.json``: per-designID rotation (degrees) and translation
  (LDU) offsets used to position parts when LDD geometry differs from the
  LDraw/Studio geometry (the "flying parts" fix).
- ``StudioColorDefinition.txt``: LDD material code -> Studio/BL/LDraw color
  code mapping with RGB values.

These files are parsed at runtime; all functions tolerate a missing/broken
Studio installation and return empty structures.
"""

import json
import math
import os
import re

PART_DEF_FILE = "StudioPartDefinition2.txt"
COLOR_DEF_FILE = "StudioColorDefinition.txt"
TRANSFORM_JSON_FILE = "ldraw_lxfml_mapping.json"
ASSEMBLY_FILE = "ldraw_new.xml"
DESIGNID_FILE = "designid.xml"


class StudioPartDef:
    """One row of StudioPartDefinition2.txt."""

    def __init__(self, studio_no, bl_no, ldraw_no, ldd_no, description):
        self.studio_no = studio_no
        self.bl_no = bl_no
        self.ldraw_no = ldraw_no
        self.ldd_no = ldd_no
        self.description = description

    def __repr__(self):
        return "StudioPartDef(ldd={}, bl={}, ldraw={}, desc={!r})".format(
            self.ldd_no, self.bl_no, self.ldraw_no, self.description)


def _parse_part_def_row(cells):
    if len(cells) < 6:
        return None
    ldd_no = cells[5].strip()
    if not ldd_no:
        return None
    return StudioPartDef(
        studio_no=cells[0].strip(),
        bl_no=cells[2].strip(),
        ldraw_no=cells[4].strip(),
        ldd_no=ldd_no,
        description=cells[6].strip() if len(cells) > 6 else "",
    )


def load_part_definition(data_dir):
    """Parse StudioPartDefinition2.txt into a list of StudioPartDef."""
    path = os.path.join(data_dir, PART_DEF_FILE)
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            cells = line.split("\t")
            if cells and cells[0].strip().lower() == "studio itemno":
                continue
            pd = _parse_part_def_row(cells)
            if pd is not None:
                rows.append(pd)
    return rows


def load_studio_mapping(data_dir):
    """Load the full authoritative LDD->BL mapping from Studio data.

    Combines StudioPartDefinition2.txt (explicit BL numbers) with the ldraw
    filenames embedded in ldraw_lxfml_mapping.json (wider coverage),
    Assembly entries from ldraw_new.xml, and <Transformation> tags which
    carry additional per-part mappings (gap filler).

    Returns (ldd_to_bl, offsets, filenames):
      - ldd_to_bl: dict design_id -> BL number
      - offsets:   dict design_id -> TransformOffset
      - filenames: dict design_id -> list of candidate ldraw filenames
    """
    rows = load_part_definition(data_dir)
    ldd_to_bl = build_ldd_to_bl_map(rows)
    offsets, filenames = load_transform_data(data_dir)
    from_transform = build_ldd_to_bl_from_filenames(filenames.items())
    # 多候选优先官方件（76257 -> 22463.dat）
    official_index = build_official_dat_index(
        os.path.join(os.path.dirname(data_dir), "ldraw"))
    if official_index:
        disambiguated = disambiguate_candidates(filenames, official_index)
        from_transform = build_ldd_to_bl_from_filenames(disambiguated.items())
    for did, bl in from_transform.items():
        ldd_to_bl.setdefault(did, bl)
    for did, bl in load_assembly_mapping(data_dir).items():
        ldd_to_bl.setdefault(did, bl)
    for did, bl in load_transformation_mapping(data_dir).items():
        ldd_to_bl.setdefault(did, bl)
    ldd_to_bl.update(_resolve_alternate_ids(ldd_to_bl, load_alternate_design_ids(data_dir)))
    return ldd_to_bl, offsets, filenames


def load_alternate_design_ids(data_dir):
    """Parse designid.xml: {alternate_design_id: main_design_id}.

    LDD reused old part numbers (e.g. 86209) that Studio records as
    alternatives of the current number (60601).  These are normalized to the
    main designID before mapping to a BL number.
    """
    path = os.path.join(data_dir, DESIGNID_FILE)
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
    except OSError:
        return {}
    for m in re.finditer(r'<Part designID="(\d+)" alternateDesignIDs="([^"]+)"\s*/>', data):
        main_id = m.group(1)
        for alt in m.group(2).split(","):
            alt = alt.strip()
            if alt and alt.isdigit():
                out[alt] = main_id
    return out


def _resolve_alternate_ids(ldd_to_bl, alternates):
    """Extend ldd_to_bl so alternate IDs resolve to the main ID's BL number."""
    for alt_id, main_id in alternates.items():
        if alt_id in ldd_to_bl:
            continue
        bl = ldd_to_bl.get(main_id)
        if bl:
            ldd_to_bl[alt_id] = bl
    return ldd_to_bl


def load_transformation_mapping(data_dir):
    """Parse <Transformation ldraw="X.dat" lego="Y"/> -> {Y: X}.

    These cover per-part conversion mappings that may not appear in the JSON
    or Assembly lists (e.g. glass parts, clips).  Returns the ldraw filename;
    callers strip '.dat' for the BL number.
    """
    out = {}
    for fname in (ASSEMBLY_FILE, "ldraw_lxfv56.xml"):
        path = os.path.join(data_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
        except OSError:
            continue
        for m in re.finditer(r'<Transformation ldraw="([^"]*)" lego="(\d+)"', data):
            out.setdefault(m.group(2), _ldraw_no_to_bl(m.group(1)))
    return out


def load_assembly_mapping(data_dir):
    """Parse <Assembly ldraw="X.dat" lego="Y"/> entries -> {Y: X}.

    These fill gaps for parts Studio stores as assemblies (e.g. wheels with
    tyres, minifigure subassemblies).
    """
    path = os.path.join(data_dir, ASSEMBLY_FILE)
    if not os.path.isfile(path):
        return {}
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return {}
    for m in re.finditer(r'<Assembly ldraw="([^"]*)" lego="(\d+)"', data):
        out.setdefault(m.group(2), _ldraw_no_to_bl(m.group(1)))
    return out


def build_official_dat_index(ldraw_dir):
    """Return set of .dat basenames in official parts dirs (parts/, p/).

    UnOfficial/ and collider/connectivity are excluded.  Returns empty set
    when ldraw_dir is missing.
    """
    out = set()
    if not ldraw_dir or not os.path.isdir(ldraw_dir):
        return out
    for root, _dirs, files in os.walk(ldraw_dir):
        rel = os.path.relpath(root, ldraw_dir).replace("\\", "/")
        parts = rel.split("/")
        if "UnOfficial" in parts or "unofficial" in parts:
            continue
        if not (parts[-1] == "parts" or parts[-1] == "p"):
            continue
        for f in files:
            if f.endswith(".dat"):
                out.add(f[:-4])
    return out


def disambiguate_candidates(filenames, official_index):
    """Pick the official .dat when a designID has multiple candidates.

    filenames: {design_id: ldraw_filename or list of candidates}.  Returns a
    new dict design_id -> resolved .dat filename: multi-candidate designIDs
    with exactly one official candidate resolve to that official file; all
    others keep their original value.
    """
    out = {}
    for did, val in filenames.items():
        cands = list(val) if isinstance(val, (list, tuple, set)) else [val]
        official = [c for c in cands
                    if c.endswith(".dat") and c[:-4] in official_index]
        if len(cands) > 1 and len(official) == 1:
            out[did] = official[0]
        else:
            out[did] = cands[-1]
    return out


def build_ldd_to_bl_map(rows):
    """Return dict: ldd_design_id -> render number.

    Studio renders parts by their LDraw .dat filename (col 4).  BL numbers
    (col 2) often carry letter suffixes (30237a) whose .dat does not exist in
    the Studio ldraw/ tree, so preferring the .dat filename avoids parts
    showing as question marks.  Fallback order: ldraw file -> BL -> studio.
    """
    out = {}
    for pd in rows:
        if not pd.ldd_no:
            continue
        target = _ldraw_no_to_bl(pd.ldraw_no) if pd.ldraw_no else ""
        if not target:
            target = pd.bl_no
        if not target:
            target = pd.studio_no
        if target:
            out.setdefault(pd.ldd_no, target)
    return out


def build_bl_number_set(rows):
    """Return the set of BL part numbers Studio knows (incl. rows with no LDD id).

    Used for identity fallback: an LDD designID that equals a Studio BL number
    maps to itself even when the LDD column of the row is empty.
    """
    out = set()
    for pd in rows:
        if pd.bl_no:
            out.add(pd.bl_no)
        elif pd.ldraw_no:
            out.add(_ldraw_no_to_bl(pd.ldraw_no))
    return out


def _ldraw_no_to_bl(ldraw_no):
    """'3001.dat' -> '3001'; keeps 'bl_973pb1234c01' style slugs."""
    return ldraw_no.split(".dat")[0] if ldraw_no else ""


class TransformOffset:
    """Rotation (degrees) + translation (LDU) for one designID."""

    def __init__(self, rx, ry, rz, tx, ty, tz):
        self.rx = float(rx)
        self.ry = float(ry)
        self.rz = float(rz)
        self.tx = float(tx)
        self.ty = float(ty)
        self.tz = float(tz)

    def __repr__(self):
        return "TransformOffset(r={},{},{} t={},{},{})".format(
            self.rx, self.ry, self.rz, self.tx, self.ty, self.tz)


def load_transform_offsets(data_dir):
    """Parse ldraw_lxfml_mapping.json into dict: design_id -> TransformOffset.

    Only entries with type == 'transformation' are used.  A transformation
    means: when converting the LDD part to Studio/LDraw geometry, rotate by
    (rx, ry, rz) degrees and translate by (tx, ty, tz) LDU.
    """
    offsets, _filenames = load_transform_data(data_dir)
    return offsets


def load_transform_data(data_dir):
    """Parse ldraw_lxfml_mapping.json in one pass.

    Returns (offsets, filenames): offsets maps design_id -> TransformOffset
    and filenames maps design_id -> list of distinct candidate ldraw
    filenames for 'transformation' entries (a designID can appear in
    multiple entries with different .dat files, e.g. 76257 -> 22463.dat and
    76257.dat).
    """
    path = os.path.join(data_dir, TRANSFORM_JSON_FILE)
    if not os.path.isfile(path):
        return {}, {}
    offsets = {}
    filenames = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return offsets, filenames
    if not isinstance(data, list):
        return offsets, filenames
    for entry in data:
        if not isinstance(entry, dict) or entry.get("type") != "transformation":
            continue
        ldd = entry.get("ldd") or {}
        rot = entry.get("rotation") or {}
        tr = entry.get("translation") or {}
        did = ldd.get("designId")
        if did is None:
            continue
        did = str(did)
        offsets[did] = TransformOffset(
            rot.get("x", 0.0), rot.get("y", 0.0), rot.get("z", 0.0),
            tr.get("x", 0.0), tr.get("y", 0.0), tr.get("z", 0.0))
        fname = (entry.get("ldraw") or {}).get("filename", "")
        if fname:
            cands = filenames.setdefault(did, [])
            if fname not in cands:
                cands.append(fname)
    return offsets, filenames


def build_ldd_to_bl_from_filenames(offset_pairs):
    """Given iterable of (design_id, ldraw_filename) -> dict design_id->bl.

    ldraw_filename like '41823.dat' or 'bl_973pb2017c01.dat'.  Numeric
    filenames map directly to BL numbers; slugs are kept as-is.  A
    design_id may map to a list of candidate filenames (multi-candidate
    entries in the mapping JSON); the last candidate is used, matching the
    old "last entry wins" collapse.
    """
    out = {}
    for did, fname in offset_pairs:
        if isinstance(fname, (list, tuple)):
            fname = fname[-1] if fname else ""
        if not fname:
            continue
        base = fname.split(".dat")[0]
        if base:
            out.setdefault(str(did), base)
    return out


class StudioColor:
    """One row of StudioColorDefinition.txt."""

    def __init__(self, studio_code, bl_code, ldraw_code, ldd_code,
                 studio_name, bl_name, ldd_name, rgb, alpha, note):
        self.studio_code = studio_code
        self.bl_code = bl_code
        self.ldraw_code = ldraw_code
        self.ldd_code = ldd_code
        self.studio_name = studio_name
        self.bl_name = bl_name
        self.ldd_name = ldd_name
        self.rgb = rgb
        self.alpha = alpha
        self.note = note

    def __repr__(self):
        return "StudioColor(ldd={}, studio={}, bl={}, name={}, rgb={})".format(
            self.ldd_code, self.studio_code, self.bl_code, self.studio_name, self.rgb)


def load_color_definition(data_dir):
    """Parse StudioColorDefinition.txt into a list of StudioColor."""
    path = os.path.join(data_dir, COLOR_DEF_FILE)
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            cells = line.split("\t")
            if cells and cells[0].strip().lower() == "studio color code":
                continue
            if len(cells) < 9:
                continue
            rows.append(StudioColor(
                studio_code=cells[0].strip(),
                bl_code=cells[1].strip(),
                ldraw_code=cells[2].strip(),
                ldd_code=cells[3].strip(),
                studio_name=cells[4].strip(),
                bl_name=cells[5].strip(),
                ldd_name=cells[7].strip() if len(cells) > 7 else "",
                rgb=cells[8].strip(),
                alpha=cells[9].strip() if len(cells) > 9 else "1",
                note=cells[12].strip() if len(cells) > 12 else "",
            ))
    return rows


def build_ldd_color_map(colors):
    """Return dict: ldd_color_code -> StudioColor (prefer 'o' official rows)."""
    out = {}
    for c in colors:
        if not c.ldd_code:
            continue
        cur = out.get(c.ldd_code)
        if cur is None:
            out[c.ldd_code] = c
            continue
        cur_note, new_note = cur.note, c.note
        if "o" in new_note and "o" not in cur_note:
            out[c.ldd_code] = c
    return out


def rgb_tuple(rgb_hex):
    """'#04121C' -> (4, 18, 28).  Returns (0,0,0) when unparsable."""
    m = re.match(r"#?([0-9a-fA-F]{6})", rgb_hex or "")
    if not m:
        return (0, 0, 0)
    h = m.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def studio_colors_for_ldd(colors):
    """Return dict: ldd_color_code -> (studio_color_code, rgb_tuple, name)."""
    out = {}
    for c in colors:
        if not c.ldd_code:
            continue
        out.setdefault(c.ldd_code, (c.studio_code, rgb_tuple(c.rgb), c.studio_name))
    return out
