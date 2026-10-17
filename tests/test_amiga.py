"""OCS/ECS precision, adaptive screen palettes and public conversion API."""
from itertools import product
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.colour_spaces import RGBGrid
from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.convert import convert_file
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.palettes import get_palette
from retroimg.palettes.amiga import AMIGA, AMIGA_RGB
from retroimg.profiles import get_profile
from retroimg.quantize import colour_distance, nearest_index, quantize
from retroimg.render import render_indexed
from retroimg.targets.amiga import AmigaImage, optimise_amiga, rasterize_amiga


def varied_source():
    source = Image.new('RGB', (16, 8))
    source.putdata([((i * 31) % 256, (i * 73) % 256, (i * 113) % 256) for i in range(128)])
    return source


def test_complete_palette_and_hardware_register_order():
    assert AMIGA.rgb_levels == tuple(range(0, 256, 17))
    assert len(AMIGA.colours) == len(set(AMIGA.rgb_values())) == 4096
    for value, colour in enumerate(AMIGA.colours):
        assert colour.rgb == (((value >> 8) & 15) * 17, ((value >> 4) & 15) * 17, (value & 15) * 17)
    assert AMIGA.colours[0xf80].rgb == (255, 136, 0)
    assert AMIGA.colours[0xfff].rgb == (255, 255, 255)


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_fast_grid_quantisation_matches_exhaustive_palette_search(dither):
    # Deliberately remove lookup metadata to use the brute-force path.
    flat = Palette('amiga', AMIGA.colours)
    source = varied_source().resize((8, 4))
    assert quantize(source, AMIGA, dither).pixels == quantize(source, flat, dither).pixels


def test_rgb_grid_float_ties_endpoints_and_nonuniform_levels():
    grid = RGBGrid((0, 17, 255))
    palette = grid.palette('custom')
    for rgb in product((-1, 0, 8.5, 17, 136, 254.5, 255, 260), repeat=3):
        oracle = min(range(27), key=lambda i: colour_distance(rgb, palette.colours[i].rgb))
        assert grid.nearest_index(rgb) == oracle
        assert grid.snap(rgb) == palette.colours[oracle].rgb
    assert nearest_index((8.5, 8.5, 8.5), AMIGA) == 0


@pytest.mark.parametrize('levels', [(), (17, 0), (0, 0, 255), (-1, 255), (0, 256), (0, True), (0, 17.0)])
def test_invalid_rgb_grids(levels):
    with pytest.raises(ValueError, match='RGB levels'):
        RGBGrid(levels)
    with pytest.raises(ValueError, match='RGB levels'):
        Palette('invalid', (), rgb_levels=levels)


def test_palette_rejects_incorrect_grid_metadata():
    with pytest.raises(ValueError, match='complete red-major'):
        Palette('invalid', (Colour('black', (0, 0, 0)),), rgb_levels=(0, 255))


def test_logical_register_mapping_and_bitplane_capacity():
    screen = AmigaImage(2, 1, 'lores', 1, (0xf80, 0x036), ((0, 1),))
    indexed = rasterize_amiga(screen)
    assert indexed.palette.rgb_values() == ((255, 136, 0), (0, 51, 102))
    assert indexed.pixels == ((0, 1),)
    assert screen.palette.rgb_levels is None  # A selected palette is not the full cube.


@pytest.mark.parametrize('resolution,counts', [('lores', (2, 4, 8, 16, 32)), ('hires', (2, 4, 8, 16))])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_legal_counts_precision_and_deterministic_screen_palettes(resolution, counts, dither):
    source = varied_source()
    for count in counts:
        screen = optimise_amiga(source, resolution=resolution, colours=count, dither=dither)
        assert screen == optimise_amiga(source, resolution=resolution, colours=count, dither=dither)
        assert screen.bitplanes == count.bit_length() - 1
        assert 1 <= len(screen.registers) <= count
        raster = rasterize_amiga(screen)
        raster.validate()
        assert len({p for row in raster.pixels for p in row}) <= count
        assert all(channel % 17 == 0 for rgb in raster.palette.rgb_values() for channel in rgb)
        assert screen.registers == optimise_amiga(source, resolution=resolution, colours=count).registers
        assert screen.pixels == quantize(source, screen.palette, dither).pixels


