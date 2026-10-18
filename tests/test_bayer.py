from itertools import product
import subprocess
import sys

from PIL import Image
import pytest

from examples.generate_gallery import check_constraints
from retroimg.constraints.cells import quantize_cells
from retroimg.convert import convert_file
from retroimg.model import Colour, Palette
from retroimg.ordered import bayer_matrix, bayer_threshold, ordered_lookup, ordered_pair
from retroimg.palettes import get_palette
from retroimg.quantize import quantize
from retroimg.targets.amiga import optimise_ham, rasterize_ham

BW = Palette('bw', (Colour('black', (0, 0, 0)), Colour('white', (255, 255, 255))))


@pytest.mark.parametrize('size', [2, 4, 8])
@pytest.mark.parametrize('name', ['atari2600-pal', 'ega-default'])
def test_cached_palette_choices_keep_integer_and_fractional_samples(size, name):
    palette = get_palette(name)
    lookup = ordered_lookup(palette, bayer_size=size)
    for sample in range(40):
        rgb = (sample * 19 % 256, sample * 37 % 256, sample * 71 % 256)
        for source in (rgb, tuple(value + .125 for value in rgb)):
            a, b, fraction = ordered_pair(source, palette.rgb_values(), bayer_size=size)
            for x, y in product(range(size), repeat=2):
                threshold = bayer_threshold(x, y, size)
                assert lookup(source, threshold) == (b if threshold < fraction else a)


def test_known_bayer_matrices():
    assert bayer_matrix(2) == ((0, 2), (3, 1))
    assert bayer_matrix(4) == ((0, 8, 2, 10), (12, 4, 14, 6),
                              (3, 11, 1, 9), (15, 7, 13, 5))


@pytest.mark.parametrize('size', [2, 4, 8])
def test_ranks_and_centered_thresholds(size):
    assert sorted(value for row in bayer_matrix(size) for value in row) == list(range(size * size))
    assert sum(bayer_threshold(x, y, size) for x, y in product(range(size), repeat=2)) / size**2 == 0.5
    assert bayer_threshold(-1, -1, size) == bayer_threshold(size - 1, size - 1, size)


@pytest.mark.parametrize('size', [2, 4, 8])
@pytest.mark.parametrize('level', [0, 32, 64, 96, 127, 128, 160, 192, 224, 255])
def test_binary_ramp_has_expected_coverage_and_orientation(size, level):
    source = Image.new('RGB', (size * 2, size * 2), (level,) * 3)
    result = quantize(source, BW, 'bayer', bayer_size=size)
    expected = tuple(tuple(int(bayer_threshold(x, y, size) < level / 255)
                           for x in range(size * 2)) for y in range(size * 2))
    assert result.pixels == expected
    assert abs(sum(sum(row[:size]) for row in result.pixels[:size]) / size**2 - level / 255) <= 0.5 / size**2


def test_palette_pair_uses_weighted_projection_and_preserves_exact_colours():
    values = ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 0, 0))
    a, b, fraction = ordered_pair((63.75, 191.25, 0), values)
    assert (a, b) == (0, 1)
    assert fraction == pytest.approx(0.75)
    source = Image.new('RGB', (8, 8), values[2])
    palette = Palette('rgb', tuple(Colour(str(i), value) for i, value in enumerate(values)))
    assert quantize(source, palette, 'bayer').pixels == ((2,) * 8,) * 8


@pytest.mark.parametrize('size', [2, 4, 8])
@pytest.mark.parametrize('source,values,forbidden', [
    # Pale background: a near-black partner used to leave isolated dark dots.
    ((201, 210, 224), ((0, 0, 36), (182, 182, 182), (219, 219, 219)), (0, 0, 36)),
    # Blue feathers: a distant white partner used to leave bright pinpricks.
    ((46, 83, 116), ((36, 73, 109), (73, 109, 146), (255, 255, 255)), (255, 255, 255)),
])
def test_nearby_colours_avoid_isolated_extreme_partners(size, source, values, forbidden):
    palette = Palette('regression', tuple(Colour(str(i), value) for i, value in enumerate(values)))
    result = quantize(Image.new('RGB', (size, size), source), palette, 'bayer', bayer_size=size)
    assert forbidden not in {palette.colours[index].rgb for row in result.pixels for index in row}


