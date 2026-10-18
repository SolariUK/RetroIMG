"""Build a native portable ZIP with Python and application dependencies included."""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from retroimg import __version__

ROOT = Path(__file__).resolve().parents[1]


def build(output: Path, *, gui: bool = False, release: bool = False) -> Path:
    output = output.resolve()
    if output.exists():
        raise ValueError('portable builds require a new output directory')
    # Fail before creating output if optional build/runtime dependencies are absent.
    names = ('Pillow', 'PySide6-Essentials', 'shiboken6', 'pyinstaller') if gui else (
        'Pillow', 'prompt-toolkit', 'wcwidth', 'pyinstaller')
    dependencies = {name: version(name) for name in names}
    application = 'retroimg-gui' if gui else 'retroimg'
    if gui and sys.platform.startswith('linux'):
        try:
            ctypes.CDLL('libxcb-cursor.so.0')
        except OSError as exc:
            raise ValueError('Linux GUI builds need libxcb-cursor0 so the X11 plugin can be bundled. '
                             'Install it, or expose an extracted copy through LD_LIBRARY_PATH.') from exc
    output.parent.mkdir(parents=True, exist_ok=True)
    system = 'windows' if sys.platform == 'win32' else sys.platform
    architecture = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64'}.get(
        platform.machine().lower(), platform.machine().lower())
    with tempfile.TemporaryDirectory(prefix='retroimg-freeze-') as temporary:
        work = Path(temporary)
        environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / 'cache'))
        subprocess.run([
            sys.executable, '-m', 'PyInstaller', '--onedir', '--windowed' if gui else '--console', '--noupx',
            '--name', application, '--paths', str(ROOT),
            '--distpath', str(output), '--workpath', str(work / 'work'),
            '--specpath', str(work / 'spec'),
            '--recursive-copy-metadata', 'retroimg',
            *(argument for name in ('PyQt5', 'PyQt6', 'PySide2', *(() if gui else ('PySide6',)))
              for argument in ('--exclude-module', name)),
            *(['--recursive-copy-metadata', 'PySide6-Essentials'] if gui else [
                '--recursive-copy-metadata', 'prompt-toolkit',
                '--collect-data', 'prompt_toolkit', '--collect-data', 'wcwidth']),
            str(ROOT / 'scripts' / ('retroimg_gui_entry.py' if gui else 'retroimg_entry.py')),
        ], cwd=ROOT, env=environment, check=True)
    bundle = output / application
    shutil.copyfile(ROOT / 'LICENSE', bundle / 'LICENSE.txt')
    shutil.copyfile(ROOT / 'docs' / ('gui.md' if gui else 'portable.md'), bundle / 'README.md')
    if gui and sys.platform.startswith('linux'):
        cursor_licences = [Path('/usr/share/doc/libxcb-cursor0/copyright')]
        cursor_licences.extend(Path(folder).parent.parent / 'share/doc/libxcb-cursor0/copyright'
                               for folder in os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep) if folder)
        for licence in cursor_licences:
            if licence.is_file():
                shutil.copyfile(licence, bundle / 'LICENSE-libxcb-cursor0.txt')
                break
    if system == 'windows' and not gui:
        (bundle / 'Start guided.cmd').write_bytes(
            b'@echo off\r\n"%~dp0retroimg.exe" guided %*\r\n'
            b'if errorlevel 1 pause\r\n')
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    information = dict(version=__version__, commit=result.stdout.strip() if result.returncode == 0 else None,
                       platform=system, architecture=architecture, python=platform.python_version(),
                       built_utc=datetime.now(timezone.utc).isoformat(), dependencies=dependencies,
                       test_build=not release, frontend='gui' if gui else 'cli')
    (bundle / 'BUILD.json').write_text(json.dumps(information, indent=2) + '\n', encoding='utf-8')
    suffix = '' if release else '-test'
    archive = Path(shutil.make_archive(str(output / f'{application}-{__version__}-{system}-{architecture}{suffix}'),
                                     'zip', root_dir=output, base_dir=application))
    checksum = f'{sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n'
    (output / 'SHA256SUMS.txt').write_text(checksum, encoding='utf-8')
    (output / f'{archive.name}.sha256').write_text(checksum, encoding='utf-8')
    print(f'Portable {"release" if release else "test"} archive: {archive}', flush=True)
    return archive


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist' / 'portable')
    parser.add_argument('--gui', action='store_true', help='build the optional desktop frontend instead of the console application')
    parser.add_argument('--release', action='store_true', help='omit the test suffix and mark release build metadata')
    args = parser.parse_args(argv)
    try:
        build(args.output_dir, gui=args.gui, release=args.release)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
