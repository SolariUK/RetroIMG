from itertools import combinations, combinations_with_replacement
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.targets.c64 import C64MulticolourCell, C64MulticolourImage, optimise_c64_multicolour
from retroimg.constraints.shared_background import fit_shared_background
from retroimg.convert import convert_file
from retroimg.geometry import resize_to_geometry
from retroimg.model import Colour, Geometry, IndexedImage, Palette
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile
from retroimg.quantize import colour_distance, quantize
from retroimg.targets.c64 import rasterize_c64_multicolour
from retroimg.targets.c64 import C64HiresCell, C64HiresImage, optimise_c64_hires, rasterize_c64_hires
from retroimg.render import render_indexed

PALETTE = get_palette("c64")
VALUES = PALETTE.rgb_values()


def source_image(width=8, height=8):
    image = Image.new("RGB", (width, height))
    image.putdata([((i * 43) % 256, (i * 97) % 256, (i * 19) % 256)
                   for i in range(width * height)])
    return image


def test_hires_bit_order_and_independent_cell_colours():
    pattern = (1 << 0) | (1 << 7) | (1 << 8) | (1 << 63)
    frame = C64HiresImage(((C64HiresCell(2, 5, pattern), C64HiresCell(6, 14, pattern)),), 2, 1)
    indexed = rasterize_c64_hires(frame)
    assert indexed.pixels[0] == (5, 2, 2, 2, 2, 2, 2, 5, 14, 6, 6, 6, 6, 6, 6, 14)
    assert indexed.pixels[1][0] == 5 and indexed.pixels[7][7] == 5
    assert optimise_c64_hires(render_indexed(indexed)) == frame


def test_hires_undithered_fit_matches_exhaustive_source_error():
    source = source_image()
    samples = [source.getpixel((x, y)) for y in range(8) for x in range(8)]
    optimum = min(sum(min(colour_distance(rgb, VALUES[a]), colour_distance(rgb, VALUES[b]))
                      for rgb in samples) for a, b in combinations_with_replacement(range(16), 2))
    indexed = rasterize_c64_hires(optimise_c64_hires(source))
    actual = sum(colour_distance(rgb, VALUES[index])
                 for rgb, index in zip(samples, sum(indexed.pixels, ())))
    assert actual == optimum


@pytest.mark.parametrize('dither', ['none', 'bayer', 'floyd-steinberg'])
def test_hires_constraints_and_dithering_reset_per_cell(tmp_path, dither):
    source = source_image(16, 16)
    frame = optimise_c64_hires(source, dither=dither)
    indexed = rasterize_c64_hires(frame)
    for y in (0, 8):
        for x in (0, 8):
            pixels = tuple(row[x:x + 8] for row in indexed.pixels[y:y + 8])
            assert len({i for row in pixels for i in row}) <= 2
            expected = rasterize_c64_hires(optimise_c64_hires(source.crop((x, y, x + 8, y + 8)), dither=dither))
            assert pixels == expected.pixels
    path = tmp_path / 'source.png'
    source.save(path)
    assert convert_file(path, tmp_path / 'result.png', profile_name='c64-hires', c64_mode='hires',
                        width=16, height=16, scale=1, fit='stretch', dither=dither) == indexed


@pytest.mark.parametrize('kwargs,match', [
    (dict(palette=get_palette('spectrum')), 'c64 palette'),
    (dict(image=Image.new('RGB', (7, 8))), 'divisible'),
    (dict(dither='invalid'), 'dither'),
])
def test_hires_rejects_incompatible_input(kwargs, match):
    with pytest.raises(ValueError, match=match):
        optimise_c64_hires(**(dict(image=source_image()) | kwargs))


@pytest.mark.parametrize('kwargs', [dict(paper=-1), dict(ink=16), dict(pattern=True), dict(pattern=1 << 64)])
def test_hires_cells_reject_invalid_registers_and_pattern(kwargs):
    with pytest.raises(ValueError):
        C64HiresCell(**(dict(paper=0, ink=1, pattern=0) | kwargs))


def test_selector_bit_order_and_shared_background():
    pattern = sum((bit % 4) << (2 * bit) for bit in range(32))
    cell = C64MulticolourCell((1, 2, 3), pattern)
    image = C64MulticolourImage(4, ((cell,),), 1, 1)
    raster = rasterize_c64_multicolour(image)
    assert raster.pixels == ((4, 1, 2, 3),) * 8
    preview = render_indexed(raster, pixel_aspect=2)
    assert preview.size == (8, 8)
    assert [preview.getpixel((x, 0)) for x in range(8)] == [VALUES[i] for i in (4, 4, 1, 1, 2, 2, 3, 3)]


