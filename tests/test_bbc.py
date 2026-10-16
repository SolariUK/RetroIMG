"""BBC steady-colour rules, logical mapping and public CLI integration."""
from itertools import combinations
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.convert import convert_file
from retroimg.model import IndexedImage, Palette
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile
from retroimg.quantize import colour_distance, quantize
from retroimg.render import render_indexed
from retroimg.targets.bbc import BBCImage, optimise_bbc, rasterize_bbc

BBC = get_palette('bbc')
VALUES = BBC.rgb_values()
MODES = ((0, 640, .5, 2), (1, 320, 1, 4), (2, 160, 2, 8),
         (4, 320, 1, 2), (5, 160, 2, 4))


def palette_source():
    image = Image.new('RGB', (8, 2))
    image.putdata(VALUES * 2)
    return image


def test_physical_colour_number_order():
    assert [colour.name for colour in BBC.colours] == [
        'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
    assert list(VALUES) == [(255 * (i & 1), 255 * ((i >> 1) & 1), 255 * ((i >> 2) & 1)) for i in range(8)]
    assert BBC.name != get_palette('teletext').name


def test_logical_mapping_is_separate_from_physical_colour_numbers():
    screen = BBCImage(2, 1, 4, (2, 1), ((0, 1),))
    assert rasterize_bbc(screen) == IndexedImage(2, 1, BBC, ((2, 1),))
    # Even two-colour modes can map both slots to non-default colours.
    source = Image.new('RGB', (2, 1))
    source.putdata([VALUES[1], VALUES[2]])
    assert render_indexed(rasterize_bbc(optimise_bbc(source, mode=4))).tobytes() == source.tobytes()


@pytest.mark.parametrize('mode,width,aspect,limit', MODES)
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_screen_wide_limits_and_determinism(mode, width, aspect, limit, dither):
    source = palette_source()
    screen = optimise_bbc(source, mode=mode, dither=dither)
    assert screen == optimise_bbc(source, mode=mode, dither=dither)
    assert 1 <= len(screen.colours) <= limit
    assert screen.colours == optimise_bbc(source, mode=mode).colours
    raster = rasterize_bbc(screen)
    raster.validate()
    used = {pixel for row in raster.pixels for pixel in row}
    assert used <= set(screen.colours)
    assert len(used) <= limit
    selected = Palette('selected', tuple(BBC.colours[i] for i in screen.colours))
    assert screen.pixels == quantize(source, selected, dither).pixels


@pytest.mark.parametrize('mode', [1, 5])
def test_known_four_colours_survive_exactly(mode):
    source = Image.new('RGB', (4, 1))
    source.putdata([VALUES[i] for i in (1, 2, 4, 6)])
    screen = optimise_bbc(source, mode=mode)
    assert screen.colours == (1, 2, 4, 6)
    assert render_indexed(rasterize_bbc(screen)).tobytes() == source.tobytes()


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_mode2_uses_all_eight_steady_colours_and_matches_bitmap(dither):
    source = palette_source()
    screen = optimise_bbc(source, mode=2, dither=dither)
    assert screen.colours == tuple(range(8))
    assert rasterize_bbc(screen) == quantize(source, BBC, dither)


def test_two_colour_fit_matches_exhaustive_source_rgb_oracle():
    samples = [(98, 45, 180), (120, 230, 90), (120, 230, 90), (15, 22, 100), (240, 150, 60)]
    source = Image.new('RGB', (5, 1))
    source.putdata(samples)
    screen = optimise_bbc(source, mode=0)
    def error(indices):
        return sum(min(colour_distance(rgb, VALUES[i]) for i in indices) for rgb in samples)
    assert error(screen.colours) == min(error(pair) for pair in combinations(range(8), 2))


@pytest.mark.parametrize('mode,width,aspect,limit', MODES)
def test_geometry_and_matching_preview_sizes(tmp_path, mode, width, aspect, limit):
    profile = get_profile(f'bbc-mode{mode}')
    assert (profile.geometry.width, profile.geometry.height, profile.geometry.pixel_aspect) == (width, 256, aspect)
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    Image.new('RGB', (32, 25), VALUES[2]).save(src)
    indexed = convert_file(src, dst, profile_name=profile.name, bbc_mode='constrained', scale=1 if mode == 0 else 2)
    assert indexed.pixels == ((2,) * width,) * 256
    with Image.open(dst) as preview:
        assert preview.size == (640, 512)


def test_mode0_preview_preserves_fine_columns():
    indexed = IndexedImage(640, 1, BBC, ((0, 7) * 320,))
    preview = render_indexed(indexed, pixel_aspect=.5)
    assert preview.size == (640, 2)
    for y in range(2):
        assert [preview.getpixel((x, y)) for x in range(640)] == [VALUES[i] for i in indexed.pixels[0]]


@pytest.mark.parametrize('mode', [0, 1, 2, 4, 5])
@pytest.mark.parametrize('palette_name', ['bbc', 'cpc'])
def test_bitmap_defaults_allow_unrestricted_colours_and_palette_swaps(tmp_path, mode, palette_name):
    palette = get_palette(palette_name)
    source = Image.new('RGB', (len(palette.colours), 1))
    source.putdata(palette.rgb_values())
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source.save(src)
    indexed = convert_file(src, dst, profile_name=f'bbc-mode{mode}', palette_name=palette_name,
                           width=source.width, height=1, fit='stretch', scale=1)
    assert indexed == quantize(source, palette)
    assert len(set(indexed.pixels[0])) == len(palette.colours)


@pytest.mark.parametrize('mode', [0, 1, 2, 4, 5])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_cli_adjustments_and_dithering(tmp_path, mode, dither):
    source = palette_source()
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source.save(src)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(src), str(dst),
                    '--profile', f'bbc-mode{mode}', '--bbc-mode', 'constrained',
                    '--width', '8', '--height', '2', '--fit', 'stretch', '--scale', '1',
                    '--dither', dither, '--hue-shift', '20', '--green-gain', '1.15'], check=True)
    expected = rasterize_bbc(optimise_bbc(adjust_colours(source, hue_shift=20, green_gain=1.15), mode=mode, dither=dither))
    with Image.open(dst) as preview:
        assert preview.tobytes() == render_indexed(expected, pixel_aspect=get_profile(f'bbc-mode{mode}').geometry.pixel_aspect).tobytes()


