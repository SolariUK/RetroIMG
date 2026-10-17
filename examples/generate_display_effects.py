"""Generate a handful of full-size display-effect examples and unscaled crops."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from PIL import Image

from retroimg.convert import convert_file
from retroimg.profiles import get_profile
from retroimg.render import render_indexed

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (('plain', None), ('lcd-subtle', .35), ('lcd-strong', .85))
CROP = (384, 288, 896, 800)  # Logical pixels (48, 36) to (112, 100), at scale 8.


def generate(output: Path, *, replace: bool = False, effect: str = 'gameboy-lcd') -> None:
    if effect not in ('gameboy-lcd', 'scanlines'):
        raise ValueError('expected gameboy-lcd or scanlines')
    lcd = effect == 'gameboy-lcd'
    prefix = 'gameboy' if lcd else 'megadrive'
    examples = EXAMPLES if lcd else (('plain', None), ('scanlines-subtle', .35), ('scanlines-strong', .85))
    base_options = (dict(profile_name='gameboy', gameboy_mode='tiles', scale=8) if lcd else
                    dict(profile_name='megadrive-320', megadrive_mode='tiles', scale=4))
    profile = get_profile(base_options['profile_name'])
    aspect = profile.geometry.pixel_aspect if profile.aspect_correct_preview else 1
    names = {'README.md', 'manifest.json',
             *(f'{prefix}-{name}{suffix}.png' for name, _ in examples for suffix in ('', '-crop'))}
    if output.exists():
        if not replace:
            raise ValueError('output directory exists; use --replace to refresh known examples')
        if not output.is_dir() or any(p.name not in names or not p.is_file() or p.is_symlink() for p in output.iterdir()):
            raise ValueError('output directory contains unmanaged files')
    source = next(s for s in json.loads((ROOT / 'examples/sources.json').read_text()) if s['id'] == 'macaws')
    path = ROOT / 'samples/sources' / source['file']
    if not source['public'] or sha256(path.read_bytes()).hexdigest() != source['reference_sha256']:
        raise ValueError('expected the catalogued public reference image')
    lines = (['# Game Boy LCD display examples', '',
              'The same 160×144 four-shade conversion, rendered at 8× (1280×1152).',
              'Each native Game Boy pixel occupies an 8×8 output area so the LCD cell borders',
              'and shadows can be drawn. The conversion still contains only 160×144 logical pixels.'] if lcd else
             ['# Scanline display examples', '',
              'The same 320×224 Mega Drive tile conversion, rendered at scale 4 with',
              '4:3 aspect correction (1280×960). One scanline beam per logical row:',
              '224 beams across the full image height, with smooth fractional spacing.'])
    lines += ['Each detail crop is an unscaled 512×512 section of its full-size PNG.',
             'Open the PNGs at 100% to judge the display pattern; browser fitting can introduce moiré.', '',
             f'Source: [{source["file"]}](../sources/{source["file"]}).',
             f'Credit: {source["credit"]}. {source["rights"]}',
             'See [source records](../README.md) and [effect documentation](../../docs/display-effects.md).', '',
             ('The LCD treatment simulates inset cells and small shadows.' if lcd else
              'Scanlines dim row boundaries in linear light; there is no phosphor mask or bloom.'),
             'This is a static aesthetic approximation. Conversion codes are identical.', '']
    records = []
    baseline = None
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.retroimg-effects-', dir=output.parent) as temporary:
        stage = Path(temporary)
        for name, strength in examples:
            filename = f'{prefix}-{name}.png'
            options = dict(base_options, fit=source['fit'], dither='bayer', bayer_size=4)
            if strength is not None:
                options.update(display_effect=effect, effect_strength=strength)
            if baseline is None:
                baseline = convert_file(path, stage / filename, **options)
            else:
                render_indexed(baseline, scale=options['scale'], pixel_aspect=aspect,
                               display_effect=effect, effect_strength=strength).save(stage / filename)
            crop_name = f'{prefix}-{name}-crop.png'
            with Image.open(stage / filename) as image:
                image.crop(CROP).save(stage / crop_name)
                size = list(image.size)
            flags = ' '.join(f'--{("profile" if key == "profile_name" else key.replace("_", "-"))} {value}'
                             for key, value in options.items())
            command = f'retroimg convert /path/to/image.jpg {filename} {flags}'
            records.append(dict(filename=filename, size=size, crop=crop_name, crop_box=list(CROP),
                                sha256=sha256((stage / filename).read_bytes()).hexdigest(),
                                crop_sha256=sha256((stage / crop_name).read_bytes()).hexdigest(),
                                settings=options, command=command))
            label = 'Plain conversion' if strength is None else f'{"LCD" if lcd else "Scanlines"} / strength {strength}'
            lines.extend([f'## {label}', '', f'[Open full-size example]({filename}) · [Open detail crop]({crop_name})',
                          '', f'![{label}, unscaled detail]({crop_name})', '', '```bash', command, '```', ''])
        lines.extend(['Refresh from the project root:', '', '```bash',
                      f'python examples/generate_display_effects.py --effect {effect} --replace', '```', ''])
        manifest = dict(version=1, source=source, logical_size=[baseline.width, baseline.height], examples=records)
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (stage / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
        output.mkdir(exist_ok=True)
        for file in stage.iterdir():
            os.replace(file, output / file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--effect', choices=('gameboy-lcd', 'scanlines'), default='gameboy-lcd')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        directory = args.output_dir or ROOT / 'samples' / ('display-effects' if args.effect == 'gameboy-lcd' else 'scanlines')
        generate(directory, replace=args.replace, effect=args.effect)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
