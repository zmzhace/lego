import os
import re

_BL_NUM = re.compile(r"^(\d{2,6})")


def find_studio_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or ""
    for c in [os.path.join(base, "Studio 2.0"),
              os.path.join(base, "Local", "Studio 2.0"),
              os.path.join(base, ".studio", "Studio 2.0")]:
        if os.path.isdir(c):
            return c
    return ""


def scan_studio_part_numbers(studio_dir: str) -> set:
    ids = set()
    if not studio_dir or not os.path.isdir(studio_dir):
        return ids
    for dirpath, _, files in os.walk(studio_dir):
        for f in files:
            stem = os.path.splitext(f)[0]
            m = _BL_NUM.match(stem)
            if m:
                ids.add(m.group(1))
    return ids
