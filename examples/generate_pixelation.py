"""Generate a small set of original-colour pixelation examples and detail crops."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from retroimg.pixelate import pixelate_file

ROOT = Path(__file__).resolve().parents[1]
BLOCK_SIZES = (4, 8, 16)
CROP = (192, 128, 448, 384)


def generate(output: Path, *, replace: bool = False) -> None:
    names = {'README.md', 'manifest.json',
             *(f'macaws-block{size}{suffix}.png' for size in BLOCK_SIZES for suffix in ('', '-crop'))}
    if output.exists():
        if not replace:
            raise ValueError('output directory exists; use --replace to refresh known examples')
        if not output.is_dir() or any(p.name not in names or not p.is_file() or p.is_symlink() for p in output.iterdir()):
            raise ValueError('output directory contains unmanaged files')
    source = next(s for s in json.loads((ROOT / 'examples/sources.json').read_text()) if s['id'] == 'macaws')
    path = ROOT / 'samples/sources' / source['file']
    if not source['public'] or sha256(path.read_bytes()).hexdigest() != source['reference_sha256']:
        raise ValueError('expected the catalogued public reference image')
    lines = ['# Original-colour pixelation', '',
             'The source image retains its 750×536 dimensions and uses RGB colour averages,',
             'with no hardware palette, dithering or colour-count limit. Block size is in',
             'source pixels. Each detail crop is an unscaled 256×256 section of the full PNG.',
             'Open the PNGs at 100% to compare the block sizes.', '',
             f'Source: [{source["file"]}](../sources/{source["file"]}).',
             f'Credit: {source["credit"]}. {source["rights"]}',
             'See [pixelation documentation](../../docs/pixelation.md).', '']
    records = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.retroimg-pixelation-', dir=output.parent) as temporary:
        stage = Path(temporary)
        for size in BLOCK_SIZES:
            filename = f'macaws-block{size}.png'
            crop_name = f'macaws-block{size}-crop.png'
            image = pixelate_file(path, stage / filename, block_size=size)
            image.crop(CROP).save(stage / crop_name)
            command = f'retroimg pixelate /path/to/image.jpg {filename} --block-size {size}'
            records.append(dict(filename=filename, size=list(image.size), block_size=size,
                                crop=crop_name, crop_box=list(CROP), command=command,
                                sha256=sha256((stage / filename).read_bytes()).hexdigest(),
                                crop_sha256=sha256((stage / crop_name).read_bytes()).hexdigest()))
            image.close()
            lines.extend([f'## {size}×{size} blocks', '',
                          f'[Open full-size image]({filename}) · [Open detail crop]({crop_name})', '',
                          f'![{size} by {size} pixel blocks, unscaled detail]({crop_name})', '',
                          '```bash', command, '```', ''])
        lines.extend(['Refresh from the project root:', '', '```bash',
                      'python examples/generate_pixelation.py --replace', '```', ''])
        (stage / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
        (stage / 'manifest.json').write_text(json.dumps(dict(version=1, source=source, examples=records), indent=2)
                                              + '\n', encoding='utf-8')
        output.mkdir(exist_ok=True)
        for file in stage.iterdir():
            os.replace(file, output / file.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'samples/pixelation')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    try:
        generate(args.output_dir, replace=args.replace)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