@pytest.mark.parametrize('size', [2, 4, 8])
def test_adjacent_shade_ramps_keep_coverage_at_each_matrix_size(size):
    values = ((0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255))
    palette = Palette('shades', tuple(Colour(str(i), value) for i, value in enumerate(values)))
    for level in range(256):
        result = quantize(Image.new('RGB', (size, size), (level,) * 3), palette, 'bayer', bayer_size=size)
        samples = [values[index][0] for row in result.pixels for index in row]
        assert max(samples) - min(samples) <= 85
        assert abs(sum(samples) / len(samples) - level) <= 85 / (2 * size * size) + 1e-9


def test_duplicate_colours_do_not_change_mixing_contrast_or_phase():
    values = ((0, 0, 36), (182, 182, 182), (219, 219, 219))
    base = Palette('base', tuple(Colour(str(i), rgb) for i, rgb in enumerate(values)))
    repeated = Palette('repeated', base.colours + base.colours)
    source = Image.new('RGB', (8, 8), (201, 210, 224))
    first = quantize(source, base, 'bayer')
    second = quantize(source, repeated, 'bayer')
    assert first.pixels == second.pixels


@pytest.mark.parametrize('size', [2, 4, 8])
def test_full_rgb_grid_rounding_is_ordered_per_channel(size):
    palette = get_palette('amiga')
    source = Image.new('RGB', (size, size), (127, 60, 33))
    result = quantize(source, palette, 'bayer', bayer_size=size)
    for y, row in enumerate(result.pixels):
        for x, index in enumerate(row):
            expected = []
            for value in (127, 60, 33):
                lower, remainder = divmod(value, 17)
                expected.append((lower + int(bayer_threshold(x, y, size) < remainder / 17)) * 17)
            assert palette.colours[index].rgb == tuple(expected)


@pytest.mark.parametrize('size', [2, 4, 8])
def test_cell_boundaries_keep_global_matrix_phase(size):
    source = Image.new('RGB', (8, 12), (96,) * 3)
    full = quantize(source, BW, 'bayer', bayer_size=size)
    cells = quantize_cells(source, BW, cell_width=2, cell_height=3,
                           dither='bayer', bayer_size=size, allowed_pairs=((0, 1),))
    assert cells == full


CASES = [
    ('teletext', dict(teletext_mode='mosaic'), 16, 24),
    ('spectrum', dict(spectrum_mode='attributes'), 16, 8),
    ('c64-multicolour', dict(c64_mode='multicolour'), 16, 8),
    *[(f'cpc-mode{mode}', dict(cpc_mode='constrained'), 16, 8) for mode in range(3)],
    *[(f'bbc-mode{mode}', dict(bbc_mode='constrained'), 16, 8) for mode in (0, 1, 2, 4, 5)],
    ('amiga-lores', dict(amiga_mode='constrained', colours=32), 16, 8),
    ('amiga-hires', dict(amiga_mode='constrained', colours=16), 16, 8),
    ('amiga-lores', dict(amiga_mode='ehb'), 16, 8),
    ('amiga-lores', dict(amiga_mode='ham'), 16, 8),
    *[('atari2600-ntsc', dict(atari_mode=mode, atari_row_height=3), 160, 8)
      for mode in ('playfield', 'repeat', 'mirror')],
    ('atari2600-pal', dict(atari_mode='playfield'), 160, 8),
]


