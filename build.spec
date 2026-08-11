# build.spec
# -*- mode: python -*-
datas = [("data/ldd_to_bl_colors.csv", "data")]
a = Analysis(["src/lddstudio/main_gui.py"],
             pathex=["src"],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
           name="lddstudio", console=False, upx=True)
