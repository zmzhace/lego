import os
import re

_BL_NUM = re.compile(r"^(\d{2,6})")


def find_studio_dir() -> str:
    """Probe common Studio 2.0 install locations.

    Also accepts an explicit override via env var LDDSTUDIO_STUDIO_DIR.
    """
    override = os.environ.get("LDDSTUDIO_STUDIO_DIR")
    if override and os.path.isdir(override):
        return override
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or ""
    base2 = os.environ.get("ProgramFiles") or "C:\\Program Files"
    base3 = os.environ.get("ProgramFiles(x86)") or "C:\\Program Files (x86)"
    base4 = os.environ.get("USERPROFILE") or ""
    candidates = [
        os.path.join(base, "Studio 2.0"),
        os.path.join(base, "Local", "Studio 2.0"),
        os.path.join(base, ".studio", "Studio 2.0"),
        os.path.join(base2, "Studio 2.0"),
        os.path.join(base3, "Studio 2.0"),
        os.path.join(base2, "BrickLink Studio", "Studio 2.0"),
        os.path.join(base3, "BrickLink Studio", "Studio 2.0"),
    ]
    # common extra drive roots (D:, E:)
    for drive in ("D:", "E:"):
        candidates.append(os.path.join(drive + os.sep, "Studio 2.0"))
        candidates.append(os.path.join(drive + os.sep, "BrickLink Studio", "Studio 2.0"))
    if base4:
        candidates.append(os.path.join(base4, "Studio 2.0"))
    for c in candidates:
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
