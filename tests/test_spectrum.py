import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.constraints.cells import quantize_cells
from retroimg.convert import convert_file
from retroimg.model import IndexedImage
from retroimg.palettes import get_palette
from retroimg.quantize import colour_distance, quantize
from retroimg.targets.spectrum import rasterize_spectrum
from retroimg.render import render_indexed
from retroimg.targets.spectrum import (
    SpectrumCell, SpectrumImage, optimise_spectrum_attributes, spectrum_from_indexed,
)

PALETTE = get_palette("spectrum")
VALUES = PALETTE.rgb_values()


def source_image(width=16, height=16):
    image = Image.new("RGB", (width, height))
    image.putdata([((i * 43) % 256, (i * 97) % 256, (i * 19) % 256)
                   for i in range(width * height)])
    return image


def assert_legal_cells(image):
    image.validate()
    for y in range(0, image.height, 8):
        for x in range(0, image.width, 8):
            colours = {image.pixels[y + dy][x + dx] for dy in range(8) for dx in range(8)}
            assert len(colours) <= 2
            assert not (colours & set(range(1, 8)) and colours & set(range(8, 15)))


@pytest.mark.parametrize("paper,ink", [(2, 4), (9, 11), (0, 14)])
def test_known_normal_bright_and_black_patterns(paper, ink):
    # Includes opposite corners and the top-row boundary: detect transposition
    # and bit-order errors independently of the optimiser and renderer.
    pattern = (1 << 0) | (1 << 7) | (1 << 8) | (1 << 63)
    rows = tuple(tuple(ink if pattern & (1 << (y * 8 + x)) else paper
                       for x in range(8)) for y in range(8))
    indexed = IndexedImage(8, 8, PALETTE, rows)
    page = spectrum_from_indexed(indexed)
    bright = ink >= 8
    assert page.cells == ((SpectrumCell(ink - 7 if bright else ink,
                                      paper - 7 if bright and paper else paper,
                                      bright, pattern),),)
    assert rasterize_spectrum(page) == indexed
    source = render_indexed(indexed)
    assert rasterize_spectrum(optimise_spectrum_attributes(source)) == indexed


@pytest.mark.parametrize("index", range(15))
def test_solid_cells_are_lossless(index):
    source = Image.new("RGB", (8, 8), VALUES[index])
    page = optimise_spectrum_attributes(source)
    cell = page.cells[0][0]
    assert cell.ink == cell.paper
    assert cell.pattern == 0
    assert cell.bright == (index >= 8)
    assert rasterize_spectrum(page).pixels == ((index,) * 8,) * 8


def test_minimum_error_over_all_shared_brightness_attributes():
    source = source_image(8, 8)
    result = rasterize_spectrum(optimise_spectrum_attributes(source))
    samples = [source.getpixel((x, y)) for y in range(8) for x in range(8)]
    # Independently enumerate all hardware ink/paper/BRIGHT combinations.
    optimum = min(
        sum(min(colour_distance(sample, VALUES[paper + 7 if bright and paper else paper]),
                colour_distance(sample, VALUES[ink + 7 if bright and ink else ink]))
            for sample in samples)
        for bright in (False, True) for paper in range(8) for ink in range(8)
    )
    actual = sum(colour_distance(sample, VALUES[index])
                 for sample, index in zip(samples, sum(result.pixels, ())))
    assert actual == optimum
    assert_legal_cells(result)


@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_cell_constraints_determinism_and_independent_dithering(dither):
    source = source_image()
    page = optimise_spectrum_attributes(source, dither=dither)
    assert (page.columns, page.rows) == (2, 2)
    assert page == optimise_spectrum_attributes(source, dither=dither)
    result = rasterize_spectrum(page)
    assert_legal_cells(result)
    for y in range(0, 16, 8):
        for x in range(0, 16, 8):
            cell = source.crop((x, y, x + 8, y + 8))
            expected = rasterize_spectrum(optimise_spectrum_attributes(cell, dither=dither))
            assert tuple(row[x:x+8] for row in result.pixels[y:y+8]) == expected.pixels


def test_mixed_brightness_is_rejected_but_black_is_shared():
    illegal = IndexedImage(8, 8, PALETTE, ((2, 11) * 4,) * 8)
    with pytest.raises(ValueError, match="mix normal and bright"):
        spectrum_from_indexed(illegal)
    source = render_indexed(illegal)
    result = rasterize_spectrum(optimise_spectrum_attributes(source))
    assert_legal_cells(result)
    assert result != illegal
    # Black remains legal with either a normal or a bright colour.
    for index in (2, 9):
        indexed = IndexedImage(8, 8, PALETTE, ((0, index) * 4,) * 8)
        assert rasterize_spectrum(spectrum_from_indexed(indexed)) == indexed


