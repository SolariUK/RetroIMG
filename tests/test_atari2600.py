from itertools import combinations_with_replacement

from PIL import Image
import pytest

from retroimg.constraints.binary_groups import fit_binary_groups
from retroimg.convert import convert_file
from retroimg.conversion_modes import get_profile_quantizer
from retroimg.model import Colour, Palette
from retroimg.palettes import get_palette
from retroimg.palettes.atari import ATARI_NTSC, ATARI_PAL
from retroimg.profiles import get_profile
from retroimg.quantize import colour_distance
from retroimg.targets.atari2600 import (
    AtariPlayfield, AtariPlayfieldRow, optimise_atari_playfield, rasterize_atari_playfield,
)


@pytest.mark.parametrize('standard,height,unique', [('ntsc', 192, 128), ('pal', 228, 104)])
def test_palettes_and_geometry(standard, height, unique):
    palette = get_palette(f'atari2600-{standard}')
    assert len(palette.colours) == 128
    assert len(set(palette.rgb_values())) == unique
    assert [colour.name for colour in palette.colours] == [f'tia-{code:02x}' for code in range(0, 256, 2)]
    assert palette.colours[0].rgb == (0, 0, 0)
    assert palette.colours[7].rgb == (236, 236, 236)
    geometry = get_profile(f'atari2600-{standard}').geometry
    assert (geometry.width, geometry.height) == (160, height)
    assert geometry.width * geometry.pixel_aspect / geometry.height == pytest.approx(4 / 3)
    if standard == 'pal':
        for hue in (1, 14, 15):
            assert palette.rgb_values()[hue * 8:(hue + 1) * 8] == palette.rgb_values()[:8]


def test_group_fitter_matches_independent_exhaustive_sample_oracle():
    palette = Palette('test', tuple(Colour(str(i), rgb) for i, rgb in enumerate(
        ((0, 0, 0), (255, 255, 255), (190, 30, 20), (20, 170, 40), (0, 0, 0)))))
    groups = (((210, 30, 0), (0, 140, 90)), ((255, 255, 255),),
              ((10, 0, 20),) * 3, ((110, 80, 20), (80, 100, 90)))
    values = palette.rgb_values()
    def error(pair):
        return sum(min(sum(colour_distance(sample, values[i]) for sample in group)
                       for i in pair) for group in groups)
    expected = min(combinations_with_replacement(range(len(values)), 2), key=error)
    pair, means = fit_binary_groups(groups, palette)
    assert pair == expected
    assert means[0] == (105, 85, 45)
    assert error(pair) == min(map(error, combinations_with_replacement(range(len(values)), 2)))


@pytest.mark.parametrize('groups,palette', [
    ((), ATARI_NTSC), (((),), ATARI_NTSC), ((((0, 0, 0),),), Palette('empty', ())),
])
def test_group_fitter_rejects_empty_inputs(groups, palette):
    with pytest.raises(ValueError, match='non-empty'):
        fit_binary_groups(groups, palette)


@pytest.mark.parametrize('mode,count', [('playfield', 40), ('repeat', 20), ('mirror', 20)])
def test_known_patterns_and_colour_codes(mode, count):
    pattern = 1 | (1 << (count - 1))
    row = AtariPlayfieldRow(0x00, 0x9e, pattern)
    frame = AtariPlayfield(3, 2, mode, (row, AtariPlayfieldRow(0x22, 0x22, 0)), ATARI_PAL)
    raster = rasterize_atari_playfield(frame)
    assert raster.width == 160 and raster.height == 3
    assert raster.pixels[0] == raster.pixels[1]
    assert raster.pixels[0][:4] == (0x4f,) * 4
    assert raster.pixels[0][4:8] == (0,) * 4
    assert raster.pixels[2] == (0x11,) * 160
    if mode == 'repeat':
        assert raster.pixels[0][:80] == raster.pixels[0][80:]
    if mode == 'mirror':
        assert raster.pixels[0][:80] == raster.pixels[0][80:][::-1]