@pytest.mark.parametrize('profile,options,width,height', CASES)
@pytest.mark.parametrize('size', [2, 4, 8])
def test_all_constrained_adapters_accept_bayer_and_preserve_constraints(tmp_path, profile, options, width, height, size):
    source = Image.new('RGB', (width, height))
    source.putdata([(x * 31 % 256, y * 59 % 256, (x * 7 + y * 19) % 256)
                    for y in range(height) for x in range(width)])
    path, output = tmp_path / 'source.png', tmp_path / 'output.png'
    source.save(path)
    result = convert_file(path, output, profile_name=profile, width=width, height=height,
                          fit='stretch', scale=1, dither='bayer', bayer_size=size, **options)
    check_constraints(result, dict(options, profile_name=profile))
    assert result == convert_file(path, output, profile_name=profile, width=width, height=height,
                                  fit='stretch', scale=1, dither='bayer', bayer_size=size, **options)


@pytest.mark.parametrize('size', [2, 4, 8])
def test_ham_ordered_choice_retains_legal_codes_and_row_resets(size):
    source = Image.new('RGB', (8, 8), (8,) * 3)
    frame = optimise_ham(source, dither='bayer', bayer_size=size)
    raster = rasterize_ham(frame)
    decoded = []
    for row in frame.codes:
        previous = frame.registers[0]
        pixels = []
        for code in row:
            assert 0 <= code < 64
            op, value = divmod(code, 16)
            if op == 0:
                previous = frame.registers[value]
            elif op == 1:
                previous = (previous & 0xff0) | value
            elif op == 2:
                previous = (previous & 0x0ff) | (value << 8)
            else:
                previous = (previous & 0xf0f) | (value << 4)
            pixels.append(previous)
        decoded.append(tuple(pixels))
    assert raster.pixels == tuple(decoded)
    assert len(set(pixel for row in raster.pixels for pixel in row)) > 1
    assert frame.registers == optimise_ham(source).registers
    if size < 8:
        assert frame.codes[0] == frame.codes[size]


@pytest.mark.parametrize('kwargs,match', [
    (dict(dither='bayer', bayer_size=3), 'size'),
    (dict(dither='bayer', bayer_size=True), 'size'),
    (dict(bayer_size=4), 'requires'),
    (dict(dither='floyd-steinberg', bayer_size=4), 'requires'),
])
def test_invalid_options_preserve_output(tmp_path, kwargs, match):
    source, output = tmp_path / 'input.png', tmp_path / 'output.png'
    Image.new('RGB', (8, 8)).save(source)
    output.write_bytes(b'keep')
    with pytest.raises(ValueError, match=match):
        convert_file(source, output, **kwargs)
    assert output.read_bytes() == b'keep'


def test_cli_and_default_matrix_size(tmp_path):
    source, output = tmp_path / 'input.png', tmp_path / 'output.png'
    Image.new('RGB', (8, 8), (96,) * 3).save(source)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(source), str(output),
                    '--dither', 'bayer', '--bayer-size', '8', '--width', '8', '--height', '8',
                    '--scale', '1'], check=True, capture_output=True)
    assert output.is_file()
    implicit = convert_file(source, output, width=8, height=8, scale=1, dither='bayer')
    explicit = convert_file(source, output, width=8, height=8, scale=1, dither='bayer', bayer_size=4)
    assert implicit == explicit


@pytest.mark.parametrize('size', [2, 4, 8])
def test_atari_bayer_phase_advances_with_logical_band(size):
    from retroimg.targets.atari2600 import optimise_atari_playfield, rasterize_atari_playfield
    source = Image.new('RGB', (160, 8))
    source.putdata([(0, 0, 0) if x < 64 else (236, 236, 236) if x >= 96 else (96, 96, 96)
                    for y in range(8) for x in range(160)])
    frame = optimise_atari_playfield(source, dither='bayer', bayer_size=size)
    assert frame.rows[0].pattern != frame.rows[1].pattern
    result = rasterize_atari_playfield(frame)
    assert result.pixels[0] == result.pixels[1]
    assert result.pixels[2] == result.pixels[3]


@pytest.mark.parametrize('size', [0, 3, 16, 4.0, True])
def test_invalid_matrix_sizes(size):
    with pytest.raises(ValueError, match='size'):
        bayer_matrix(size)
