"""Console register layouts, bank constraints and CLI/preset integration."""
from dataclasses import replace
import json

from PIL import Image
import pytest

from retroimg.cli import build_parser, main
from retroimg.constraints.palette_banks import fit_palette_banks
from retroimg.convert import convert_file
from retroimg.guided import palette_choices, profile_families, profile_modes
from retroimg.palettes import get_palette
from retroimg.palettes.megadrive import MEGADRIVE_RGB
from retroimg.palettes.snes import SNES_RGB
from retroimg.profiles import get_profile
from retroimg.render import render_indexed
from retroimg.settings import default_settings, merge_settings, normalize_settings
from retroimg.targets.megadrive import (
    MegaDriveImage, decode_colour as md_decode, encode_colour as md_encode,
    optimise_megadrive, rasterize_megadrive,
)
from retroimg.targets.snes import (
    SNESTileImage, decode_colour as snes_decode, encode_colour as snes_encode,
    optimise_snes_tiles, optimise_snes_indexed, rasterize_snes_tiles, rasterize_snes_indexed,
)


def source(size=(16, 16)):
    image = Image.new('RGB', size)
    image.putdata([((x * 23 + y * 7) % 256, (x * 7 + y * 41) % 256, (x * 17 + y * 19) % 256)
                   for y in range(size[1]) for x in range(size[0])])
    return image


def test_hardware_register_layouts_and_roundtrips():
    assert md_encode((255, 0, 0)) == 0x00e
    assert md_encode((0, 255, 0)) == 0x0e0
    assert md_encode((0, 0, 255)) == 0xe00
    for colour in get_palette('megadrive').rgb_values():
        assert md_decode(md_encode(colour)) == colour
    assert snes_encode((255, 0, 0)) == 0x001f
    assert snes_encode((0, 255, 0)) == 0x03e0
    assert snes_encode((0, 0, 255)) == 0x7c00
    for colour in get_palette('snes').rgb_values():
        assert snes_decode(snes_encode(colour)) == colour


@pytest.mark.parametrize('decoder,values', [(md_decode, (-1, 1, 0x1000, True)),
                                            (snes_decode, (-1, 0x8000, True))])
def test_invalid_registers(decoder, values):
    for value in values:
        with pytest.raises(ValueError):
            decoder(value)


@pytest.mark.parametrize('optimise,rasterize,count,grid', [
    (optimise_megadrive, rasterize_megadrive, 4, MEGADRIVE_RGB),
    (optimise_snes_tiles, rasterize_snes_tiles, 8, SNES_RGB),
])
@pytest.mark.parametrize('dither,size', [('none', 4), ('floyd-steinberg', 4),
                                      ('bayer', 2), ('bayer', 4), ('bayer', 8)])
def test_constrained_tiles_and_determinism(optimise, rasterize, count, grid, dither, size):
    image = source()
    model = optimise(image, dither=dither, bayer_size=size)
    assert model == optimise(image, dither=dither, bayer_size=size)
    assert len(model.registers) == count
    assert all(len(bank) == 16 for bank in model.registers)
    tiles = model.tiles
    assert all(bank[0] == tiles.palettes[0][0] for bank in tiles.palettes)
    assert all(grid.snap(rgb) == rgb for bank in tiles.palettes for rgb in bank)
    output = rasterize(model)
    output.validate()
    assert render_indexed(output).mode == 'RGB'
    assert len(set(v for row in output.pixels for v in row)) <= 15 * count + count
    for ty in range(2):
        for tx in range(2):
            bank = tiles.tile_palettes[ty][tx]
            assert all(output.pixels[y][x] // 16 == bank
                       for y in range(ty * 8, ty * 8 + 8) for x in range(tx * 8, tx * 8 + 8))
    assert len(render_indexed(output).getcolors(count * 16)) <= 15 * count + 1


