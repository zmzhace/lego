import csv
import os
from typing import NamedTuple

from .studio_data import rgb_tuple

# Studio reserves 509xxx for its own special custom colors; we allocate
# fresh codes in a high range that won't collide.
CUSTOM_COLOR_BASE = 520000


class ColorResult(NamedTuple):
    bl_color_id: str
    name: str
    r: int
    g: int
    b: int
    is_custom: bool


def load_bl_color_map(path: str) -> dict:
    mapping = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("LDD_ID"):
                continue
            mapping[row["LDD_ID"]] = (
                row.get("BL_ID", row["LDD_ID"]),
                int(float(row["R"])), int(float(row["G"])), int(float(row["B"])),
                row.get("Material", ""),
            )
    return mapping


class ColorProcessor:
    def __init__(self, bl_map, studio_colors, ldd_materials, studio_color_map=None,
                 existing_custom_codes=None):
        """studio_color_map: dict ldd_color_code -> (studio_code, rgb, name).

        existing_custom_codes: set of Studio color codes already in use so the
        allocator never collides (e.g. codes present in CustomColorDefinition.txt).
        """
        self.bl_map = bl_map
        self.studio_colors = studio_colors
        self.ldd_materials = ldd_materials
        self.studio_color_map = studio_color_map or {}
        self._custom_cache = {}
        self._next_custom = CUSTOM_COLOR_BASE
        self.existing_custom_codes = set(existing_custom_codes or ())
        while self._next_custom in self.existing_custom_codes:
            self._next_custom += 1

    def _alloc_custom_code(self):
        while self._next_custom in self.existing_custom_codes:
            self._next_custom += 1
        code = self._next_custom
        self._next_custom += 1
        self.existing_custom_codes.add(code)
        return str(code)

    def resolve(self, mat_id: str) -> ColorResult:
        # LDD uses '0' as a no-op / inherited material slot in multi-material
        # parts (e.g. materials="26,0").  Keep it untouched, not a custom color.
        if mat_id == "0":
            return ColorResult("0", "", 0, 0, 0, False)
        # 1. Studio's own LDD color -> Studio/BL color mapping (authoritative)
        if mat_id in self.studio_color_map:
            studio_code, (r, g, b), name = self.studio_color_map[mat_id]
            return ColorResult(studio_code, name, r, g, b, False)
        # 2. bundled ldd->bl csv fallback
        if mat_id in self.bl_map:
            bl_id, r, g, b, _ = self.bl_map[mat_id]
            return ColorResult(bl_id, "", r, g, b, False)
        # 3. LDD material known in the LDD database -> migrate as a
        #    Studio custom color carrying the real RGB.
        if mat_id in self.ldd_materials:
            m = self.ldd_materials[mat_id]
            if mat_id in self._custom_cache:
                return self._custom_cache[mat_id]
            name = m.name or ("Custom " + mat_id)
            code = self._alloc_custom_code()
            res = ColorResult(code, name, m.r, m.g, m.b, True)
            self._custom_cache[mat_id] = res
            return res
        # 4. truly unknown -> grey placeholder, still reported as custom
        if mat_id in self._custom_cache:
            return self._custom_cache[mat_id]
        code = self._alloc_custom_code()
        res = ColorResult(code, "Custom " + mat_id, 128, 128, 128, True)
        self._custom_cache[mat_id] = res
        return res

    def build_studio_custom_color_xml(self, custom_colors: dict) -> str:
        lines = ['<CustomColors>']
        for cid, (name, r, g, b) in custom_colors.items():
            lines.append('  <Color id="{}" name="{}" r="{}" g="{}" b="{}"/>'.format(
                cid, name, r, g, b))
        lines.append("</CustomColors>")
        return "\n".join(lines)

    def build_studio_custom_color_csv(self, custom_colors: dict, path: str) -> None:
        """Write Studio's CustomColorDefinition.txt-format rows for import.

        17 columns matching the real file (incl. Categogy NickName).
        """
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow([
                "Studio Color Code", "BL Color Code", "LDraw Color Code",
                "LDD color code", "Studio Color Name", "BL Color Name",
                "LDraw Color Name", "LDD Color Name", "RGB value", "Alpha",
                "CategoryName", "Color Group Index", "note", "Ins_RGB",
                "Ins_CMYK", "Categogy NickName"])
            for cid, (name, r, g, b) in custom_colors.items():
                hex_rgb = "#{:02X}{:02X}{:02X}".format(r, g, b)
                w.writerow([
                    cid, "", "", "", name, name, name, name,
                    hex_rgb, "1", "Custom Colors", "-1", "o", "", "", ""])

    def append_to_custom_definition(self, custom_colors: dict, path: str) -> int:
        """Append rows to an existing Studio CustomColorDefinition.txt.

        Returns the number of rows appended.  Existing header is preserved.
        """
        lines = []
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                existing = f.read().rstrip("\n")
            if existing:
                lines.append(existing)
        else:
            lines.append("\t".join([
                "Studio Color Code", "BL Color Code", "LDraw Color Code",
                "LDD color code", "Studio Color Name", "BL Color Name",
                "LDraw Color Name", "LDD Color Name", "RGB value", "Alpha",
                "CategoryName", "Color Group Index", "note", "Ins_RGB",
                "Ins_CMYK", "Categogy NickName"]))
        added = 0
        for cid, (name, r, g, b) in custom_colors.items():
            hex_rgb = "#{:02X}{:02X}{:02X}".format(r, g, b)
            lines.append("\t".join([
                str(cid), "", "", "", name, name, name, name,
                hex_rgb, "1", "Custom Colors", "-1", "o", "", "", ""]))
            added += 1
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return added
