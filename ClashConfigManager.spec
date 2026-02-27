# -*- mode: python ; coding: utf-8 -*-
# ClashConfigManager.spec — PyInstaller onefile (PySide6, без qtawesome)
# Директория проекта: D:\Documents2\coding\yaml
# Запуск: pyinstaller ClashConfigManager.spec

a = Analysis(
    ['clash_app.py'],
    pathex=[r'D:\Documents2\coding\yaml'],
    binaries=[],
    datas=[
        (r'D:\Documents2\coding\yaml\icon.png', '.'),        (r'D:\\Documents2\\coding\\yaml\\icon.ico', '.'),    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtGui',
        'PySide6.QtCore',
        'PySide6.QtSvg',
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
    ],
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
    name='ClashConfigManager',
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
    icon=r'D:\Documents2\coding\yaml\icon.png',

)
