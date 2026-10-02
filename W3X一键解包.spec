# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/dnd_ref/W3X解包工具/unpack_gui.py'],
    pathex=['D:/dnd_ref/W3X解包工具'],
    binaries=[],
    datas=[('D:/dnd_ref/W3X解包工具/mpyq.py', '.'), ('D:/dnd_ref/W3X解包工具/内置技能名.json', '.')],
    hiddenimports=['mpyq'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='W3X一键解包',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