@pytest.mark.parametrize("size", [(7, 8), (8, 9), (0, 8)])
def test_invalid_geometry(size):
    with pytest.raises(ValueError, match="divisible by 8"):
        optimise_spectrum_attributes(Image.new("RGB", size))


@pytest.mark.parametrize("args", [(8, 0, False, 0), (-1, 0, False, 0),
    (0, 8, False, 0), (0, 0, 1, 0), (0, 0, False, -1),
    (0, 0, False, 1 << 64), (0, 0, False, 0.5)])
def test_invalid_cell(args):
    with pytest.raises(ValueError):
        SpectrumCell(*args)


def test_invalid_grid_palette_and_colour_count():
    with pytest.raises(ValueError, match="grid"):
        SpectrumImage((), 1, 1)
    with pytest.raises(ValueError, match="positive"):
        SpectrumImage((), 0, 0)
    with pytest.raises(ValueError, match="SpectrumCell"):
        SpectrumImage(((None,),), 1, 1)
    with pytest.raises(ValueError, match="spectrum palette"):
        optimise_spectrum_attributes(source_image(), get_palette("c64"))
    with pytest.raises(ValueError, match="more than two"):
        spectrum_from_indexed(IndexedImage(8, 8, PALETTE, ((0, 1, 2, 0, 0, 0, 0, 0),) * 8))


def test_standard_screen_dimensions():
    page = optimise_spectrum_attributes(Image.new("RGB", (256, 192)))
    assert (page.columns, page.rows) == (32, 24)
    assert (rasterize_spectrum(page).width, rasterize_spectrum(page).height) == (256, 192)


@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_cli_and_default_bitmap_compatibility(tmp_path, dither):
    source = source_image()
    src, dst = tmp_path / "source.png", tmp_path / "out.png"
    source.save(src)
    bitmap = convert_file(src, dst, profile_name="spectrum", width=16, height=16,
                          scale=1, dither=dither)
    assert bitmap == quantize(source, PALETTE, dither)
    subprocess.run([sys.executable, "-m", "retroimg.cli", "convert", str(src), str(dst),
                    "--profile", "spectrum", "--spectrum-mode", "attributes",
                    "--width", "16", "--height", "16", "--scale", "2",
                    "--dither", dither, "--hue-shift", "20", "--green-gain", "1.15"], check=True)
    adjusted = adjust_colours(source, hue_shift=20, green_gain=1.15)
    expected = rasterize_spectrum(optimise_spectrum_attributes(adjusted, dither=dither))
    with Image.open(dst) as preview:
        assert preview.size == (32, 32)
        assert preview.tobytes() == render_indexed(expected, scale=2).tobytes()


@pytest.mark.parametrize("options,match", [
    (dict(spectrum_mode="unknown"), "unknown Spectrum"),
    (dict(spectrum_mode="attributes"), "only valid"),
    (dict(profile_name="spectrum", teletext_mode="mosaic"), "only valid"),
    (dict(profile_name="spectrum", spectrum_mode="attributes", palette_name="c64"), "spectrum palette"),
    (dict(profile_name="spectrum", spectrum_mode="attributes", width=15, height=16), "divisible by 8"),
])
def test_invalid_conversion_options_leave_output_untouched(tmp_path, options, match):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source_image().save(src)
    with pytest.raises(ValueError, match=match):
        convert_file(src, dst, scale=1, **options)
    assert not dst.exists()


def test_bitmap_retains_palette_independence(tmp_path):
    source = source_image()
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source.save(src)
    result = convert_file(src, dst, profile_name="spectrum", palette_name="c64",
                          width=16, height=16, scale=1)
    assert result == quantize(source, get_palette("c64"))


@pytest.mark.parametrize("pairs", [(), ((0, 15),), ((-1, 1),), ((1,),), ((0, 1.0),)])
def test_invalid_generic_allowed_pairs(pairs):
    with pytest.raises(ValueError, match="allowed pairs"):
        quantize_cells(source_image(8, 8), PALETTE, cell_width=8, cell_height=8,
                       allowed_pairs=pairs)
