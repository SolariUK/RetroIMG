"""Background palette constraints, hardware codes and monochrome rendering."""
from dataclasses import replace

import pytest
from PIL import Image

from retroimg.constraints.palette_banks import fit_palette_banks
from retroimg.convert import convert_file
from retroimg.palettes import get_palette
from retroimg.palettes.gameboy import GAMEBOY, GAMEBOY_GREY
from retroimg.palettes.nes import NES, NES_SAFE_CODES
from retroimg.palettes.mastersystem import MASTERSYSTEM, MASTERSYSTEM_RGB
from retroimg.render import render_indexed
from retroimg.targets.gameboy import GameBoyImage, optimise_gameboy, rasterize_gameboy
from retroimg.targets.nes import NESImage, optimise_nes, rasterize_nes
from retroimg.targets.mastersystem import (
    MasterSystemImage, encode_colour, decode_colour, optimise_mastersystem, rasterize_mastersystem,
)
from examples.generate_gallery import check_constraints


def source():
    image = Image.new('RGB', (32, 32))
    image.putdata([((x*23+y*7)%256, (x*7+y*41)%256, (x*17+y*19)%256)
                   for y in range(32) for x in range(32)])
    return image


@pytest.mark.parametrize('optimise,rasterize,options', [
    (optimise_nes, rasterize_nes, dict(nes_mode='attributes')),
    (optimise_mastersystem, rasterize_mastersystem, dict(mastersystem_mode='tiles')),
    (optimise_gameboy, rasterize_gameboy, dict(gameboy_mode='tiles')),
])
@pytest.mark.parametrize('dither,size', [('none', 4), ('floyd-steinberg', 4), ('bayer', 2), ('bayer', 4), ('bayer', 8)])
def test_models_are_deterministic_and_outputs_obey_constraints(optimise, rasterize, options, dither, size):
    model = optimise(source(), dither=dither, bayer_size=size)
    assert model == optimise(source(), dither=dither, bayer_size=size)
    output = rasterize(model)
    check_constraints(output, options)
    assert render_indexed(output).mode == 'RGB'


def test_nes_four_attribute_palettes_can_retain_thirteen_colours():
    image = Image.new('RGB', (64, 16))
    colours = [c.rgb for i, c in enumerate(NES.colours) if i in NES_SAFE_CODES and c.rgb != (0, 0, 0)]
    colours = list(dict.fromkeys(colours))[:12]
    for block in range(4):
        values = [(0, 0, 0)] * 130 + colours[block*3:block*3+3] * 42
        for i, rgb in enumerate(values):
            image.putpixel((block*16+i%16, i//16), rgb)
    model = optimise_nes(image)
    assert len(model.registers) == 4
    assert len(set(model.attributes.tile_palettes[0])) == 4
    assert all(code != 0x0d for bank in model.registers for code in bank)
    actual = render_indexed(rasterize_nes(model))
    assert actual.tobytes() == image.tobytes()
    assert len(actual.getcolors()) == 13


def test_master_system_uses_all_thirty_two_background_colours():
    image = Image.new('RGB', (16, 8))
    colours = MASTERSYSTEM.rgb_values()
    for block, bank in enumerate((colours[:16], colours[-16:])):
        for i in range(64):
            image.putpixel((block*8+i%8, i//8), bank[i%16])
    model = optimise_mastersystem(image)
    assert not model.tiles.shared_backdrop
    assert model.registers[0][0] != model.registers[1][0]
    actual = render_indexed(rasterize_mastersystem(model))
    assert actual.tobytes() == image.tobytes()
    assert len(actual.getcolors()) == 32


def test_master_system_cram_encoding():
    assert encode_colour((255, 0, 0)) == 3
    assert encode_colour((0, 255, 0)) == 12
    assert encode_colour((0, 0, 255)) == 48
    for colour in MASTERSYSTEM.rgb_values():
        assert decode_colour(encode_colour(colour)) == colour
    for invalid in (-1, 64, True):
        with pytest.raises(ValueError):
            decode_colour(invalid)


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg', 'bayer'])
def test_gameboy_tint_does_not_change_luminance_codes(dither):
    green = optimise_gameboy(source(), GAMEBOY, dither)
    grey = optimise_gameboy(source(), GAMEBOY_GREY, dither)
    assert green.pixels == grey.pixels
    assert green.bgp == 0xe4
    assert len(render_indexed(rasterize_gameboy(green)).getcolors()) <= 4
    inverted = rasterize_gameboy(replace(grey, bgp=0x1b))
    assert inverted.pixels == tuple(tuple(3-code for code in row) for row in grey.pixels)


def test_model_validation_rejects_invalid_codes_and_layouts():
    nes = optimise_nes(source())
    with pytest.raises(ValueError, match='four'):
        NESImage(nes.registers[:3], nes.attributes)
    registers = list(nes.registers)
    registers[0] = (0x0d,) + registers[0][1:]
    with pytest.raises(ValueError, match='code'):
        NESImage(tuple(registers), nes.attributes)
    with pytest.raises(ValueError, match='attributes'):
        NESImage(nes.registers, replace(nes.attributes, shared_backdrop=False))
    sms = optimise_mastersystem(source())
    with pytest.raises(ValueError):
        MasterSystemImage(sms.registers[:1], sms.tiles)
    gb = optimise_gameboy(source())
    for change in ({'width': 31}, {'bgp': 256}, {'bgp': True}, {'palette': NES},
                   {'pixels': ((4,)*32,)*32}):
        with pytest.raises(ValueError):
            replace(gb, **change)


@pytest.mark.parametrize('optimise,multiple', [(optimise_nes, 16), (optimise_mastersystem, 8), (optimise_gameboy, 8)])
def test_bad_dimensions_palettes_and_dithers(optimise, multiple):
    with pytest.raises(ValueError, match='multiple'):
        optimise(Image.new('RGB', (multiple-1, multiple)))
    with pytest.raises(ValueError, match='palette'):
        optimise(source(), get_palette('c64'))
    with pytest.raises(ValueError, match='dither'):
        optimise(source(), dither='invalid')


@pytest.mark.parametrize('flag,mode', [('nes_mode', 'attributes'), ('mastersystem_mode', 'tiles'), ('gameboy_mode', 'tiles')])
def test_incompatible_mode_fails_before_opening_input(tmp_path, flag, mode):
    with pytest.raises(ValueError, match='only valid'):
        convert_file(tmp_path/'missing', tmp_path/'out.png', **{flag: mode})


def test_generic_bank_parameters_are_validated():
    for kwargs in ({'grid': None}, {'grid': MASTERSYSTEM_RGB, 'palette': NES},
                   {'grid': MASTERSYSTEM_RGB, 'shared_backdrop': 0}):
        with pytest.raises(ValueError):
            fit_palette_banks(source(), bank_count=2, **kwargs)
