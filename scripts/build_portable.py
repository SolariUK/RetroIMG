"""Build a native portable test ZIP with Python, Pillow and completion included."""
from __future__ import annotations

import argparse
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


def build(output: Path) -> Path:
    output = output.resolve()
    if output.exists():
        raise ValueError('portable builds require a new output directory')
    # Fail before creating output if optional build/runtime dependencies are absent.
    dependencies = {name: version(name) for name in ('Pillow', 'prompt-toolkit', 'wcwidth', 'pyinstaller')}
    output.parent.mkdir(parents=True, exist_ok=True)
    system = 'windows' if sys.platform == 'win32' else sys.platform
    architecture = {'amd64': 'x64', 'x86_64': 'x64', 'aarch64': 'arm64'}.get(
        platform.machine().lower(), platform.machine().lower())
    with tempfile.TemporaryDirectory(prefix='retroimg-freeze-') as temporary:
        work = Path(temporary)
        environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(work / 'cache'))
        subprocess.run([
            sys.executable, '-m', 'PyInstaller', '--onedir', '--console', '--noupx',
            '--name', 'retroimg', '--paths', str(ROOT),
            '--distpath', str(output), '--workpath', str(work / 'work'),
            '--specpath', str(work / 'spec'),
            '--recursive-copy-metadata', 'retroimg',
            '--recursive-copy-metadata', 'prompt-toolkit',
            '--collect-data', 'prompt_toolkit', '--collect-data', 'wcwidth',
            str(ROOT / 'scripts' / 'retroimg_entry.py'),
        ], cwd=ROOT, env=environment, check=True)
    bundle = output / 'retroimg'
    shutil.copyfile(ROOT / 'LICENSE', bundle / 'LICENSE.txt')
    shutil.copyfile(ROOT / 'docs' / 'portable.md', bundle / 'README.md')
    if system == 'windows':
        (bundle / 'Start guided.cmd').write_bytes(
            b'@echo off\r\n"%~dp0retroimg.exe" guided %*\r\n'
            b'if errorlevel 1 pause\r\n')
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True)
    information = dict(version=__version__, commit=result.stdout.strip() if result.returncode == 0 else None,
                       platform=system, architecture=architecture, python=platform.python_version(),
                       built_utc=datetime.now(timezone.utc).isoformat(), dependencies=dependencies,
                       test_build=True)
    (bundle / 'BUILD.json').write_text(json.dumps(information, indent=2) + '\n', encoding='utf-8')
    archive = Path(shutil.make_archive(str(output / f'retroimg-{__version__}-{system}-{architecture}-test'),
                                     'zip', root_dir=output, base_dir='retroimg'))
    (output / 'SHA256SUMS.txt').write_text(f'{sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n')
    print(f'Portable test archive: {archive}', flush=True)
    return archive


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist' / 'portable')
    args = parser.parse_args(argv)
    try:
        build(args.output_dir)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
