# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import get_module_file_attribute
import os


numpy_basedir = os.path.dirname(get_module_file_attribute('numpy'))

block_cipher = None

entry_point = os.path.join('src', 'main.py')
analysis_paths = [os.path.join(os.getcwd(), 'src')]

a = Analysis(
    [entry_point], 
    pathex=analysis_paths, 
    binaries=[],
    
    datas=[
        (numpy_basedir, 'numpy'), 
        ('assets', 'assets') 
    ],
    
    
    hiddenimports=[
        
        'playhouse.sqlite_ext', 
        
        # Necessari per SecurityManager (gestione password sicura)
        'keyring.backends',
        'keyring.backends.Windows', 
        'win32ctypes.core',         
    ],
    
    
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AO3 Helper',
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
    icon=os.path.join('assets', 'app_icon.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AO3 Helper',
)
