"""Validate a release tag and native bundles, then write their shared checksums."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import runpy
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def validate_tag(tag: str) -> str:
    version = runpy.run_path(str(ROOT / 'retroimg' / '__init__.py'))['__version__']
    if tag != f'v{version}':
        raise ValueError(f'Release tag must match the application version: v{version}')
    if not (ROOT / 'docs' / 'releases' / f'{version}.md').is_file():
        raise ValueError(f'Missing release notes: docs/releases/{version}.md')
    return version


def prepare_assets(directory: Path, *, tag: str, commit: str) -> Path:
    version = validate_tag(tag)
    if len(commit) != 40 or any(character not in '0123456789abcdef' for character in commit):
        raise ValueError('Expected a full Git commit SHA')
    targets = (('gui', 'windows'), ('gui', 'linux'), ('cli', 'windows'))
    expected = {f'{"retroimg-gui" if frontend == "gui" else "retroimg"}-{version}-{system}-x64.zip':
                (frontend, system) for frontend, system in targets}
    archives = {path.name: path for path in directory.glob('*.zip')}
    if archives.keys() != expected.keys():
        raise ValueError(f'Expected exactly these release ZIPs: {", ".join(sorted(expected))}')
    checksums = []
    for name, (frontend, system) in sorted(expected.items()):
        application = 'retroimg-gui' if frontend == 'gui' else 'retroimg'
        with zipfile.ZipFile(archives[name]) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'Corrupt ZIP: {name}')
            information = json.loads(archive.read(f'{application}/BUILD.json'))
            wanted = dict(version=version, commit=commit, frontend=frontend,
                          platform=system, architecture='x64', test_build=False)
            for key, value in wanted.items():
                actual = information.get(key)
                if actual != value or type(actual) is not type(value):
                    raise ValueError(f'{name}: {key} must be {value!r}, got {actual!r}')
            executable = application + ('.exe' if system == 'windows' else '')
            for relative in (executable, 'README.md', 'LICENSE.txt'):
                if f'{application}/{relative}' not in archive.namelist():
                    raise ValueError(f'{name}: missing {relative}')
        checksums.append(f'{sha256(archives[name].read_bytes()).hexdigest()}  {name}\n')
    manifest = directory / 'SHA256SUMS.txt'
    manifest.write_text(''.join(checksums), encoding='utf-8')
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--commit')
    parser.add_argument('--assets-dir', type=Path, default=Path('release-assets'))
    parser.add_argument('--check-only', action='store_true', help='only validate the tag, version and release notes')
    args = parser.parse_args(argv)
    try:
        validate_tag(args.tag)
        if args.check_only:
            print(f'Release version and notes verified: {args.tag}')
        else:
            if not args.commit:
                parser.error('--commit is required when preparing assets')
            manifest = prepare_assets(args.assets_dir, tag=args.tag, commit=args.commit)
            print(f'Three native release bundles verified; checksums: {manifest}')
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'Release preparation failed: {exc}\n')


if __name__ == '__main__':
    main()
