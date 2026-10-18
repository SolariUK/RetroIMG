"""A draft release must contain complete bundles from one version and commit."""
from hashlib import sha256
import json
from pathlib import Path
import runpy
import zipfile

import pytest

from retroimg import __version__


release = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_release.py'))
TAG = f'v{__version__}'
COMMIT = 'abcde12345' * 4


@pytest.fixture
def bundles(tmp_path):
    def create(frontend, system, /, **changes):
        application = 'retroimg-gui' if frontend == 'gui' else 'retroimg'
        path = tmp_path / f'{application}-{__version__}-{system}-x64.zip'
        information = dict(version=__version__, commit=COMMIT, frontend=frontend,
                           platform=system, architecture='x64', test_build=False)
        information.update(changes)
        executable = application + ('.exe' if system == 'windows' else '')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr(f'{application}/BUILD.json', json.dumps(information))
            for name in (executable, 'README.md', 'LICENSE.txt'):
                archive.writestr(f'{application}/{name}', 'fixture')
        return path
    for frontend, system in (('gui', 'windows'), ('gui', 'linux'), ('cli', 'windows')):
        create(frontend, system)
    return tmp_path, create


def test_release_manifest_lists_exact_files_and_checksums(bundles):
    directory, _ = bundles
    manifest = release['prepare_assets'](directory, tag=TAG, commit=COMMIT)
    actual = dict(line.split('  ') for line in manifest.read_text().splitlines())
    assert len(actual) == 3
    for checksum, name in actual.items():
        assert checksum == sha256((directory / name).read_bytes()).hexdigest()


@pytest.mark.parametrize('changes', [dict(commit='f' * 40), dict(version='0.1.0'),
                                    dict(test_build=True), dict(test_build=0),
                                    dict(platform='linux'), dict(architecture='arm64'),
                                    dict(frontend='cli')])
def test_release_rejects_wrong_build_metadata(bundles, changes):
    directory, create = bundles
    create('gui', 'windows', **changes)
    with pytest.raises(ValueError):
        release['prepare_assets'](directory, tag=TAG, commit=COMMIT)
    assert not (directory / 'SHA256SUMS.txt').exists()


def test_release_rejects_incomplete_download_set(bundles):
    directory, _ = bundles
    next(directory.glob('*linux*.zip')).rename(directory / 'renamed.zip')
    with pytest.raises(ValueError, match='exactly') as failure:
        release['prepare_assets'](directory, tag=TAG, commit=COMMIT)
    assert 'renamed.zip' in str(failure.value)
    assert str(directory) in str(failure.value)


def test_release_explains_when_downloads_were_unpacked(tmp_path):
    (tmp_path / 'retroimg-gui').mkdir()
    with pytest.raises(ValueError, match='Found in') as failure:
        release['prepare_assets'](tmp_path, tag=TAG, commit=COMMIT)
    assert 'retroimg-gui' in str(failure.value).split('Found in', 1)[1]


def test_release_rejects_missing_executable(bundles):
    directory, _ = bundles
    path = next(directory.glob('*linux*.zip'))
    with zipfile.ZipFile(path) as archive:
        entries = [(name, archive.read(name)) for name in archive.namelist()
                   if name != 'retroimg-gui/retroimg-gui']
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in entries:
            archive.writestr(name, data)
    with pytest.raises(ValueError, match='missing retroimg-gui'):
        release['prepare_assets'](directory, tag=TAG, commit=COMMIT)


def test_release_tag_requires_matching_application_version():
    assert release['validate_tag'](TAG) == __version__
    with pytest.raises(ValueError, match='application version'):
        release['validate_tag']('v9.9.9')
