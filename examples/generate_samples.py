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

PANEL_SIZE = (800, 600)
DEFAULT_OUTPUT = BUNDLED_SOURCES.parent / 'comparisons'
LEGACY_SHEETS = {'macaws-cpc.jpg', 'portrait-colour-teletext.jpg', 'lush-landscape-c64.jpg'}


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
    """Seven representative modes and one controlled adjustment comparison."""
    panels = []
    for source, family, slug, title in (
        ('macaws', 'cpc', 'mode0-constrained', 'Amstrad CPC mode 0 / 16 screen colours'),
        ('portrait-colour', 'teletext', 'mosaic', 'Teletext / two colours per mosaic cell'),
        ('lush-landscape', 'c64', 'multicolour', 'Commodore 64 / multicolour cells'),
        ('lush-landscape', 'spectrum', 'attributes', 'ZX Spectrum / attribute cells'),
        ('macaws', 'bbc', 'mode2-constrained', 'BBC Micro mode 2 / eight steady colours'),
        ('portrait-colour', 'amiga', 'lores-32', 'Amiga PAL low resolution / 32 colours'),
        ('lush-landscape', 'atari2600', 'ntsc-playfield', 'Atari 2600 NTSC / independent playfield'),
    ):
        base = next(v for v in variants_for(family) if v.slug == slug)
        variants = []
        for dither, label in (('none', 'No dither'), ('floyd-steinberg', 'Floyd-Steinberg'), ('bayer', 'Bayer 4x4')):
            options = dict(base.options, dither=dither)
            if dither == 'bayer':
                options['bayer_size'] = 4
            variants.append(Variant(dither, label, options, base.size))
        panels.append(Panel(source, family, title, tuple(variants)))
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
    return tuple(panels)


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
    preview = ImageOps.contain(image.convert('RGB'), (376, 220),
                              method=Image.Resampling.LANCZOS if source else Image.Resampling.NEAREST)
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
    manifest = {'version': 2, 'panel_size': list(PANEL_SIZE), 'comparisons': []}
    lines = ['# Screen-sized sample comparisons', '',
             'Eight lossless PNG panels, each **800 x 600**, arranged in two columns.',
             'They cover all seven target families and one macaws colour-adjustment recipe.',
             'Each target panel shows the source, no dither, Floyd–Steinberg and Bayer 4x4.',
             'Representative modes keep this collection small; the target reference covers other modes.', '',
             'Converted previews are fitted with nearest-neighbour resizing for documentation.',
             'They are thumbnails; inspect regenerated individual PNGs for exact pixel patterns.',
             'Source thumbnails use smooth resizing. Palette counts in the manifest refer to',
             'the original conversions, not labels, source photos or whole panels.', '',
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
            sheet = Image.new('RGB', PANEL_SIZE, '#202020')
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
                    if colours is None or any(rgb not in set(indexed.palette.rgb_values()) for _, rgb in colours):
                        raise AssertionError(f'off-palette conversion: {rendered_path}')
                    _tile(sheet, index + int(panel.show_source), variant.label, rendered)
                command = command_for(source, rendered_path.name, options).replace(
                    f'/path/to/{source["file"]}', '/path/to/image.jpg')
                variants.append(dict(label=variant.label, settings=options, command=command,
                                     preview_size=list(variant.size), logical_size=[indexed.width, indexed.height],
                                     colours_used=len(colours), palette=indexed.palette.name,
                                     sha256=sha256(rendered_path.read_bytes()).hexdigest()))
                lines.extend([f'### {variant.label}', '', '```bash', command, '```', ''])
            draw.text((16, 580), '800 x 600 | Source credits and exact settings: README.md', fill='#cccccc', font=_font(12))
            sheet.save(stage / panel.filename)
            manifest['comparisons'].append(dict(
                source=source, family=panel.family, title=panel.title, sheet=panel.filename,
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
