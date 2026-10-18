"""Unpack a test ZIP outside the checkout and compare its CLI with Python output."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from PIL import Image

from retroimg import __version__
from retroimg.convert import convert_file
from retroimg.conversion_modes import CONSTRAINED_QUANTIZERS, MODE_OPTIONS
from retroimg.profiles import PROFILES
from retroimg.pixelate import pixelate_file


def check(archive: Path) -> None:
    with tempfile.TemporaryDirectory(prefix='retroimg-portable-check-') as temporary:
        directory = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(directory)
        bundle = directory / 'retroimg'
        executable = bundle / ('retroimg.exe' if os.name == 'nt' else 'retroimg')
        if os.name != 'nt':
            executable.chmod(executable.stat().st_mode | 0o111)
        environment = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME'}}
        environment['PYTHONUTF8'] = '1'
        def run(*arguments, input=None):
            result = subprocess.run([str(executable), *arguments], cwd=directory,
                                    env=environment, input=input, capture_output=True,
                                    text=True, encoding='utf-8', timeout=60)
            if result.returncode:
                raise RuntimeError(f'Portable command failed: {arguments}\n{result.stdout}\n{result.stderr}')
            return result.stdout
        assert run('--version').strip() == 'retroimg ' + __version__
        assert 'cpc-mode1' in run('profiles')
        assert 'builtin:cpc-macaws-bayer2' in run('presets', '--presets-dir', str(directory / 'presets'))
        source = directory / 'source image.png'
        image = Image.new('RGB', (32, 24))
        image.putdata([((x * 23 + y * 7) % 256, (x * 7 + y * 41) % 256, (x * 17 + y * 19) % 256)
                       for y in range(24) for x in range(32)])
        image.save(source)
        reference = directory / 'pixelation-reference.png'
        actual = directory / 'pixelated.png'
        pixelate_file(source, reference, block_size=4)
        run('pixelate', str(source), str(actual), '--block-size=4')
        with Image.open(reference) as expected, Image.open(actual) as result:
            assert result.size == expected.size and result.tobytes() == expected.tobytes()
        cases = []
        reference, actual = directory / 'effects-reference.png', directory / 'combined effects.png'
        effect_options = dict(profile_name='cpc-mode1', width=16, height=24, scale=3,
                              display_effect='crt-aperture', bloom_strength=.25,
                              bloom_radius=1.5, chromatic_strength=.5, rf_strength=.5, display_brightness=1.2)
        convert_file(source, reference, **effect_options)
        effect_arguments = [f'--{"profile" if key == "profile_name" else key.replace("_", "-")}={value}'
                            for key, value in effect_options.items()]
        run('convert', str(source), str(actual), *effect_arguments)
        with Image.open(reference) as expected, Image.open(actual) as result:
            assert result.size == expected.size and result.tobytes() == expected.tobytes()
        for name, profile in PROFILES.items():
            cases.append((name, {}))
            for flag, spec in MODE_OPTIONS.items():
                if profile.constraint_model in spec.constraint_models:
                    cases.extend((name, {flag: mode}) for mode in spec.modes if mode != 'bitmap'
                                 and (profile.constraint_model, mode) in CONSTRAINED_QUANTIZERS)
        for index, (profile, modes) in enumerate(cases):
            options = dict(profile_name=profile, width=160 if profile.startswith('atari') else 16,
                           height=32 if profile == 'nes' else 24, scale=1, dither='bayer', bayer_size=2,
                           brightness=1.1, contrast=1.2, hue_shift=10, green_gain=1.1, **modes)
            reference, actual = directory / 'reference.png', directory / f'actual-{index}.png'
            convert_file(source, reference, **options)
            arguments = [f'--{"profile" if key == "profile_name" else key.replace("_", "-")}={value}'
                         for key, value in options.items()]
            run('convert', str(source), str(actual), *arguments)
            with Image.open(reference) as expected, Image.open(actual) as result:
                assert result.size == expected.size, (profile, modes)
                assert result.convert('RGB').tobytes() == expected.convert('RGB').tobytes(), (profile, modes)
        jpeg, output = directory / 'source.jpg', directory / 'output.jpg'
        image.save(jpeg)
        run('convert', str(jpeg), str(output), '--scale=1')
        with Image.open(output) as converted:
            converted.verify()
        text = run('guided', '--print-only', '--preset', 'builtin:cpc-macaws-bayer2',
                   input=str(source) + '\n' + str(directory / 'guided.png') + '\n')
        assert 'Equivalent command' in text and 'Command only; no image written.' in text
        assert not (directory / 'guided.png').exists()
        preset = directory / 'my style.json'
        preset.write_text(json.dumps(dict(version=1, name='Portable test', settings=dict(
            profile='cpc-mode1', cpc_mode='constrained', brightness=1.1, contrast=1.2))), encoding='utf-8')
        run('convert', str(source), str(output), '--preset', str(preset), '--scale=1')
        assert (bundle / 'LICENSE.txt').is_file()
        assert json.loads((bundle / 'BUILD.json').read_text())['version'] == __version__
        print(f'Portable checks passed: {len(cases)} modes match Python; JPEG, presets and guided input work.')
        print('Archive SHA-256:', sha256(archive.read_bytes()).hexdigest())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    args = parser.parse_args(argv)
    check(args.archive)


if __name__ == '__main__':
    main()
