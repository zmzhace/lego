import csv
import os
from typing import NamedTuple

from .studio_data import rgb_tuple


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
    def __init__(self, bl_map, studio_colors, ldd_materials, studio_color_map=None):
        """studio_color_map: dict ldd_color_code -> (studio_code, rgb, name)."""
        self.bl_map = bl_map
        self.studio_colors = studio_colors
        self.ldd_materials = ldd_materials
        self.studio_color_map = studio_color_map or {}
        self._custom_cache = {}

    def resolve(self, mat_id: str) -> ColorResult:
        # 1. Studio's own LDD color -> Studio/BL color mapping (authoritative)
        if mat_id in self.studio_color_map:
            studio_code, (r, g, b), name = self.studio_color_map[mat_id]
            return ColorResult(studio_code, name, r, g, b, False)
        # 2. bundled ldd->bl csv fallback
        if mat_id in self.bl_map:
            bl_id, r, g, b, _ = self.bl_map[mat_id]
            return ColorResult(bl_id, "", r, g, b, False)
        # 3. LDD custom material (from db / palette)
        if mat_id in self.ldd_materials:
            m = self.ldd_materials[mat_id]
            name = m.name or ("Custom " + mat_id)
            return ColorResult("C" + mat_id, name, m.r, m.g, m.b, True)
        return ColorResult("C" + mat_id, "Custom " + mat_id, 128, 128, 128, True)

    def build_studio_custom_color_xml(self, custom_colors: dict) -> str:
        lines = ['<CustomColors>']
        for cid, (name, r, g, b) in custom_colors.items():
            lines.append('  <Color id="{}" name="{}" r="{}" g="{}" b="{}"/>'.format(
                cid, name, r, g, b))
        lines.append("</CustomColors>")
        return "\n".join(lines)

    def build_studio_custom_color_csv(self, custom_colors: dict, path: str) -> None:
        """Write Studio's CustomColorDefinition.txt-format CSV for import."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow([
                "Studio Color Code", "BL Color Code", "LDraw Color Code",
                "LDD color code", "Studio Color Name", "BL Color Name",
                "LDraw Color Name", "LDD Color Name", "RGB value", "Alpha",
                "CategoryName", "Color Group Index", "note", "Ins_RGB", "Ins_CMYK"])
            for cid, (name, r, g, b) in custom_colors.items():
                hex_rgb = "#{:02X}{:02X}{:02X}".format(r, g, b)
                w.writerow([
                    cid, cid, "", "", name, name, name, name,
                    hex_rgb, "1", "Custom Colors", "-1", "o", "", ""])
