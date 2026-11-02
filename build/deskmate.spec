# -*- mode: python ; coding: utf-8 -*-
"""
build/deskmate.spec - PyInstaller Specification for AI DeskMate.

Bundles the application into a single executable or standalone folder distribution
with windowed execution (no console), embedded icons, bundled data assets,
and collected dependencies including Streamlit, CustomTkinter, and scikit-learn.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None
PROJECT_ROOT = Path(os.path.abspath(SPEC)).parent.parent

# Collect Streamlit dependencies and assets
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all('streamlit')
ctk_datas, ctk_binaries, ctk_hiddenimports = collect_all('customtkinter')

datas = [
    (str(PROJECT_ROOT / 'nudge_messages.json'), '.'),
    (str(PROJECT_ROOT / 'insight_messages.json'), '.'),
    (str(PROJECT_ROOT / 'VERSION'), '.'),
    (str(PROJECT_ROOT / 'app'), 'app'),
]

assets_path = PROJECT_ROOT / 'assets'
if assets_path.exists():
    datas.append((str(assets_path), 'assets'))

datas += streamlit_datas
datas += ctk_datas

hiddenimports = [
    'pynput',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'pystray',
    'pystray._win32',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'pyttsx3.drivers.dummy',
    'winreg',
    'sklearn',
    'sklearn.utils',
    'sklearn.utils._typedefs',
    'sklearn.tree',
    'sklearn.tree._tree',
    'sklearn.linear_model',
    'sklearn.preprocessing',
    'sklearn.pipeline',
    'joblib',
    'pandas',
    'numpy',
    'plotly',
    'plotly.graph_objects',
    'plotly.express',
    'app',
    'app.dashboard',
    'app.dashboard.dashboard',
    'app.dashboard.launcher',
    'app.dashboard.analytics',
    'app.dashboard.insights',
    'app.demo.demo_seeder',
    'app.system.autostart',
] + streamlit_hiddenimports + ctk_hiddenimports

binaries = streamlit_binaries + ctk_binaries

a = Analysis(
    [str(PROJECT_ROOT / 'app' / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter.test', 'pytest'],
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
    name='AIDeskMate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / 'assets' / 'tray_icon.png') if (PROJECT_ROOT / 'assets' / 'tray_icon.png').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIDeskMate',
)
