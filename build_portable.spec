# -*- mode: python ; coding: utf-8 -*-
# ============================================================
# build_portable.spec — папочная сборка (PySide6, без qtawesome)
# Директория: D:\Documents2\coding\yaml
# Запуск: pyinstaller build_portable.spec
# ============================================================

block_cipher = None

a = Analysis(
    ['clash_app.py'],
    pathex=[r'D:\Documents2\coding\yaml'],
    binaries=[],
    datas=[
        (r'D:\\Documents2\\coding\\yaml\\icon.png', '.'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'winreg',
        'requests',
        'yaml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'pystray',
        'PIL',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ClashConfigManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'D:\Documents2\coding\yaml\icon.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ClashConfigManager',
)
