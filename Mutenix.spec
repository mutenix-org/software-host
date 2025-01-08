# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/mutenix/package.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/mutenix/assets/*', 'mutenix/assets'), ('src/mutenix/static/*', 'mutenix/static'), ('src/mutenix/static/js/*', 'mutenix/static/js'), ('src/mutenix/templates/*', 'mutenix/templates')],
    hiddenimports=[ "hidapi" ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
onefile = True
if onefile:
    exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='Mutenix',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=False,
          icon="src/mutenix/assets/mutenix.ico",
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None, )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='Mutenix',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='Mutenix',
    )
