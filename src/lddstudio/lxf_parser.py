import zipfile
import os

LXFML_ENTRY = "IMAGE100.LXFML"

class LxfPackage:
    def __init__(self, members: dict):
        self.members = members

    def get(self, name: str) -> bytes:
        return self.members[name]


def open_lxf(path: str) -> LxfPackage:
    with zipfile.ZipFile(path, "r") as z:
        return LxfPackage({n: z.read(n) for n in z.namelist()})


def extract_lxfml(members: dict) -> bytes:
    return members[LXFML_ENTRY]


def save_lxf(pkg: LxfPackage, out_path: str, files: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in pkg.members.items():
            if name in files:
                continue
            z.writestr(name, data)
        for name, data in files.items():
            z.writestr(name, data)
