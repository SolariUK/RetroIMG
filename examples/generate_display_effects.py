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
EFFECT_DIRECTORIES = {'gameboy-lcd': 'display-effects', 'scanlines': 'scanlines',
                      'crt-aperture': 'crt-aperture', 'bloom': 'bloom',
                      'chromatic-aberration': 'chromatic-aberration'}
CROP = (384, 288, 896, 800)  # Logical pixels (48, 36) to (112, 100), at scale 8.


def generate(output: Path, *, replace: bool = False, effect: str = 'gameboy-lcd') -> None:
    if effect not in EFFECT_DIRECTORIES:
        raise ValueError('unknown example effect: ' + effect)
    lcd = effect == 'gameboy-lcd'
    optical = effect in ('bloom', 'chromatic-aberration')
    crop = (768, 32, 1280, 544) if optical else CROP
    prefix = 'gameboy' if lcd else 'megadrive'
    if lcd:
        examples = EXAMPLES
    elif effect == 'scanlines':
        examples = (('plain', None), ('scanlines-subtle', .35), ('scanlines-strong', .85))
    elif effect == 'bloom':
        examples = (('plain', None), ('bloom-only', .25), ('crt-only', .35),
                    ('crt-bloom-subtle', .25), ('crt-bloom-strong', .85), ('crt-bloom-wide', .85))
    elif effect == 'chromatic-aberration':
        examples = (('plain', None), ('chromatic-subtle', .25), ('chromatic-strong', .85),
                    ('crt-bloom', None), ('crt-bloom-chromatic-subtle', .25), ('crt-bloom-chromatic-strong', .85))
    else:
        examples = (('plain', None), ('scanlines-only', .35), ('crt-aperture-subtle', .35),
                    ('crt-aperture-strong', .85), ('crt-aperture-strong-brighter', .85))
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
    source_id = 'city-night' if optical else 'macaws'
    source = next(s for s in json.loads((ROOT / 'examples/sources.json').read_text()) if s['id'] == source_id)
    path = ROOT / 'samples/sources' / source['file']
    if not source['public'] or sha256(path.read_bytes()).hexdigest() != source['reference_sha256']:
        raise ValueError('expected the catalogued public reference image')
    lines = (['# Game Boy LCD display examples', '',
              'The same 160×144 four-shade conversion, rendered at 8× (1280×1152).',
              'Each native Game Boy pixel occupies an 8×8 output area so the LCD cell borders',
              'and shadows can be drawn. The conversion still contains only 160×144 logical pixels.'] if lcd else
             ['# Chromatic aberration and combined effects' if effect == 'chromatic-aberration' else
              '# Bloom and combined CRT examples' if effect == 'bloom' else
              '# CRT aperture-grille examples' if effect == 'crt-aperture' else '# Scanline display examples', '',
              'The same 320×224 Mega Drive tile conversion, rendered at scale 4 with',
              '4:3 aspect correction (1280×960). One scanline beam per logical row:',
              '224 beams across the full image height, with smooth fractional spacing.'])
    if effect == 'crt-aperture':
        lines += ['The grille repeats one red, green and blue stripe across three output columns.',
                  'Strength controls both the grille and scanlines. A scanlines-only version',
                  'at the same subtle strength isolates what the grille adds.',
                  'The final example adds display brightness 2.0 after the strong effect,',
                  'preserving the same palette conversion and dithering.']
    if effect == 'bloom':
        lines += ['The night photograph has bright window lights against dark brickwork,',
                  'with a detail crop around an isolated lit window to make the halo easier to judge.',
                  'Bloom adds a soft highlight glow without blurring the original pixels.',
                  'Compare bloom alone, CRT alone, then CRT with subtle and stronger bloom.',
                  'All CRT versions use the same grille/scanline strength 0.35;',
                  'the regular comparisons use radius 1 logical pixel width (4 output pixels).',
                  'The final wider-glow example keeps strong bloom 0.85 and uses radius 3',
                  '(12 output pixels), explicitly demonstrating the spread control.',
                  'Display brightness stays neutral at 1 throughout.']
    if effect == 'chromatic-aberration':
        lines += ['Bright windows near the frame edge show radial red/blue colour separation.',
                  'Red expands outwards, blue contracts inwards, and green stays fixed.',
                  'The crop retains the full frame centre and displacement; it is not reprocessed.',
                  'Compare plain, subtle/strong chromatic aberration alone, then CRT + bloom',
                  'without and with the same chromatic settings. CRT strength remains 0.35,',
                  'bloom strength 0.25, bloom radius 1, and display brightness 1 throughout.',
                  'Order: chromatic aberration, display treatment, bloom, final display brightness.']
    lines += ['Each detail crop is an unscaled 512×512 section of its full-size PNG.',
             'Open the PNGs at 100% to judge the display pattern; browser fitting can introduce moiré.', '',
             f'Source: [{source["file"]}](../sources/{source["file"]}).',
             f'Credit: {source["credit"]}. {source["rights"]}',
             'See [source records](../README.md) and [effect documentation](../../docs/display-effects.md).', '',
             ('The LCD treatment simulates inset cells and small shadows.' if lcd else
              'The original indexed conversion stays unchanged by all effects.' if optical else
              'The CRT treatment combines scanlines and an RGB grille in linear light; there is no bloom.'
              if effect == 'crt-aperture' else
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
            selected_effect = 'scanlines' if name == 'scanlines-only' else effect
            if effect == 'bloom':
                selected_effect = 'crt-aperture' if name.startswith('crt-') else 'none'
                if selected_effect != 'none':
                    options.update(display_effect=selected_effect, effect_strength=.35)
                if 'bloom' in name:
                    options.update(bloom_strength=strength, bloom_radius=3.0 if name == 'crt-bloom-wide' else 1.0)
            elif effect == 'chromatic-aberration':
                selected_effect = 'crt-aperture' if name.startswith('crt-') else 'none'
                if selected_effect != 'none':
                    options.update(display_effect=selected_effect, effect_strength=.35,
                                   bloom_strength=.25, bloom_radius=1.0)
                if strength is not None:
                    options['chromatic_strength'] = strength
            elif strength is not None:
                options.update(display_effect=selected_effect, effect_strength=strength)
            if name == 'crt-aperture-strong-brighter':
                options['display_brightness'] = 2.0
            if baseline is None:
                baseline = convert_file(path, stage / filename, **options)
            else:
                render_indexed(baseline, scale=options['scale'], pixel_aspect=aspect,
                               display_effect=options.get('display_effect', 'none'),
                               effect_strength=options.get('effect_strength'),
                               bloom_strength=options.get('bloom_strength', 0),
                               bloom_radius=options.get('bloom_radius', 1),
                               chromatic_strength=options.get('chromatic_strength', 0),
                               display_brightness=options.get('display_brightness', 1.0)).save(stage / filename)
            crop_name = f'{prefix}-{name}-crop.png'
            with Image.open(stage / filename) as image:
                image.crop(crop).save(stage / crop_name)
                size = list(image.size)
            flags = ' '.join(f'--{("profile" if key == "profile_name" else key.replace("_", "-"))} {value}'
                             for key, value in options.items())
            command = f'retroimg convert /path/to/image.jpg {filename} {flags}'
            records.append(dict(filename=filename, size=size, crop=crop_name, crop_box=list(crop),
                                sha256=sha256((stage / filename).read_bytes()).hexdigest(),
                                crop_sha256=sha256((stage / crop_name).read_bytes()).hexdigest(),
                                settings=options, command=command))
            treatment = ('LCD' if lcd else 'CRT aperture' if selected_effect == 'crt-aperture' else
                         'Scanlines only' if name == 'scanlines-only' else 'Scanlines')
            label = 'Plain conversion' if strength is None else f'{treatment} / strength {strength}'
            if effect == 'bloom' and strength is not None:
                label = ('CRT alone / strength 0.35' if name == 'crt-only' else
                         f'{"CRT + bloom" if selected_effect != "none" else "Bloom alone"} / bloom strength {strength}')
                if 'bloom' in name:
                    label += f' / radius {options["bloom_radius"]}'
            if effect == 'chromatic-aberration' and name != 'plain':
                label = 'CRT + bloom, without chromatic aberration' if name == 'crt-bloom' else (
                    ('CRT + bloom + chromatic aberration' if selected_effect != 'none' else 'Chromatic aberration alone')
                    + f' / chromatic strength {strength}')
            if 'display_brightness' in options:
                label += f' / display brightness {options["display_brightness"]} after effects'
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
    parser.add_argument('--effect', choices=tuple(EFFECT_DIRECTORIES), default='gameboy-lcd')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        directory = args.output_dir or ROOT / 'samples' / EFFECT_DIRECTORIES[args.effect]
        generate(directory, replace=args.replace, effect=args.effect)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