def test_known_register_colours_survive_exactly_when_they_fit():
    values = (0x000, 0xf80, 0x036, 0xfff)
    source = Image.new('RGB', (4, 2))
    source.putdata([AMIGA.colours[value].rgb for value in values * 2])
    screen = optimise_amiga(source, colours=4)
    assert screen.registers == tuple(sorted(values))
    assert render_indexed(rasterize_amiga(screen)).tobytes() == source.tobytes()
    solid = optimise_amiga(Image.new('RGB', (3, 2), (255, 136, 0)))
    assert solid.registers == (0xf80,)
    assert solid.bitplanes == 5  # Requested capacity is independent of colours used.


def test_weighted_mean_is_fitted_from_original_rgb_not_prequantised_pixels():
    source = Image.new('RGB', (4, 1))
    source.putdata([(0, 0, 0)] + [(9, 0, 0)] * 3)
    # Mean 6.75 snaps to 0. Quantising first gives 0/17/17/17, whose mean
    # instead snaps to 17. Fit the original RGB samples and their weights.
    assert fit_rgb_palette(source, AMIGA_RGB, 1) == ((0, 0, 0),)
    source.putdata([(8, 0, 0)] * 3 + [(17, 0, 0)])
    assert fit_rgb_palette(source, AMIGA_RGB, 1) == ((17, 0, 0),)


def test_refinement_does_not_increase_original_rgb_error():
    source = varied_source()
    samples = [source.getpixel((x, y)) for y in range(source.height) for x in range(source.width)]
    def error(colours):
        return sum(min(colour_distance(rgb, value) for value in colours) for rgb in samples)
    initial = fit_rgb_palette(source, AMIGA_RGB, 8, max_iterations=0)
    refined = fit_rgb_palette(source, AMIGA_RGB, 8)
    assert error(refined) <= error(initial)
    assert refined == fit_rgb_palette(source, AMIGA_RGB, 8)


def test_generic_fitter_works_on_other_rgb_precision_and_sample_limits():
    grid = RGBGrid((0, 85, 170, 255))
    source = varied_source()
    fitted = fit_rgb_palette(source, grid, 4, max_samples=16)
    assert fitted == fit_rgb_palette(source, grid, 4, max_samples=16)
    assert 1 <= len(fitted) <= 4
    assert all(channel in grid.levels for rgb in fitted for channel in rgb)


@pytest.mark.parametrize('kwargs', [dict(colour_limit=0), dict(colour_limit=True), dict(colour_limit=4097),
                                  dict(max_samples=0), dict(max_samples=1.5), dict(max_iterations=-1),
                                  dict(max_iterations=True)])
def test_invalid_fitter_options(kwargs):
    args = dict(colour_limit=4)
    args.update(kwargs)
    with pytest.raises(ValueError):
        fit_rgb_palette(varied_source(), AMIGA_RGB, **args)


def test_empty_fitter_image():
    with pytest.raises(ValueError, match='positive'):
        fit_rgb_palette(Image.new('RGB', (0, 1)), AMIGA_RGB, 4)


@pytest.mark.parametrize('resolution,width,aspect', [('lores', 320, 1), ('hires', 640, .5)])
@pytest.mark.parametrize('suffix,height', [('', 256), ('-ntsc', 200)])
def test_standard_profiles_and_consistent_preview_dimensions(tmp_path, resolution, width, aspect, suffix, height):
    profile = get_profile(f'amiga-{resolution}{suffix}')
    assert (profile.geometry.width, profile.geometry.height, profile.geometry.pixel_aspect) == (width, height, aspect)
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    Image.new('RGB', (16, 10), (255, 136, 0)).save(src)
    result = convert_file(src, dst, profile_name=profile.name, amiga_mode='constrained', scale=2 if resolution == 'lores' else 1)
    assert (result.width, result.height) == (width, height)
    assert result.palette.rgb_values() == ((255, 136, 0),)
    with Image.open(dst) as preview:
        assert preview.size == (640, height * 2)


def test_hires_preview_retains_every_logical_column():
    image = IndexedImage(640, 1, AMIGA, ((0, 4095) * 320,))
    preview = render_indexed(image, pixel_aspect=.5)
    assert preview.size == (640, 2)
    for y in range(2):
        assert [preview.getpixel((x, y)) for x in range(640)] == [(0, 0, 0), (255, 255, 255)] * 320