def test_global_background_and_cell_sets_match_exhaustive_oracle():
    # Each cell has four exact colours, but the cells have no colour in common.
    # Independent four-colour fits would be illegal together: a global choice
    # must sacrifice some accuracy in at least one cell.
    groups = ((2, 3, 4, 5), (6, 7, 8, 9))
    source = Image.new("RGB", (8, 8))
    source.putdata([VALUES[groups[x // 4][x % 4]] for y in range(8) for x in range(8)])
    samples = [[VALUES[i] for i in group] for group in groups]
    per_background = []
    for bg in range(16):
        total = 0
        for cell in samples:
            total += 8 * min(
                sum(min(colour_distance(sample, VALUES[index]) for index in (bg, *local))
                    for sample in cell)
                for local in combinations([i for i in range(16) if i != bg], 3)
            )
        per_background.append(total)
    expected_background = min(range(16), key=per_background.__getitem__)
    result = optimise_c64_multicolour(source)
    raster = rasterize_c64_multicolour(result)
    actual = sum(colour_distance(source.getpixel((x, y)), VALUES[raster.pixels[y][x]])
                 for y in range(8) for x in range(8))
    assert result.background == expected_background
    assert actual == min(per_background)
    assert actual > 0
    for row in result.cells:
        for cell in row:
            assert len(set((result.background, *cell.colours))) <= 4
    for cx in range(2):
        used = {raster.pixels[y][cx * 4 + x] for y in range(8) for x in range(4)}
        assert len(used - {result.background}) <= 3


def test_background_slot_can_be_unused_and_ties_are_deterministic():
    source = Image.new("RGB", (4, 8))
    source.putdata([VALUES[(2, 4, 6)[i % 3]] for i in range(32)])
    result = optimise_c64_multicolour(source)
    assert result.background == 0  # All backgrounds achieve zero error.
    raster = rasterize_c64_multicolour(result)
    assert all(index != 0 for row in raster.pixels for index in row)
    assert render_indexed(raster).tobytes() == source.tobytes()
    assert result == optimise_c64_multicolour(source)


@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_cell_constraints_and_diffusion_boundaries(dither):
    source = source_image(8, 16)
    result = optimise_c64_multicolour(source, dither=dither)
    assert result == optimise_c64_multicolour(source, dither=dither)
    undithered = optimise_c64_multicolour(source)
    assert result.background == undithered.background
    raster = rasterize_c64_multicolour(result)
    for cy, row in enumerate(result.cells):
        for cx, cell in enumerate(row):
            assert cell.colours == undithered.cells[cy][cx].colours
            indices = sorted(set((result.background, *cell.colours)))
            local_palette = Palette("local", tuple(PALETTE.colours[i] for i in indices))
            crop = source.crop((cx * 4, cy * 8, cx * 4 + 4, cy * 8 + 8))
            expected = quantize(crop, local_palette, dither)
            actual = tuple(tuple(raster.pixels[cy * 8 + y][cx * 4 + x] for x in range(4)) for y in range(8))
            assert actual == tuple(tuple(indices[i] for i in line) for line in expected.pixels)
            assert {i for line in actual for i in line} <= set(indices)


def test_standard_grid_and_solid_image():
    source = Image.new("RGB", (160, 200), VALUES[5])
    result = optimise_c64_multicolour(source)
    assert (result.columns, result.rows) == (40, 25)
    raster = rasterize_c64_multicolour(result)
    assert (raster.width, raster.height) == (160, 200)
    assert raster.pixels == ((5,) * 160,) * 200


@pytest.mark.parametrize("args", [((1, 2), 0), ((1, 2, 16), 0), ((1, -1, 2), 0),
                                   ((1, 2, 3), -1), ((1, 2, 3), 1 << 64), ((1, 2, 3), 0.5)])
def test_invalid_cells(args):
    with pytest.raises(ValueError):
        C64MulticolourCell(*args)


def test_invalid_images():
    cell = C64MulticolourCell((1, 2, 3), 0)
    with pytest.raises(ValueError, match="background"):
        C64MulticolourImage(16, ((cell,),), 1, 1)
    with pytest.raises(ValueError, match="grid"):
        C64MulticolourImage(0, (), 1, 1)
    with pytest.raises(ValueError, match="positive"):
        C64MulticolourImage(0, (), 0, 0)
    with pytest.raises(ValueError, match="C64MulticolourCell"):
        C64MulticolourImage(0, ((None,),), 1, 1)
    with pytest.raises(ValueError, match="c64 palette"):
        C64MulticolourImage(0, ((cell,),), 1, 1, get_palette("teletext"))


@pytest.mark.parametrize("size", [(5, 8), (4, 9), (0, 8)])
def test_invalid_geometry(size):
    with pytest.raises(ValueError, match="divisible"):
        optimise_c64_multicolour(Image.new("RGB", size))


def test_invalid_palette_and_dither():
    with pytest.raises(ValueError, match="c64 palette"):
        optimise_c64_multicolour(source_image(), get_palette("spectrum"))
    with pytest.raises(ValueError, match="dither"):
        optimise_c64_multicolour(source_image(), dither="invalid")


@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
@pytest.mark.parametrize("palette_name", ["c64", "teletext"])
def test_unrestricted_new_profile_allows_palette_swaps(tmp_path, dither, palette_name):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source = source_image()
    source.save(src)
    result = convert_file(src, dst, profile_name="c64-multicolour", palette_name=palette_name,
                          width=8, height=8, scale=2, dither=dither)
    prepared = resize_to_geometry(source, Geometry(8, 8, pixel_aspect=2))
    assert result == quantize(prepared, get_palette(palette_name), dither)
    with Image.open(dst) as preview:
        assert preview.size == (32, 16)
        assert preview.tobytes() == render_indexed(result, scale=2, pixel_aspect=2).tobytes()


def test_legacy_c64_hires_geometry_and_preview_are_unchanged(tmp_path):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source = source_image()
    source.save(src)
    result = convert_file(src, dst, profile_name="c64-hires", scale=1)
    prepared = resize_to_geometry(source, get_profile("c64-hires").geometry)
    assert result == quantize(prepared, PALETTE)
    with Image.open(dst) as preview:
        assert preview.size == (320, 200)
        assert preview.tobytes() == render_indexed(result).tobytes()


@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_cli_multicolour_with_adjustments(tmp_path, dither):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source = source_image()
    source.save(src)
    subprocess.run([sys.executable, "-m", "retroimg.cli", "convert", str(src), str(dst),
                    "--profile", "c64-multicolour", "--c64-mode", "multicolour",
                    "--width", "8", "--height", "8", "--scale", "2", "--dither", dither,
                    "--hue-shift", "20", "--green-gain", "1.15"], check=True)
    prepared = resize_to_geometry(source, Geometry(8, 8, pixel_aspect=2))
    prepared = adjust_colours(prepared, hue_shift=20, green_gain=1.15)
    expected = rasterize_c64_multicolour(optimise_c64_multicolour(prepared, dither=dither))
    with Image.open(dst) as preview:
        assert preview.size == (32, 16)
        assert preview.tobytes() == render_indexed(expected, scale=2, pixel_aspect=2).tobytes()


@pytest.mark.parametrize("kwargs,match", [
    (dict(c64_mode="invalid"), "unknown C64"),
    (dict(c64_mode="multicolour"), "only valid"),
    (dict(profile_name="c64-hires", c64_mode="multicolour"), "unsupported mode"),
    (dict(profile_name="c64-multicolour", c64_mode="multicolour", palette_name="spectrum"), "c64 palette"),
    (dict(profile_name="c64-multicolour", c64_mode="multicolour", width=7, height=8), "divisible"),
])
def test_invalid_conversion_leaves_output_untouched(tmp_path, kwargs, match):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source_image().save(src)
    with pytest.raises(ValueError, match=match):
        convert_file(src, dst, **kwargs)
    assert not dst.exists()


@pytest.mark.parametrize("aspect", [0, -1, float("inf"), float("nan")])
def test_invalid_preview_aspect(aspect):
    raster = IndexedImage(1, 1, PALETTE, ((0,),))
    with pytest.raises(ValueError, match="aspect"):
        render_indexed(raster, pixel_aspect=aspect)


@pytest.mark.parametrize("colour_limit", [1, 2, 4, 8])
def test_generic_shared_fit_matches_small_palette_oracle(colour_limit):
    palette = Palette("test", tuple(Colour(str(v), (v, v, v)) for v in (0, 60, 120, 180, 255)))
    source = Image.new("RGB", (4, 1))
    samples = [(v, v, v) for v in (10, 90, 165, 240)]
    source.putdata(samples)
    result = fit_shared_background(source, palette, cell_width=2, cell_height=1, colour_limit=colour_limit)
    values = palette.rgb_values()
    scores = []
    for bg in range(len(values)):
        candidates = [(bg, *others) for others in combinations(
            [i for i in range(len(values)) if i != bg], min(colour_limit - 1, len(values) - 1))]
        scores.append(sum(min(sum(min(colour_distance(sample, values[index]) for index in choice)
                                      for sample in cell) for choice in candidates)
                          for cell in (samples[:2], samples[2:])))
    assert result.background == min(range(len(values)), key=scores.__getitem__)
    actual = sum(min(colour_distance(sample, values[index]) for index in choice)
                 for cell, choice in zip((samples[:2], samples[2:]), result.colours[0]) for sample in cell)
    assert actual == min(scores)
    for choice in result.colours[0]:
        assert result.background in choice
        assert len(choice) <= colour_limit
