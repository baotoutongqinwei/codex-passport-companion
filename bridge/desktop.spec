# Build with tools/build_desktop.sh on an Apple Silicon Mac.
from pathlib import Path
import importlib.metadata
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPEC).resolve().parents[1]
engine = root / '.local/whisper.cpp/build/bin/whisper-cli'
if not engine.is_file():
    raise SystemExit('Build the pinned CPU whisper engine with tools/bootstrap_bridge.py first.')
datas = collect_data_files('opencc')
datas += collect_data_files('esptool')
datas += [(str(root / 'build/desktop-firmware'), 'firmware')]
datas += [(str(root / 'assets/images/codex-passport-icon.png'), 'assets/images')]
datas += [(str(root / 'LICENSE'), 'licenses/project'),
          (str(root / '.local/whisper.cpp/LICENSE'), 'licenses/whisper.cpp'),
          (str(Path(sys.base_prefix) / f'lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt'), 'licenses/python'),
          (str(root / 'bridge/licenses/pyserial-LICENSE.txt'), 'licenses/pyserial')]
for package in ('bleak', 'opencc-python-reimplemented', 'pyobjc-framework-Cocoa', 'pyobjc-framework-CoreBluetooth',
                'typing-extensions', 'async-timeout', 'pyinstaller', 'esptool', 'bitstring', 'bitarray',
                'cryptography', 'cffi', 'pycparser', 'ecdsa', 'reedsolo', 'PyYAML', 'intelhex', 'six',
                'argcomplete', 'tibs'):
    distribution = importlib.metadata.distribution(package)
    for file in distribution.files:
        if Path(file).name.lower().startswith(('license', 'copying')) or Path(file).name.lower() == 'authors.rst':
            datas.append((str(distribution.locate_file(file)), 'licenses/' + package))
a = Analysis([str(root / 'bridge/desktop.py')], pathex=[str(root / 'bridge'), str(root / 'tools')],
             binaries=[(str(engine), 'voice/bin')], datas=datas,
             hiddenimports=['bleak.backends.corebluetooth', 'serial.tools.list_ports_osx'] + collect_submodules('esptool'),
             excludes=['tkinter', 'unittest', 'pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CodexPassport',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, argv_emulation=False, target_arch='arm64', codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CodexPassport')
app = BUNDLE(coll, name='Codex Passport.app', bundle_identifier='local.codex-passport.companion',
             icon=str(root / 'assets/images/codex-passport.icns'),
             info_plist={'CFBundleDisplayName': 'Codex 随行助手', 'CFBundleShortVersionString': '0.9.2',
                         'NSBluetoothAlwaysUsageDescription': '通过蓝牙连接你的 AI Passport，传输语音与对话状态。',
                         'NSBluetoothPeripheralUsageDescription': '连接你选择的 AI Passport 卡片。',
                         'NSHighResolutionCapable': True, 'LSMinimumSystemVersion': '15.0'})