@pytest.mark.parametrize('profile', ['amiga-lores', 'amiga-hires', 'amiga-lores-ntsc', 'amiga-hires-ntsc'])
@pytest.mark.parametrize('palette_name', ['amiga', 'c64', 'cpc'])
def test_unrestricted_default_and_palette_mixing(tmp_path, profile, palette_name):
    source = varied_source()
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source.save(src)
    result = convert_file(src, dst, profile_name=profile, palette_name=palette_name,
                          width=16, height=8, fit='stretch', scale=1)
    assert result == quantize(source, get_palette(palette_name))
    if palette_name == 'amiga':
        assert len({p for row in result.pixels for p in row}) > 32


@pytest.mark.parametrize('profile', ['amiga-lores', 'amiga-hires-ntsc'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_cli_adjustments_and_selected_colour_count(tmp_path, profile, dither):
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source = varied_source()
    source.save(src)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(src), str(dst),
                    '--profile', profile, '--amiga-mode', 'constrained', '--colours', '8',
                    '--width', '16', '--height', '8', '--fit', 'stretch', '--scale', '1',
                    '--hue-shift', '20', '--green-gain', '1.15', '--dither', dither], check=True)
    resolution = 'hires' if 'hires' in profile else 'lores'
    expected = rasterize_amiga(optimise_amiga(adjust_colours(source, hue_shift=20, green_gain=1.15),
                                            resolution=resolution, colours=8, dither=dither))
    with Image.open(dst) as preview:
        assert preview.tobytes() == render_indexed(expected, pixel_aspect=get_profile(profile).geometry.pixel_aspect).tobytes()


@pytest.mark.parametrize('changes,match', [
    (dict(resolution='invalid'), 'resolution'), (dict(resolution='hires', bitplanes=5), 'colours'),
    (dict(bitplanes=0), 'bitplanes'), (dict(bitplanes=True), 'bitplanes'),
    (dict(registers=()), 'count'), (dict(registers=(0, 1, 2)), 'count'),
    (dict(registers=(-1, 0)), 'register colours'), (dict(registers=(0, 4096)), 'register colours'),
    (dict(registers=(0, True)), 'register colours'), (dict(registers=(0, 0)), 'unique'),
    (dict(pixels=()), 'grid'), (dict(pixels=((2, 0),)), 'index'),
    (dict(pixels=((True, 0),)), 'index'), (dict(width=0), 'positive'),
])
def test_invalid_models(changes, match):
    args = dict(width=2, height=1, resolution='lores', bitplanes=1, registers=(0, 0xfff), pixels=((0, 1),))
    args.update(changes)
    with pytest.raises(ValueError, match=match):
        AmigaImage(**args)


@pytest.mark.parametrize('kwargs,match', [
    (dict(amiga_mode='invalid'), 'unknown Amiga'), (dict(amiga_mode='constrained'), 'only valid'),
    (dict(colours=8), 'requires'), (dict(profile_name='amiga-lores', colours=8), 'requires'),
    (dict(profile_name='amiga-lores', amiga_mode='constrained', colours=3), 'colours'),
    (dict(profile_name='amiga-lores', amiga_mode='constrained', colours=True), 'colours'),
    (dict(profile_name='amiga-hires', amiga_mode='constrained', colours=32), 'colours'),
    (dict(profile_name='amiga-lores', amiga_mode='constrained', palette_name='c64'), 'amiga palette'),
    (dict(profile_name='amiga-lores', bbc_mode='constrained'), 'only valid'),
    (dict(profile_name='amiga-lores', cpc_mode='constrained'), 'only valid'),
    (dict(profile_name='amiga-lores', c64_mode='multicolour'), 'only valid'),
    (dict(profile_name='amiga-lores', teletext_mode='mosaic'), 'only valid'),
    (dict(profile_name='amiga-lores', spectrum_mode='attributes'), 'only valid'),
])
def test_invalid_options_preserve_existing_output(tmp_path, kwargs, match):
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    varied_source().save(src)
    dst.write_bytes(b'unchanged output')
    with pytest.raises(ValueError, match=match):
        convert_file(src, dst, **kwargs)
    assert dst.read_bytes() == b'unchanged output'


def test_invalid_optimiser_dither():
    with pytest.raises(ValueError, match='dither'):
        optimise_amiga(varied_source(), dither='invalid')
