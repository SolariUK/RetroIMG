from PIL import Image
import pytest

from retroimg.pixelate import pixelate_image


def test_pixelation_averages_blocks_without_modifying_source():
    source = Image.new('RGB', (8, 8))
    source.putdata([(255, 255, 255) if (x + y) % 2 else (0, 0, 0)
                    for y in range(8) for x in range(8)])
    original = source.tobytes()
    output = pixelate_image(source, 4)
    assert output.size == source.size
    assert output.getcolors() == [(64, (128, 128, 128))]
    assert source.tobytes() == original


def test_fixed_block_grid_preserves_partial_edges():
    source = Image.new('RGB', (10, 9))
    source.paste((255, 0, 0), (0, 0, 4, 8))
    source.paste((0, 255, 0), (4, 0, 8, 8))
    source.paste((0, 0, 255), (8, 0, 10, 8))
    source.paste((255, 255, 255), (0, 8, 10, 9))
    output = pixelate_image(source, 4)
    assert output.size == (10, 9)
    assert output.tobytes() == source.tobytes()


def test_block_size_one_is_neutral_and_larger_than_image_is_one_block():
    source = Image.new('RGB', (3, 2), (70, 140, 210))
    assert pixelate_image(source, 1).tobytes() == source.tobytes()
    assert pixelate_image(source, 16).getcolors() == [(6, (70, 140, 210))]


def test_generic_pixelation_retains_more_than_256_source_derived_colours():
    source = Image.new('RGB', (35, 33))
    source.putdata([(x * 6, y * 7, (x * 3 + y * 5) % 256) for y in range(33) for x in range(35)])
    assert pixelate_image(source, 1).tobytes() == source.tobytes()
    output = pixelate_image(source, 2)
    assert output.size == source.size
    assert len(output.getcolors(35 * 33)) > 256


def test_pixelate_cli_uses_original_dimensions_and_block_size(tmp_path, capsys):
    from retroimg.cli import main

    source = tmp_path / 'source.png'
    Image.new('RGB', (13, 11), (77, 131, 193)).save(source)
    output = tmp_path / 'pixelated.png'
    main(['pixelate', str(source), str(output), '--block-size', '4'])
    with Image.open(output) as result:
        assert result.size == (13, 11)
        assert result.getcolors() == [(143, (77, 131, 193))]
    assert 'block-size=4' in capsys.readouterr().out


def test_invalid_pixelate_cli_does_not_touch_output(tmp_path):
    from retroimg.cli import main

    output = tmp_path / 'output.png'
    output.write_bytes(b'keep')
    with pytest.raises(SystemExit) as exc:
        main(['pixelate', str(tmp_path / 'missing.png'), str(output), '--block-size=0'])
    assert exc.value.code == 2
    assert output.read_bytes() == b'keep'


@pytest.mark.parametrize('size', [0, -1, 1.5, True, None])
def test_invalid_block_sizes_are_rejected(size):
    with pytest.raises(ValueError, match='positive whole number'):
        pixelate_image(Image.new('RGB', (1, 1)), size)


def test_bundled_pixelation_examples_have_matching_hashes_commands_and_crops():
    from hashlib import sha256
    import json
    from pathlib import Path
    import shlex
    from retroimg.cli import build_parser

    root = Path(__file__).resolve().parents[1]
    directory = root / 'samples/pixelation'
    manifest = json.loads((directory / 'manifest.json').read_text())
    source = manifest['source']
    assert source['public']
    assert sha256((root / 'samples/sources' / source['file']).read_bytes()).hexdigest() == source['reference_sha256']
    assert {record['block_size'] for record in manifest['examples']} == {4, 8, 16}
    for record in manifest['examples']:
        assert sha256((directory / record['filename']).read_bytes()).hexdigest() == record['sha256']
        assert sha256((directory / record['crop']).read_bytes()).hexdigest() == record['crop_sha256']
        args = build_parser().parse_args(shlex.split(record['command'])[1:])
        assert args.command == 'pixelate' and args.block_size == record['block_size']
        with Image.open(directory / record['filename']) as full, Image.open(directory / record['crop']) as crop:
            assert full.size == tuple(source['reference_size'])
            assert full.crop(record['crop_box']).tobytes() == crop.tobytes()
