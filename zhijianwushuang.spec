# -*- mode: python ; coding: utf-8 -*-

import os
import sys

ENV_PREFIX = sys.prefix
if os.path.basename(os.path.dirname(sys.executable)).lower() == 'scripts':
    ENV_PREFIX = os.path.dirname(os.path.dirname(sys.executable))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('img', 'img')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'scipy',
        'pandas',
        'matplotlib',
        'PIL',
        'PyQt5',
        'PyQt6',
        'IPython',
        'mkl',
        'psutil',
        'yaml',
    ],
    noarchive=False,
    optimize=0,
)

def keep_runtime_file(entry):
    names = [str(part).replace('\\', '/').lower() for part in entry[:2]]
    dest_name = names[0]
    base_name = os.path.basename(dest_name)
    for name in names:
        name_base = os.path.basename(name)
        if name_base.startswith('mkl_') or name_base.startswith('mkl.'):
            return False
        if name_base.startswith(('tbb', 'omptarget', 'libiomp', 'libimalloc', 'vcomp')):
            return False
        if name_base in {'yaml.dll'}:
            return False
        if '/mkl/' in name or '/psutil/' in name or '/yaml/' in name:
            return False
    if base_name.startswith('opencv_videoio_ffmpeg'):
        return False
    if 'numpy/_core/_multiarray_tests.' in dest_name:
        return False
    if '/numpy-' in dest_name and '.dist-info/' in dest_name:
        return False
    return True

a.binaries = [entry for entry in a.binaries if keep_runtime_file(entry)]
a.datas = [entry for entry in a.datas if keep_runtime_file(entry)]

def force_env_tcl_tk(entries):
    if not ENV_PREFIX:
        return entries
    replacements = {
        'tcl86t.dll': os.path.join(ENV_PREFIX, 'Library', 'bin', 'tcl86t.dll'),
        'tk86t.dll': os.path.join(ENV_PREFIX, 'Library', 'bin', 'tk86t.dll'),
        'zlib1.dll': os.path.join(ENV_PREFIX, 'Library', 'bin', 'zlib1.dll'),
    }
    result = []
    replaced = set()
    for entry in entries:
        dest_name = os.path.basename(entry[0]).lower()
        if dest_name in replacements and os.path.exists(replacements[dest_name]):
            result.append((entry[0], replacements[dest_name], entry[2]))
            replaced.add(dest_name)
        else:
            result.append(entry)
    for dest_name, source_path in replacements.items():
        if dest_name not in replaced and os.path.exists(source_path):
            result.append((dest_name, source_path, 'BINARY'))
    return result

a.binaries = force_env_tcl_tk(a.binaries)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='zhijianwushuang',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['tcl86t.dll', 'tk86t.dll', '_tkinter.pyd'],
    name='zhijianwushuang',
)