@pytest.mark.parametrize('changes,match', [
    (dict(mode=3), 'mode'), (dict(mode=6), 'mode'), (dict(mode=7), 'mode'),
    (dict(mode=True), 'mode'), (dict(mode=1.0), 'mode'),
    (dict(colours=()), 'count'), (dict(colours=(0, 1, 2)), 'count'),
    (dict(colours=(0, 8)), 'physical'), (dict(colours=(0, -1)), 'physical'),
    (dict(colours=(0, True)), 'physical'), (dict(colours=(0, 0)), 'unique'),
    (dict(pixels=((2, 0),)), 'logical'), (dict(pixels=((True, 0),)), 'logical'),
    (dict(pixels=()), 'grid'), (dict(width=0), 'positive'),
    (dict(palette=get_palette('teletext')), 'bbc palette'),
])
def test_invalid_models(changes, match):
    args = dict(width=2, height=1, mode=0, colours=(0, 7), pixels=((0, 1),))
    args.update(changes)
    with pytest.raises(ValueError, match=match):
        BBCImage(**args)


@pytest.mark.parametrize('kwargs,match', [
    (dict(bbc_mode='invalid'), 'unknown BBC'),
    (dict(bbc_mode='constrained'), 'only valid'),
    (dict(profile_name='bbc-mode0', bbc_mode='constrained', palette_name='cpc'), 'bbc palette'),
    (dict(profile_name='bbc-mode1', cpc_mode='constrained'), 'only valid'),
    (dict(profile_name='bbc-mode2', teletext_mode='mosaic'), 'only valid'),
    (dict(profile_name='bbc-mode4', spectrum_mode='attributes'), 'only valid'),
    (dict(profile_name='bbc-mode5', c64_mode='multicolour'), 'only valid'),
])
def test_invalid_options_leave_output_untouched(tmp_path, kwargs, match):
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    palette_source().save(src)
    dst.write_bytes(b'preserve existing output')
    with pytest.raises(ValueError, match=match):
        convert_file(src, dst, **kwargs)
    assert dst.read_bytes() == b'preserve existing output'


def test_invalid_optimizer_options():
    for kwargs in (dict(mode=7), dict(dither='invalid'), dict(palette=get_palette('cpc'))):
        with pytest.raises(ValueError):
            optimise_bbc(palette_source(), **kwargs)
