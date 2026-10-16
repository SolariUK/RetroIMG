"""Generate a small, credited selection of comparison sheets for the repository."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

if __package__:
    from .generate_gallery import BUNDLED_SOURCES, generate
else:
    from generate_gallery import BUNDLED_SOURCES, generate


SELECTION = (
    ('macaws', 'cpc'),
    ('portrait-colour', 'teletext'),
    ('lush-landscape', 'c64'),
)


def generate_samples(output: Path) -> None:
    if output.exists():
        raise ValueError('sample sheets require a new output directory')
    output.mkdir(parents=True)
    manifest = {'version': 1, 'comparisons': []}
    lines = ['# Selected comparison sheets', '',
             'Each sheet compares no dithering, Floyd–Steinberg and Bayer 2×2/4×4/8×8',
             'with identical geometry, palette limits and neutral colour adjustments.',
             'These are visual PNG previews of hardware-inspired constraints.', '',
             'Only the labelled JPEG sheets are stored here. JPEG compression can add',
             'colours; use the regenerated PNGs for exact palette/count inspection.',
             'Source images and detailed rights records are in [samples/README.md](../README.md).', '',
             'Regenerate from the project root into a new directory:', '', '```bash',
             'python examples/generate_samples.py --output-dir /path/to/new-sample-sheets',
             '```', '',
             '`manifest.json` records source and sheet checksums, conversion settings,',
             'PNG checksums, colour counts and reproduction commands. Individual PNGs',
             'are generated temporarily and omitted from this small published selection.', '',
             'Commands below use `/path/to/image.jpg`; run them in a temporary output',
             'directory with the indicated bundled source. They print POSIX shell syntax;',
             'PowerShell users can enter the same options on one line.', '']
    with tempfile.TemporaryDirectory(prefix='retroimg-samples-') as temporary:
        for source_id, family in SELECTION:
            gallery = Path(temporary) / f'{source_id}-{family}'
            result = generate(BUNDLED_SOURCES, gallery, (family,), public_only=True,
                              dither_comparison=True, source_ids=[source_id])
            source = result['sources'][0]
            filename = f'{source_id}-{family}.jpg'
            shutil.copyfile(gallery / source_id / family / 'comparison.jpg', output / filename)
            variants = []
            lines.extend([f'## {source["title"]} — {family}', '',
                          f'Credit: {source["credit"]}. {source["rights"]}', '',
                          f'![{source["title"]}: {family} dithering comparison]({filename})', ''])
            for entry in result['outputs']:
                name = Path(entry['png']).name
                command = entry['command'].replace(f'/path/to/{source["file"]}', '/path/to/image.jpg').replace(entry['png'], name)
                variants.append({key: value for key, value in entry.items()
                                 if key not in {'elapsed_seconds', 'png', 'command'}} | {'command': command})
                lines.extend([f'### {entry["label"]}', '', '```bash', command, '```', ''])
            manifest['comparisons'].append(dict(
                source=source, family=family, sheet=filename,
                sha256=sha256((output / filename).read_bytes()).hexdigest(), variants=variants))
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    (output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='new directory for three curated sheets and provenance')
    args = parser.parse_args(argv)
    try:
        generate_samples(args.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
