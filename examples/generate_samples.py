"""Generate a bounded set of screen-sized documentation panels."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

from retroimg.convert import convert_file

if __package__:
    from .generate_gallery import BUNDLED_SOURCES, CATALOG, Variant, check_constraints, command_for, variants_for
else:
    from generate_gallery import BUNDLED_SOURCES, CATALOG, Variant, check_constraints, command_for, variants_for

PANEL_WIDTH = 800
DEFAULT_OUTPUT = BUNDLED_SOURCES.parent / 'comparisons'
LEGACY_SHEETS = {'macaws-cpc.jpg', 'portrait-colour-teletext.jpg', 'lush-landscape-c64.jpg',
                 'portrait-colour-teletext.png'}


@dataclass(frozen=True)
class Panel:
    source: str
    family: str
    title: str
    variants: tuple[Variant, ...]
    show_source: bool = True

    @property
    def filename(self) -> str:
        return f'{self.source}-{self.family}.png'


def selections() -> tuple[Panel, ...]:
    """Cover mode differences and useful adjustments within twenty tiles each."""
    baselines = {family: {v.slug: v for v in variants_for(family)} for family in
                 ('teletext', 'c64', 'cpc', 'spectrum', 'bbc', 'amiga', 'atari2600')}
    dithers = (('none', 'No dither'), ('floyd-steinberg', 'FS'), ('bayer', 'Bayer 4x4'))

    def make(family, slug, label, dither='none', **controls):
        base = baselines[family][slug]
        options = dict(base.options, dither=dither, **controls)
        if dither == 'bayer':
            options.setdefault('bayer_size', 4)
        identifier = slug + '-' + dither + ''.join(f'-{key}-{value}' for key, value in controls.items())
        return Variant(identifier, label, options, base.size)

    panels = []
    variants = []
    for dither, label, controls in (
        ('none', 'No dither', {}), ('floyd-steinberg', 'FS', {}),
        ('bayer', 'Bayer 2x2', dict(bayer_size=2)),
        ('bayer', 'Bayer 4x4', dict(bayer_size=4)),
        ('bayer', 'Bayer 8x8', dict(bayer_size=8)),
    ):
        for mode in ('bitmap', 'mosaic'):
            variants.append(make('teletext', mode, f'{mode.title()} / {label}', dither, **controls))
    for slug, label in (('mosaic-large', 'Mosaic / 160x150 logical / FS'),
                        ('mosaic-c64', 'Mosaic / C64 palette / FS'),
                        ('mosaic-spectrum', 'Mosaic / Spectrum palette / FS')):
        variants.append(make('teletext', slug, label, 'floyd-steinberg'))
    panels.append(Panel('macaws', 'teletext', 'Teletext / bitmap, mosaics and palette swaps', tuple(variants)))

    variants = []
    for mode, title, controls in (
        ('bitmap', 'Hires geometry bitmap', dict(profile_name='c64-hires')),
        ('bitmap', 'Wide bitmap', {}), ('multicolour', 'Multicolour', {}),
    ):
        for dither, label in dithers:
            variants.append(make('c64', mode, f'{title} / {label}', dither, **controls))
    for label, controls in (
        ('Multicolour / FS / saturation 1.3', dict(saturation=1.3)),
        ('Multicolour / FS / green 1.15', dict(green_gain=1.15)),
        ('Multicolour / FS / hue 20 + green 1.15', dict(hue_shift=20, green_gain=1.15)),
        ('FS / sat 1.3 + hue 20 + green 1.15', dict(saturation=1.3, hue_shift=20, green_gain=1.15)),
    ):
        variants.append(make('c64', 'multicolour', label, 'floyd-steinberg', **controls))
    variants.append(make('c64', 'multicolour', 'Bayer 4 / sat 1.3 + hue 20 + green 1.15',
                         'bayer', saturation=1.3, hue_shift=20, green_gain=1.15))
    panels.append(Panel('lush-landscape', 'c64', 'Commodore 64 / geometry, constraints and greener colour', tuple(variants)))

    variants = []
    for mode in range(3):
        for dither, label in dithers:
            for constraint in ('bitmap', 'constrained'):
                variants.append(make('cpc', f'mode{mode}-{constraint}',
                                     f'Mode {mode} / {constraint} / {label}', dither))
    panels.append(Panel('macaws', 'cpc', 'Amstrad CPC / modes 0, 1 and 2 / bitmap vs constrained', tuple(variants)))

    variants = []
    for dither, label in dithers:
        for mode in ('bitmap', 'attributes'):
            variants.append(make('spectrum', mode, f'{mode.title()} / {label}', dither))
    for size in (2, 8):
        variants.append(make('spectrum', 'attributes', f'Attributes / Bayer {size}x{size}', 'bayer', bayer_size=size))
    panels.append(Panel('lush-landscape', 'spectrum', 'ZX Spectrum / bitmap and attribute cells', tuple(variants)))

    variants = []
    for mode in (0, 1, 2, 4, 5):
        for dither, label in dithers:
            variants.append(make('bbc', f'mode{mode}-constrained', f'Mode {mode} / constrained / {label}', dither))
    for dither, label in dithers[:2]:
        variants.append(make('bbc', 'mode0-bitmap', f'Mode 0 / unrestricted / {label}', dither))
    panels.append(Panel('macaws', 'bbc', 'BBC Micro / modes 0, 1, 2, 4 and 5', tuple(variants)))

    variants = []
    for slug, title in (('lores-bitmap', 'Lores / unrestricted RGB12'),
                        *[(f'lores-{count}', f'Lores / {count} colours') for count in (2, 4, 8, 16, 32)]):
        for dither, label in dithers[:2]:
            variants.append(make('amiga', slug, f'{title} / {label}', dither))
    for mode in ('ehb', 'ham'):
        for dither, label in dithers:
            variants.append(make('amiga', mode, f'{mode.upper()} / {label}', dither))
    variants.append(make('amiga', 'hires-16', 'Hires / 16 colours / FS', 'floyd-steinberg'))
    panels.append(Panel('portrait-colour', 'amiga', 'Amiga / RGB12, indexed palettes, EHB and HAM6', tuple(variants)))

    variants = []
    for mode in ('bitmap', 'playfield', 'repeat', 'mirror'):
        for dither, label in dithers:
            variants.append(make('atari2600', f'ntsc-{mode}', f'NTSC / {mode} / {label}', dither))
    for mode in ('bitmap', 'playfield', 'repeat', 'mirror'):
        variants.append(make('atari2600', f'pal-{mode}', f'PAL / {mode} / FS', 'floyd-steinberg'))
    variants.append(make('atari2600', 'ntsc-chunky', 'NTSC / playfield / 8-line bands / FS', 'floyd-steinberg'))
    panels.append(Panel('lush-landscape', 'atari2600', 'Atari 2600 / bitmap, playfield, repeat and mirror', tuple(variants)))

    base = dict(profile_name='cpc-mode1', cpc_mode='constrained', dither='bayer',
                bayer_size=2, saturation=1.1, scale=2)
    variants = []
    for slug, label, controls in (
        ('baseline', 'Baseline: saturation 1.1', {}),
        ('blue', 'Blue gain 1.5', dict(blue_gain=1.5)),
        ('brightness', 'Blue 1.5 + brightness 1.5', dict(blue_gain=1.5, brightness=1.5)),
        ('contrast', 'Blue 1.5 + brightness 1.5 + contrast 1.2',
         dict(blue_gain=1.5, brightness=1.5, contrast=1.2)),
    ):
        variants.append(Variant(slug, label, dict(base, **controls), (640, 400)))
    panels.append(Panel('macaws', 'adjustments', 'CPC mode 1 / Bayer 2x2 / source adjustments', tuple(variants), False))
    for family, source, title, modes in (
        ('megadrive', 'macaws', 'Sega Mega Drive / Genesis / bitmap and palette-bank tiles', ('bitmap', 'tiles')),
        ('snes', 'lush-landscape', 'SNES / bitmap, 4bpp tiles and 8bpp indexed', ('bitmap', 'tiles', 'indexed')),
    ):
        variants = []
        profile = 'megadrive-320' if family == 'megadrive' else 'snes'
        size = (640, 480) if family == 'megadrive' else (597, 448)
        for dither, label in dithers:
            for mode in modes:
                options = dict(profile_name=profile, **{family + '_mode': mode}, dither=dither, scale=2)
                if dither == 'bayer':
                    options['bayer_size'] = 4
                variants.append(Variant(f'{mode}-{dither}', f'{mode.title()} / {label}', options, size))
        panels.append(Panel(source, family, title, tuple(variants)))
    return tuple(panels)


def panel_size(panel: Panel) -> tuple[int, int]:
    tiles = len(panel.variants) + int(panel.show_source)
    if not 1 <= tiles <= 20:
        raise ValueError('sample panels must contain between one and twenty tiles')
    return PANEL_WIDTH, 72 + 264 * ((tiles + 1) // 2)


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow 10.0 has a fixed-size default font.
        return ImageFont.load_default()


def _tile(sheet: Image.Image, index: int, label: str, image: Image.Image, *, source: bool = False) -> None:
    x, y = 16 + (index % 2) * 392, 48 + (index // 2) * 264
    draw = ImageDraw.Draw(sheet)
    draw.multiline_text((x, y), '\n'.join(textwrap.wrap(label, width=43)),
                        fill='white', font=_font(14), spacing=2)
    # Average reduced pixel patterns so Bayer textures do not alias into bands.
    # Keep enlarged conversions crisp; photographs use smooth resizing throughout.
    method = (Image.Resampling.LANCZOS if source else
              Image.Resampling.BOX if image.width > 376 or image.height > 220 else
              Image.Resampling.NEAREST)
    preview = ImageOps.contain(image.convert('RGB'), (376, 220), method=method)
    sheet.paste(preview, (x + (376 - preview.width) // 2, y + 34 + (220 - preview.height) // 2))


def generate_samples(output: Path, *, replace: bool = False) -> None:
    panels = selections()
    managed = {'README.md', 'manifest.json', *LEGACY_SHEETS, *(p.filename for p in panels)}
    if output.exists():
        if not replace:
            raise ValueError('sample directory exists; use --replace to refresh the curated panels')
        if not output.is_dir() or any(p.name not in managed or not p.is_file() or p.is_symlink() for p in output.iterdir()):
            raise ValueError('sample directory contains unmanaged files; choose a new directory')
    records = json.loads(CATALOG.read_text(encoding='utf-8'))
    sources = {r['id']: r for r in records if r['public']}
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 3, 'panel_width': PANEL_WIDTH, 'columns': 2, 'comparisons': []}
    lines = ['# Sample mode comparisons', '',
             'Ten lossless PNG panels, **800 pixels wide**, arranged in two columns.',
             'Panels grow vertically to show more modes, with at most ten rows each.',
             'FS means Floyd–Steinberg. No dither, FS and Bayer are compared throughout.',
             'CPC covers modes 0/1/2; BBC covers 0/1/2/4/5; Amiga includes indexed/EHB/HAM.',
             'C64 includes neutral and greener saturation/hue/channel-gain examples.',
             'Teletext uses the colourful macaws for bitmap and mosaic comparisons.', '',
             'Mega Drive adds four-bank tiles; SNES compares eight-bank tiles and 256-colour indexed output.', '',
             'Converted thumbnails use area averaging when reduced to limit moiré and banding;',
             'enlarged conversions retain nearest-neighbour scaling for crisp pixels.',
             'They are thumbnails; inspect regenerated individual PNGs for exact pixel patterns.',
             'Source thumbnails use smooth resizing. Palette counts in the manifest refer to',
             'the original conversions, not filtered thumbnails, labels, source photos or whole panels.', '',
             'Source credits and rights: [reference images](../README.md).', '',
             'Refresh these panels from the project root:', '', '```bash',
             'python examples/generate_samples.py --replace', '```', '',
             'This defaults to `samples/comparisons`. Use `--output-dir /path/to/new-samples`',
             'for a separate set. Only known sample files are replaced; other files are refused.',
             'Individual conversions are temporary and cleaned up automatically.', '',
             'The manifest records source/panel checksums, settings, PNG checksums and colour counts.',
             'Commands use `/path/to/image.jpg`; substitute the indicated source and choose an output',
             'directory. Commands are single-line POSIX syntax; the shown options also work in PowerShell.', '']
    with tempfile.TemporaryDirectory(prefix='.retroimg-samples-', dir=output.parent) as temporary:
        stage = Path(temporary)
        renders = stage / 'renders'
        renders.mkdir()
        for panel in panels:
            source = dict(sources[panel.source])
            path = BUNDLED_SOURCES / source['file']
            source['sha256'] = sha256(path.read_bytes()).hexdigest()
            size = panel_size(panel)
            sheet = Image.new('RGB', size, '#202020')
            draw = ImageDraw.Draw(sheet)
            draw.text((16, 12), panel.title, fill='white', font=_font(18))
            if panel.show_source:
                with Image.open(path) as original:
                    _tile(sheet, 0, 'Source photograph', original, source=True)
            lines.extend([f'## {panel.title}', '',
                          f'Source: [{source["file"]}](../sources/{source["file"]}). '
                          f'Credit: {source["credit"]}. {source["rights"]}', '',
                          f'![{panel.title}]({panel.filename})', '', '<details>',
                          '<summary>Settings and reproduction commands</summary>', ''])
            variants = []
            for index, variant in enumerate(panel.variants):
                options = dict(variant.options, fit=source['fit'])
                rendered_path = renders / f'{panel.source}-{panel.family}-{variant.slug}.png'
                indexed = convert_file(path, rendered_path, **options)
                check_constraints(indexed, options)
                with Image.open(rendered_path) as rendered:
                    if rendered.size != variant.size:
                        raise AssertionError(f'unexpected preview size: {rendered_path}')
                    colours = rendered.convert('RGB').getcolors(maxcolors=len(indexed.palette.colours))
                    allowed = set(indexed.palette.rgb_values())
                    if colours is None or any(rgb not in allowed for _, rgb in colours):
                        raise AssertionError(f'off-palette conversion: {rendered_path}')
                    _tile(sheet, index + int(panel.show_source), variant.label, rendered)
                command = command_for(source, rendered_path.name, options).replace(
                    f'/path/to/{source["file"]}', '/path/to/image.jpg')
                variants.append(dict(label=variant.label, settings=options, command=command,
                                     preview_size=list(variant.size), logical_size=[indexed.width, indexed.height],
                                     colours_used=len(colours), palette=indexed.palette.name,
                                     sha256=sha256(rendered_path.read_bytes()).hexdigest()))
                lines.extend([f'### {variant.label}', '', '```bash', command, '```', ''])
            draw.text((16, size[1] - 20), f'{size[0]} x {size[1]} | Source credits and exact settings: README.md',
                      fill='#cccccc', font=_font(12))
            sheet.save(stage / panel.filename)
            manifest['comparisons'].append(dict(
                source=source, family=panel.family, title=panel.title, sheet=panel.filename, panel_size=list(size),
                show_source=panel.show_source, sha256=sha256((stage / panel.filename).read_bytes()).hexdigest(), variants=variants))
            lines.extend(['</details>', ''])
            print(f'{panel.filename}: {len(variants)} conversions checked', flush=True)
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (stage / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
        output.mkdir(exist_ok=True)
        for path in stage.iterdir():
            if path.is_file():
                os.replace(path, output / path.name)
        for name in LEGACY_SHEETS:
            (output / name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT, help='sample directory (default: samples/comparisons)')
    parser.add_argument('--replace', action='store_true', help='refresh known sample files in an existing directory')
    args = parser.parse_args(argv)
    try:
        generate_samples(args.output_dir, replace=args.replace)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