def test_full_fifteen_local_slots_plus_backdrop_are_available():
    # Two distinct banks, each with fifteen colours and the same black backdrop.
    levels = MEGADRIVE_RGB.levels
    red = [(r, g, 0) for r in levels[1:4] for g in levels[:5]]
    blue = [(0, g, b) for b in levels[1:4] for g in levels[:5]]
    image = Image.new('RGB', (16, 8))
    for x0, colours in ((0, red), (8, blue)):
        values = [(0, 0, 0)] * 19 + colours * 3
        for i, rgb in enumerate(values):
            image.putpixel((x0 + i % 8, i // 8), rgb)
    model = optimise_megadrive(image)
    assert render_indexed(rasterize_megadrive(model)).tobytes() == image.tobytes()
    assert len(set(model.tiles.tile_palettes[0])) == 2


def test_seed_tiles_with_equal_means_still_get_different_banks():
    grid = MEGADRIVE_RGB
    image = Image.new('RGB', (16, 8))
    for y in range(8):
        for x in range(16):
            colours = ((255, 0, 0), (0, 255, 255)) if x < 8 else ((0, 255, 0), (255, 0, 255))
            image.putpixel((x, y), colours[x % 2])
    fitted = fit_palette_banks(image, grid, 2, slots=3)
    assert fitted.tile_palettes[0][0] != fitted.tile_palettes[0][1]


@pytest.mark.parametrize('dither', ['bayer', 'floyd-steinberg'])
def test_bayer_phase_and_tile_diffusion_are_preserved(dither):
    from retroimg.model import Colour, Palette
    from retroimg.quantize import quantize
    model = fit_palette_banks(source(), MEGADRIVE_RGB, 4, tile_size=4, dither=dither, bayer_size=8)
    for tx in range(2):
        bank = model.palettes[model.tile_palettes[0][tx]]
        palette = Palette('bank', tuple(Colour(str(i), rgb) for i, rgb in enumerate(bank)))
        expected = quantize(source().crop((tx * 4, 0, tx * 4 + 4, 4)), palette,
                            dither, bayer_size=8, bayer_origin=(tx * 4, 0))
        assert tuple(tuple(row[tx * 4:tx * 4 + 4]) for row in model.pixels[:4]) == expected.pixels


@pytest.mark.parametrize('optimise,rasterize', [(optimise_megadrive, rasterize_megadrive),
                                              (optimise_snes_tiles, rasterize_snes_tiles)])
def test_solid_backdrop_and_unused_banks(optimise, rasterize):
    model = optimise(Image.new('RGB', (8, 8), 'black'))
    assert all(bank == (0,) * 16 for bank in model.registers)
    assert model.tiles.pixels == ((0,) * 8,) * 8
    assert render_indexed(rasterize(model)).getcolors() == [(64, (0, 0, 0))]


def test_models_reject_inconsistent_registers_selectors_and_codes():
    md = optimise_megadrive(source())
    for change in ({'width': 15}, {'tile_palettes': ((4, 0), (0, 0))},
                   {'pixels': ((16,) * 16,) * 16}, {'palettes': (((0, 0, 0),),)}):
        with pytest.raises(ValueError):
            replace(md.tiles, **change)
    with pytest.raises(ValueError):
        MegaDriveImage(md.registers[:3], md.tiles)
    with pytest.raises(ValueError):
        SNESTileImage(md.registers * 2, md.tiles)
    with pytest.raises(ValueError):
        replace(md, registers=tuple((0,) * 16 for _ in range(4)))


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg', 'bayer'])
def test_snes_indexed_retains_up_to_256_colours(dither):
    image = source()
    model = optimise_snes_indexed(image, dither=dither)
    assert 1 <= len(model.registers) <= 256
    assert all(0 <= v <= 0x7fff for v in model.registers)
    assert model == optimise_snes_indexed(image, dither=dither)
    output = rasterize_snes_indexed(model)
    assert len(set(output.palette.rgb_values())) <= 256
    with pytest.raises(ValueError):
        replace(model, registers=(0,) * 257)
    with pytest.raises(ValueError):
        replace(model, pixels=((256,) * 16,) * 16)


@pytest.mark.parametrize('profile,flag,mode', [
    ('megadrive-320', 'megadrive_mode', 'tiles'),
    ('megadrive-256-pal', 'megadrive_mode', 'tiles'),
    ('snes', 'snes_mode', 'tiles'), ('snes', 'snes_mode', 'indexed'),
])
def test_cli_presets_adjustments_and_guided_discovery(tmp_path, profile, flag, mode):
    image = source()
    input_path, output = tmp_path / 'source.png', tmp_path / 'output.png'
    image.save(input_path)
    values = dict(profile=profile, **{flag: mode}, width=16, height=16, scale=1,
                  dither='bayer', bayer_size=2, brightness=1.2, contrast=1.1, hue_shift=20)
    defaults = default_settings(build_parser())
    normalized = normalize_settings(values, defaults)
    assert normalized[flag] == mode
    assert profile_modes(get_profile(profile))[0] == flag
    assert palette_choices(get_profile(profile), mode, flag) == (get_profile(profile).default_palette,)
    assert profile.split('-')[0] in profile_families()
    preset = tmp_path / 'test.json'
    preset.write_text(json.dumps(dict(version=1, name='Console', settings=values)))
    main(['convert', str(input_path), str(output), '--preset', str(preset)])
    expected = convert_file(input_path, tmp_path / 'reference.png', profile_name=profile,
                            **{flag: mode}, width=16, height=16, scale=1, dither='bayer', bayer_size=2,
                            brightness=1.2, contrast=1.1, hue_shift=20)
    with Image.open(output) as actual:
        assert actual.tobytes() == render_indexed(expected, pixel_aspect=get_profile(profile).geometry.pixel_aspect).tobytes()
    reset = merge_settings(normalized, dict(profile='teletext'), defaults)
    assert reset[flag] == 'bitmap'


@pytest.mark.parametrize('optimise', [optimise_megadrive, optimise_snes_tiles, optimise_snes_indexed])
def test_dimensions_palette_and_dither_validation(optimise):
    for image in (source((15, 16)), source((16, 15))):
        with pytest.raises(ValueError, match='multiple'):
            optimise(image)
    with pytest.raises(ValueError, match='palette'):
        optimise(source(), get_palette('c64'))
    with pytest.raises(ValueError, match='dither'):
        optimise(source(), dither='invalid')


def test_wrong_profile_modes_are_rejected_before_reading_files(tmp_path):
    with pytest.raises(ValueError, match='megadrive'):
        convert_file(tmp_path / 'absent', tmp_path / 'out.png', megadrive_mode='tiles')
    with pytest.raises(ValueError, match='snes'):
        convert_file(tmp_path / 'absent', tmp_path / 'out.png', snes_mode='indexed')


def test_neutral_bitmap_modes_use_existing_quantizer(tmp_path):
    from retroimg.geometry import resize_to_geometry
    from retroimg.model import Geometry
    from retroimg.quantize import quantize
    path = tmp_path / 'source.png'
    source().save(path)
    for profile in ('megadrive-320', 'snes'):
        actual = convert_file(path, tmp_path / 'out.png', profile_name=profile, width=16, height=16, scale=1)
        geometry = get_profile(profile).geometry
        prepared = resize_to_geometry(source(), Geometry(16, 16, pixel_aspect=geometry.pixel_aspect))
        assert actual == quantize(prepared, get_palette(get_profile(profile).default_palette))
