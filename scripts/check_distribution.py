"""Install each built artifact in a fresh environment and exercise its CLI.

Run after `python -m build`. Environments and outputs stay in a temporary
directory outside the checkout; package-index access is needed for dependencies.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import venv


PROBE = '''
import importlib.metadata
import importlib.util
from pathlib import Path
import subprocess
import sys

from PIL import Image
import retroimg

environment, extra = Path(sys.argv[1]), sys.argv[2]
assert Path(retroimg.__file__).resolve().is_relative_to(environment.resolve())
assert retroimg.__version__ == importlib.metadata.version('retroimg')
assert (importlib.util.find_spec('prompt_toolkit') is not None) == (extra == 'guided')
cli = environment / ('Scripts/retroimg.exe' if sys.platform == 'win32' else 'bin/retroimg')
def run(*args, input=None):
    return subprocess.run([str(cli), *args], input=input, capture_output=True,
                          text=True, check=True, timeout=30).stdout
assert run('--version').strip() == 'retroimg ' + retroimg.__version__
assert 'cpc-mode1' in run('profiles')
assert 'builtin:cpc-macaws-bayer2' in run('presets', '--presets-dir', 'presets')
source, output = Path('source image.png'), Path('output image.png')
Image.new('RGB', (16, 24), (60, 150, 230)).save(source)
pixelated = Path('pixelated.png')
run('pixelate', str(source), str(pixelated), '--block-size', '4')
with Image.open(pixelated) as image:
    assert image.size == (16, 24)
    assert image.getpixel((0, 0)) == (60, 150, 230)
run('convert', str(source), str(output), '--preset', 'builtin:cpc-macaws-bayer2',
    '--width', '16', '--height', '24', '--scale', '1', '--presets-dir', 'presets')
with Image.open(output) as image:
    assert image.size == (16, 24)
    image.verify()
combined = Path('combined effects.png')
run('convert', str(source), str(combined), '--profile', 'cpc-mode1',
    '--width', '16', '--height', '24', '--scale', '3', '--display-effect', 'crt-aperture',
    '--bloom-strength', '0.25', '--bloom-radius', '1.5', '--display-brightness', '1.2')
with Image.open(combined) as image:
    assert image.size == (48, 72)
    image.verify()
text = run('guided', '--print-only', '--preset', 'builtin:cpc-macaws-bayer2',
           '--presets-dir', 'presets', input=str(source.resolve()) + '\\n' + str(output.resolve()) + '\\n')
assert 'Equivalent command' in text
assert 'Command only; no image written.' in text
assert not Path('presets').exists()
if extra == 'guided':
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from retroimg.path_input import DirectoryPathCompleter
    matches = list(DirectoryPathCompleter().get_completions(
        Document('source im'), CompleteEvent(completion_requested=True)))
    assert any('source im' + match.text == str(source) for match in matches)
print('Installed package checks passed:', retroimg.__version__, extra)
'''


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=Path('dist'))
    parser.add_argument('--extra', choices=('base', 'guided'), default='base')
    args = parser.parse_args(argv)
    wheels = list(args.dist_dir.glob('retroimg-*.whl'))
    sources = list(args.dist_dir.glob('retroimg-*.tar.gz'))
    if len(wheels) != 1 or len(sources) != 1:
        parser.error('expected exactly one retroimg wheel and one source archive; use a fresh build directory')
    clean_env = {key: value for key, value in os.environ.items()
                 if key not in {'PYTHONPATH', 'PYTHONHOME'}}
    clean_env['PYTHONNOUSERSITE'] = '1'
    for artifact in (wheels[0], sources[0]):
        with tempfile.TemporaryDirectory(prefix='retroimg-package-') as temporary:
            work = Path(temporary)
            environment = work / 'environment'
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            requirement = str(artifact.resolve()) + ('[guided]' if args.extra == 'guided' else '')
            subprocess.run([str(python), '-m', 'pip', 'install', requirement],
                           cwd=work, env=clean_env, check=True)
            subprocess.run([str(python), '-I', '-c', PROBE, str(environment), args.extra],
                           cwd=work, env=clean_env, check=True)
            print(f'Checked {artifact.name} ({args.extra})', flush=True)


if __name__ == '__main__':
    main()
