"""Test an extracted native desktop bundle, its real child worker and export."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def check(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='retroimg-gui-bundle-') as temporary:
        directory = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(directory)
        bundle = directory / 'retroimg-gui'
        executable = bundle / ('retroimg-gui.exe' if os.name == 'nt' else 'retroimg-gui')
        if os.name != 'nt':
            executable.chmod(executable.stat().st_mode | 0o111)
        environment = {key: value for key, value in os.environ.items()
                       if key not in {'PYTHONPATH', 'PYTHONHOME', 'QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH'}}
        environment.update(QT_QPA_PLATFORM='offscreen', PYTHONUTF8='1')
        report = directory / 'report.json'
        result = subprocess.run([str(executable), '--smoke-test', str(report)], cwd=directory,
                                env=environment, capture_output=True, text=True, encoding='utf-8', timeout=90)
        if result.returncode:
            raise RuntimeError(f'Desktop bundle failed: {result.returncode}\n{result.stdout}\n{result.stderr}\n'
                               + (report.read_text(encoding='utf-8') if report.exists() else 'No report'))
        information = json.loads(report.read_text(encoding='utf-8'))
        assert information['ok'] and information['reused_conversion']
        assert information['source_aspect']
        assert information['size'] == [48, 48]
        assert json.loads((bundle / 'BUILD.json').read_text())['frontend'] == 'gui'
        assert (bundle / 'LICENSE.txt').exists()
        print('Desktop bundle: window, background worker, cached rendering, presets and full-size export passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    check(parser.parse_args().archive)
