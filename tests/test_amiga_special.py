"""Native EHB/HAM codes, register links, scanline state and diffusion."""
from itertools import product
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.convert import convert_file
from retroimg.palettes import get_palette
from retroimg.palettes.builtin import AMIGA
from retroimg.quantize import colour_distance, quantize
from retroimg.render import render_indexed
from retroimg.targets.amiga import (
    AmigaEHBImage, AmigaHAMImage, decode_ham_code, half_bright,
    fit_ehb_registers, optimise_ehb, optimise_ham, rasterize_ehb, rasterize_ham,
)


def source_image():
    image = Image.new('RGB', (16, 8))
    image.putdata([((i * 31) % 256, (i * 73) % 256, (i * 113) % 256) for i in range(128)])
    return image


def test_half_bright_truncates_each_four_bit_channel():
    assert half_bright(0xfff) == 0x777  # 119 in preview RGB, not 127 or 128.
    assert half_bright(0xf80) == 0x740
    assert half_bright(0x111) == 0
    for r, g, b in product(range(16), repeat=3):
        assert half_bright((r << 8) | (g << 4) | b) == ((r // 2) << 8) | ((g // 2) << 4) | (b // 2)


def test_ehb_code_bit5_selects_linked_colour():
    screen = AmigaEHBImage(4, 1, (0xfff, 0xf80) + (0,) * 30, ((0, 32, 1, 33),))
    image = rasterize_ehb(screen)
    assert screen.bitplanes == 6
    assert image.pixels == screen.codes
    assert len(image.palette.colours) == 64
    assert [image.palette.colours[index].rgb for index in image.pixels[0]] == [
        (255, 255, 255), (119, 119, 119), (255, 136, 0), (119, 68, 0)]


def test_ehb_refinement_is_deterministic_and_does_not_worsen_linked_fit():
    source = source_image()
    seed = fit_ehb_registers(source, max_samples=None, max_iterations=0)
    fitted = fit_ehb_registers(source, max_samples=None)
    def error(registers):
        values = [AMIGA.colours[value].rgb for value in (*registers, *(half_bright(v) for v in registers))]
        return sum(min(colour_distance(source.getpixel((x, y)), value) for value in values)
                   for y in range(source.height) for x in range(source.width))
    assert error(fitted) <= error(seed)
    assert len(fitted) == 32
    assert fitted == fit_ehb_registers(source, max_samples=None)


@pytest.mark.parametrize('iterations', [-1, True, 1.5])
def test_ehb_rejects_invalid_iteration_budget(iterations):
    with pytest.raises(ValueError, match='max_iterations'):
        fit_ehb_registers(source_image(), max_iterations=iterations)


def test_ham_known_operations_and_row_reset():
    registers = (0x123, 0xabc) + (0,) * 14
    image = AmigaHAMImage(4, 2, registers, ((1, 0x14, 0x25, 0x36), (0x15, 0, 0, 0)))
    assert image.bitplanes == 6
    assert rasterize_ham(image).pixels == ((0xabc, 0xab4, 0x5b4, 0x564), (0x125, 0x123, 0x123, 0x123))
    assert decode_ham_code(0xabc, registers, 0) == 0x123


def test_ham_codes_can_reach_the_entire_rgb12_space():
    codes = tuple(code for r, g, b in product(range(16), repeat=3)
                  for code in (0x20 | r, 0x30 | g, 0x10 | b))
    screen = AmigaHAMImage(len(codes), 1, (0,) * 16, (codes,))
    raster = rasterize_ham(screen)
    assert raster.pixels[0][2::3] == tuple(range(4096))
    assert len(set(raster.pixels[0])) == 4096


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_ham_greedy_matches_all_64_code_oracle_with_real_decoded_error(dither):
    source = source_image()
    screen = optimise_ham(source, dither=dither)
    previous = screen.registers[0]
    codes = []
    def exhaustive(x, y, rgb):
        nonlocal previous
        if x == 0:
            previous = screen.registers[0]
            codes.append([])
        choices = [decode_ham_code(previous, screen.registers, code) for code in range(64)]
        code = min(range(64), key=lambda c: colour_distance(rgb, AMIGA.colours[choices[c]].rgb))
        previous = choices[code]
        codes[-1].append(code)
        return previous
    oracle = quantize(source, AMIGA, dither, pixel_lookup=exhaustive)
    assert screen.codes == tuple(tuple(row) for row in codes)
    assert rasterize_ham(screen) == oracle
    assert any(code >= 16 for row in screen.codes for code in row)
    assert len({pixel for row in oracle.pixels for pixel in row}) > 16


@pytest.mark.parametrize('optimise,rasterize', [(optimise_ehb, rasterize_ehb), (optimise_ham, rasterize_ham)])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_special_modes_repeatability_and_exact_known_colours(optimise, rasterize, dither):
    source = Image.new('RGB', (4, 2))
    source.putdata([AMIGA.colours[value].rgb for value in (0x000, 0xf80, 0x036, 0xfff) * 2])
    screen = optimise(source, dither=dither)
    assert screen == optimise(source, dither=dither)
    assert render_indexed(rasterize(screen)).tobytes() == source.tobytes()
    assert len(screen.registers) == (32 if optimise == optimise_ehb else 16)
    assert all(0 <= code < 64 for row in screen.codes for code in row)
    assert screen.registers == optimise(source).registers


@pytest.mark.parametrize('model,slots', [(AmigaEHBImage, 32), (AmigaHAMImage, 16)])
@pytest.mark.parametrize('changes,match', [
    (dict(width=0), 'positive'), (dict(height=True), 'positive'),
    (dict(registers=()), 'exactly'), (dict(registers='out-of-range'), 'register colours'),
    (dict(codes=()), 'grid'), (dict(codes=((0,),)), 'grid'),
    (dict(codes=((0, 64),)), 'codes'), (dict(codes=((True, 0),)), 'codes'),
    (dict(codes=((0, -1),)), 'codes'), (dict(codes=((0, 1.5),)), 'codes'),
])
def test_special_model_validation(model, slots, changes, match):
    if changes.get('registers') == 'out-of-range':
        changes = dict(registers=(4096,) + (0,) * (slots - 1))
    args = dict(width=2, height=1, registers=(0,) * slots, codes=((0, 1),))
    args.update(changes)
    with pytest.raises(ValueError, match=match):
        model(**args)


@pytest.mark.parametrize('mode', ['ehb', 'ham'])
@pytest.mark.parametrize('profile', ['amiga-lores', 'amiga-lores-ntsc'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_special_cli_with_adjustments(tmp_path, mode, profile, dither):
    source = source_image()
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source.save(src)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(src), str(dst),
                    '--profile', profile, '--amiga-mode', mode, '--dither', dither,
                    '--width', '16', '--height', '8', '--fit', 'stretch', '--scale', '1',
                    '--hue-shift', '20', '--green-gain', '1.15'], check=True)
    optimise, rasterize = (optimise_ehb, rasterize_ehb) if mode == 'ehb' else (optimise_ham, rasterize_ham)
    expected = render_indexed(rasterize(optimise(adjust_colours(source, hue_shift=20, green_gain=1.15), dither=dither)))
    with Image.open(dst) as preview:
        assert preview.tobytes() == expected.tobytes()


@pytest.mark.parametrize('mode', ['ehb', 'ham'])
@pytest.mark.parametrize('profile', ['amiga-hires', 'amiga-hires-ntsc', 'teletext'])
def test_special_modes_reject_wrong_geometry_without_overwriting(tmp_path, mode, profile):
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source_image().save(src)
    dst.write_bytes(b'original')
    with pytest.raises(ValueError, match='unsupported mode|only valid'):
        convert_file(src, dst, profile_name=profile, amiga_mode=mode)
    assert dst.read_bytes() == b'original'


@pytest.mark.parametrize('optimise', [optimise_ehb, optimise_ham])
@pytest.mark.parametrize('kwargs,match', [(dict(colours=16), 'colours'), (dict(dither='invalid'), 'dither'),
                                         (dict(palette=get_palette('c64')), 'amiga palette')])
def test_special_optimiser_options(optimise, kwargs, match):
    with pytest.raises(ValueError, match=match):
        optimise(source_image(), **kwargs)


@pytest.mark.parametrize('mode', ['ehb', 'ham'])
def test_colour_count_option_is_only_for_standard_indexed_modes(tmp_path, mode):
    src, dst = tmp_path / 'in.png', tmp_path / 'out.png'
    source_image().save(src)
    with pytest.raises(ValueError, match='colours requires'):
        convert_file(src, dst, profile_name='amiga-lores', amiga_mode=mode, colours=32)
    assert not dst.exists()
