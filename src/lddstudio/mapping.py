import csv
import os
import re
import sqlite3
from difflib import SequenceMatcher
from typing import NamedTuple


class PartMapping(NamedTuple):
    design_id: str
    bl_number: str
    name: str
    match_type: str


def default_db_path() -> str:
    base = os.environ.get("USERPROFILE") or os.environ.get("HOME") or "."
    return os.path.join(base, ".lddstudio", "mapping.db")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


class MappingDb:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS parts (design_id TEXT PRIMARY KEY, "
            "bl_number TEXT, name TEXT, match_type TEXT)")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def rebuild(self, ldd_names: dict, bl_parts: dict, bl_numbers: set) -> None:
        manual_ids = {r[0] for r in self.conn.execute(
            "SELECT design_id FROM parts WHERE match_type='manual'")}
        for design_id, name in ldd_names.items():
            if design_id in manual_ids:
                continue
            if design_id in bl_numbers:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, design_id, name, "exact"))
                continue
            best, best_score = None, 0.0
            for bl_num, bl_name in bl_parts.items():
                score = SequenceMatcher(None, _norm(name), _norm(bl_name)).ratio()
                if score > best_score:
                    best, best_score = bl_num, score
            if best and best_score >= 0.85:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, best, name, "auto"))
            else:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, None, name, "unmatched"))
        self.conn.commit()

    def seed_from_studio(self, ldd_to_bl: dict, names: dict = None,
                         force=False) -> int:
        """Seed rows from Studio's authoritative LDD->BL mapping.

        Rows with match_type='manual' are preserved.  'exact' rows from a
        previous authoritative build are refreshed only when force=True
        (so user-verified exact mappings stay stable).
        """
        names = names or {}
        seeded = 0
        for design_id, bl_number in ldd_to_bl.items():
            cur = self.conn.execute(
                "SELECT match_type FROM parts WHERE design_id=?",
                (design_id,)).fetchone()
            if cur and cur[0] in ("manual",):
                continue
            if cur and cur[0] == "exact" and not force:
                continue
            name = names.get(design_id, "")
            self.conn.execute(
                "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                (design_id, bl_number, name, "exact"))
            seeded += 1
        self.conn.commit()
        return seeded

    def lookup(self, design_id: str):
        row = self.conn.execute(
            "SELECT design_id, bl_number, name, match_type FROM parts "
            "WHERE design_id=?", (design_id,)).fetchone()
        if row:
            return PartMapping(*row)
        return None

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT 1 FROM parts LIMIT 1").fetchone() is None

    def set_manual(self, design_id: str, bl_number: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO parts VALUES (?,?,"
            "COALESCE((SELECT name FROM parts WHERE design_id=?),''),?)",
            (design_id, bl_number, design_id, "manual"))
        self.conn.commit()

    def all_unmatched(self):
        rows = self.conn.execute(
            "SELECT design_id, bl_number, name, match_type FROM parts "
            "WHERE match_type='unmatched'").fetchall()
        return [PartMapping(*r) for r in rows]

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["design_id", "bl_number", "name", "match_type"])
            for r in self.conn.execute("SELECT * FROM parts"):
                w.writerow(r)

    def import_csv(self, path: str) -> None:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (row["design_id"], row["bl_number"] or None, row["name"], row["match_type"]))
        self.conn.commit()