@pytest.mark.parametrize('mode', ['playfield', 'repeat', 'mirror'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_fit_exact_two_colour_pattern_and_band_boundaries(mode, dither):
    pattern = sum(1 << bit for bit in range(20) if bit % 3 == 0)
    original = AtariPlayfield(3, 2, mode, (
        AtariPlayfieldRow(0, 14, pattern), AtariPlayfieldRow(0, 14, 0)), ATARI_NTSC)
    raster = rasterize_atari_playfield(original)
    source = Image.new('RGB', (160, 3))
    source.putdata([ATARI_NTSC.colours[i].rgb for row in raster.pixels for i in row])
    fitted = optimise_atari_playfield(source, dither=dither, mode=mode)
    assert rasterize_atari_playfield(fitted).pixels == raster.pixels
    assert fitted == optimise_atari_playfield(source, dither=dither, mode=mode)
    assert fitted.rows[-1].pattern == 0  # No diffusion into the next band.


@pytest.mark.parametrize('mode', ['playfield', 'repeat', 'mirror'])
def test_undithered_fit_is_minimum_error_against_full_rgb_source(mode):
    source = Image.new('RGB', (160, 1))
    source.putdata([(x * 13 % 256, x * 37 % 256, x * 71 % 256) for x in range(160)])
    frame = optimise_atari_playfield(source, mode=mode, row_height=1)
    def selector(x):
        block = x // 4
        return block if block < 20 or mode == 'playfield' else (block - 20 if mode == 'repeat' else 39 - block)
    groups = [[] for _ in range(40 if mode == 'playfield' else 20)]
    for x in range(160):
        groups[selector(x)].append(source.getpixel((x, 0)))
    # Direct evaluation per group and candidate colour, with no group means.
    costs = [[sum(colour_distance(sample, rgb) for sample in group)
              for rgb in ATARI_NTSC.rgb_values()] for group in groups]
    expected = min(sum(min(row[a], row[b]) for row in costs)
                   for a, b in combinations_with_replacement(range(128), 2))
    raster = rasterize_atari_playfield(frame)
    actual = sum(colour_distance(source.getpixel((x, 0)), ATARI_NTSC.colours[raster.pixels[0][x]].rgb)
                 for x in range(160))
    assert actual == expected


@pytest.mark.parametrize('kwargs', [dict(background=1), dict(foreground=256), dict(pattern=-1),
                                    dict(pattern=1 << 40), dict(background=True)])
def test_invalid_row_values(kwargs):
    with pytest.raises(ValueError):
        AtariPlayfieldRow(**(dict(background=0, foreground=14, pattern=0) | kwargs))


@pytest.mark.parametrize('kwargs', [dict(height=0), dict(row_height=0), dict(row_height=True),
    dict(rows=()), dict(mode='invalid'), dict(palette=get_palette('c64')),
    dict(mode='mirror', rows=(AtariPlayfieldRow(0, 14, 1 << 20),))])
def test_invalid_frames(kwargs):
    with pytest.raises(ValueError):
        AtariPlayfield(**(dict(height=1, row_height=2, mode='playfield',
                              rows=(AtariPlayfieldRow(0, 14, 0),)) | kwargs))


@pytest.mark.parametrize('standard', ['ntsc', 'pal'])
@pytest.mark.parametrize('mode', ['bitmap', 'playfield', 'repeat', 'mirror'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_conversion_integration(tmp_path, standard, mode, dither):
    source = tmp_path / 'source.png'
    Image.new('RGB', (160, 4), (70, 150, 90)).save(source)
    output = tmp_path / 'result.png'
    indexed = convert_file(source, output, profile_name=f'atari2600-{standard}',
        width=160, height=4, atari_mode=mode, dither=dither, scale=2,
        hue_shift=20, green_gain=1.15)
    indexed.validate()
    with Image.open(output) as preview:
        assert preview.size == (round(160 * 2 * get_profile(f'atari2600-{standard}').geometry.pixel_aspect), 8)
    if mode != 'bitmap':
        assert all(len(set(row)) <= 2 for row in indexed.pixels)


@pytest.mark.parametrize('kwargs,match', [
    (dict(atari_mode='playfield', width=80, height=2), 'width of 160'),
    (dict(atari_mode='playfield', palette_name='c64'), 'palette'),
    (dict(atari_mode='playfield', atari_row_height=0), 'positive'),
    (dict(atari_row_height=2), 'requires'),
    (dict(profile_name='teletext', atari_mode='mirror'), 'only valid'),
    (dict(atari_mode='playfield', colours=2), 'colours'),
])
def test_invalid_conversion_preserves_output(tmp_path, kwargs, match):
    source, output = tmp_path / 'source.png', tmp_path / 'output.png'
    Image.new('RGB', (2, 2)).save(source)
    output.write_bytes(b'keep')
    with pytest.raises(ValueError, match=match):
        convert_file(source, output, **(dict(profile_name='atari2600-ntsc', scale=1) | kwargs))
    assert output.read_bytes() == b'keep'


def test_row_height_option_dispatch_and_unrestricted_palette_mix(tmp_path):
    profile = get_profile('atari2600-pal')
    adapter = get_profile_quantizer(profile, atari_mode='mirror', atari_row_height=3)
    image = adapter(Image.new('RGB', (160, 5), 'red'), ATARI_PAL, 'none')
    assert image.pixels[0] == image.pixels[2]
    source = tmp_path / 'input.png'
    Image.new('RGB', (2, 2), 'red').save(source)
    result = convert_file(source, tmp_path / 'out.png', profile_name=profile.name,
                          palette_name='c64', width=4, height=4, scale=1)
    assert result.palette == get_palette('c64')


@pytest.mark.parametrize('mode,pixels,match', [
    ('playfield', ((0, 1) + (0,) * 158,) * 2, 'four-clock'),
    ('playfield', ((0,) * 160, (1,) * 160), 'band'),
    ('playfield', ((0,) * 4 + (1,) * 4 + (2,) * 152,) * 2, 'colour'),
    ('repeat', ((1,) * 4 + (0,) * 156,) * 2, 'repeated'),
    ('mirror', ((1,) * 4 + (0,) * 156,) * 2, 'mirrored'),
])
def test_gallery_checks_detect_playfield_violations(mode, pixels, match):
    from examples.generate_gallery import check_constraints
    from retroimg.model import IndexedImage
    with pytest.raises(AssertionError, match=match):
        check_constraints(IndexedImage(160, 2, ATARI_NTSC, pixels), dict(atari_mode=mode))


def test_cli_exposes_atari_options_and_converts(tmp_path):
    import subprocess
    import sys
    from retroimg.cli import build_parser
    args = build_parser().parse_args(['convert', 'in.jpg', 'out.png', '--profile', 'atari2600-pal',
                                      '--atari-mode', 'mirror', '--atari-row-height', '8'])
    assert (args.atari_mode, args.atari_row_height) == ('mirror', 8)
    source, output = tmp_path / 'source.png', tmp_path / 'output.png'
    Image.new('RGB', (160, 2), 'green').save(source)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(source), str(output),
        '--profile', 'atari2600-pal', '--atari-mode', 'repeat', '--atari-row-height', '8',
        '--width', '160', '--height', '2', '--scale', '1'], check=True, capture_output=True)
    with Image.open(output) as image:
        assert image.size == (304, 2)
