from itertools import combinations
import subprocess
import sys

from PIL import Image
import pytest

from retroimg.adjustments import adjust_colours
from retroimg.cpc import CPCImage, optimise_cpc
from retroimg.convert import convert_file
from retroimg.model import Colour, Palette, IndexedImage
from retroimg.palettefit import select_palette_indices
from retroimg.palettes import get_palette
from retroimg.profiles import get_profile
from retroimg.quantize import colour_distance, quantize
from retroimg.render import rasterize_cpc, render_indexed

CPC = get_palette("cpc")
VALUES = CPC.rgb_values()


def palette_source():
    image = Image.new("RGB", (27, 1))
    image.putdata(VALUES)
    return image


def test_palette_matches_all_firmware_colour_numbers():
    levels = (0, 128, 255)
    assert len(VALUES) == len(set(VALUES)) == 27
    # Firmware colour = 9*green_level + 3*red_level + blue_level.
    for ink in range(27):
        assert VALUES[ink] == (levels[(ink // 3) % 3], levels[ink // 9], levels[ink % 3])
    assert CPC.colours[13].name == "white"  # Historical name: middle grey in ideal RGB.
    assert VALUES[13] == (128, 128, 128)
    assert CPC.colours[26].name == "bright-white"
    assert VALUES[26] == (255, 255, 255)


def test_pen_mapping_is_separate_from_firmware_indices():
    screen = CPCImage(2, 1, 2, (26, 0), ((0, 1),))
    assert rasterize_cpc(screen) == IndexedImage(2, 1, CPC, ((26, 0),))


@pytest.mark.parametrize("mode,limit", [(0, 16), (1, 4), (2, 2)])
@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_global_ink_limits_and_determinism(mode, limit, dither):
    source = palette_source()
    screen = optimise_cpc(source, mode=mode, dither=dither)
    assert 1 <= len(screen.inks) <= limit
    assert screen == optimise_cpc(source, mode=mode, dither=dither)
    raster = rasterize_cpc(screen)
    raster.validate()
    used = {index for row in raster.pixels for index in row}
    assert used <= set(screen.inks)
    assert len(used) <= limit  # Across the entire image, with no cell partition.
    undithered = optimise_cpc(source, mode=mode)
    assert screen.inks == undithered.inks
    local = Palette("selected", tuple(CPC.colours[i] for i in screen.inks))
    assert screen.pixels == quantize(source, local, dither).pixels


def test_known_inks_are_preserved_when_they_fit():
    source = Image.new("RGB", (4, 2))
    source.putdata([VALUES[i] for i in (0, 6, 18, 26) * 2])
    screen = optimise_cpc(source, mode=1)
    assert screen.inks == (0, 6, 18, 26)
    assert render_indexed(rasterize_cpc(screen)).tobytes() == source.tobytes()


@pytest.mark.parametrize("mode,width,aspect,scale", [(0, 160, 2.0, 2), (1, 320, 1.0, 2), (2, 640, 0.5, 1)])
def test_standard_geometry_and_matching_preview_sizes(tmp_path, mode, width, aspect, scale):
    profile = get_profile(f"cpc-mode{mode}")
    assert (profile.geometry.width, profile.geometry.height, profile.geometry.pixel_aspect) == (width, 200, aspect)
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    Image.new("RGB", (32, 20), VALUES[6]).save(src)
    indexed = convert_file(src, dst, profile_name=profile.name, cpc_mode="constrained", scale=scale)
    assert (indexed.width, indexed.height) == (width, 200)
    assert indexed.pixels == ((6,) * width,) * 200
    with Image.open(dst) as preview:
        assert preview.size == (640, 400)


def test_mode2_preview_retains_every_logical_column():
    # A horizontal downsample would destroy this alternating one-pixel detail.
    image = IndexedImage(640, 1, CPC, ((0, 26) * 320,))
    preview = render_indexed(image, pixel_aspect=0.5)
    assert preview.size == (640, 2)
    for y in range(2):
        assert [preview.getpixel((x, y)) for x in range(640)] == [VALUES[i] for i in image.pixels[0]]


@pytest.mark.parametrize("mode", [0, 1, 2])
@pytest.mark.parametrize("palette_name", ["cpc", "c64"])
def test_default_bitmap_is_unrestricted_and_allows_palette_swaps(tmp_path, mode, palette_name):
    source = palette_source()
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source.save(src)
    indexed = convert_file(src, dst, profile_name=f"cpc-mode{mode}", palette_name=palette_name,
                           width=27, height=1, fit="stretch", scale=1)
    palette = get_palette(palette_name)
    assert indexed == quantize(source, palette)
    if palette_name == "cpc":
        assert len(set(indexed.pixels[0])) == 27


@pytest.mark.parametrize("mode", [0, 1, 2])
@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_cli_with_colour_adjustments(tmp_path, mode, dither):
    source = palette_source()
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    source.save(src)
    subprocess.run([sys.executable, "-m", "retroimg.cli", "convert", str(src), str(dst),
                    "--profile", f"cpc-mode{mode}", "--cpc-mode", "constrained",
                    "--width", "27", "--height", "1", "--fit", "stretch", "--scale", "1",
                    "--dither", dither, "--hue-shift", "20", "--green-gain", "1.15"], check=True)
    adjusted = adjust_colours(source, hue_shift=20, green_gain=1.15)
    expected = rasterize_cpc(optimise_cpc(adjusted, mode=mode, dither=dither))
    aspect = get_profile(f"cpc-mode{mode}").geometry.pixel_aspect
    with Image.open(dst) as preview:
        assert preview.tobytes() == render_indexed(expected, pixel_aspect=aspect).tobytes()


@pytest.mark.parametrize("changes,match", [
    (dict(mode=3), "mode"), (dict(mode=True), "mode"),
    (dict(inks=()), "ink count"), (dict(inks=(0, 1, 2)), "ink count"),
    (dict(inks=(0, 27)), "firmware"), (dict(inks=(0, -1)), "firmware"),
    (dict(inks=(0, 0)), "unique"), (dict(pixels=((2, 0),)), "pen"),
    (dict(pixels=()), "grid"), (dict(width=0), "positive"),
    (dict(palette=get_palette("c64")), "cpc palette"),
])
def test_invalid_screen_models(changes, match):
    args = dict(width=2, height=1, mode=2, inks=(0, 26), pixels=((0, 1),))
    args.update(changes)
    with pytest.raises(ValueError, match=match):
        CPCImage(**args)


@pytest.mark.parametrize("kwargs,match", [
    (dict(cpc_mode="invalid"), "unknown CPC"),
    (dict(cpc_mode="constrained"), "only valid"),
    (dict(profile_name="cpc-mode0", cpc_mode="constrained", palette_name="c64"), "cpc palette"),
    (dict(profile_name="cpc-mode1", teletext_mode="mosaic"), "only valid"),
    (dict(profile_name="cpc-mode2", spectrum_mode="attributes"), "only valid"),
    (dict(profile_name="cpc-mode0", c64_mode="multicolour"), "only valid"),
])
def test_invalid_conversion_leaves_output_untouched(tmp_path, kwargs, match):
    src, dst = tmp_path / "in.png", tmp_path / "out.png"
    palette_source().save(src)
    with pytest.raises(ValueError, match=match):
        convert_file(src, dst, **kwargs)
    assert not dst.exists()


def test_invalid_dither():
    with pytest.raises(ValueError, match="dither"):
        optimise_cpc(palette_source(), dither="invalid")


def test_palette_selector_matches_exhaustive_weighted_pair_oracle():
    palette = Palette("grey", tuple(Colour(str(v), (v, v, v)) for v in (0, 60, 120, 180, 255)))
    source = Image.new("RGB", (8, 1))
    samples = [(v, v, v) for v in (10, 90, 90, 90, 90, 165, 240, 240)]
    source.putdata(samples)
    values = palette.rgb_values()
    def score(indices):
        return sum(min(colour_distance(sample, values[i]) for i in indices) for sample in samples)
    selected = select_palette_indices(source, palette, 2, max_samples=None)
    assert score(selected) == min(score(pair) for pair in combinations(range(len(values)), 2))
    assert score(select_palette_indices(source, palette, 1)) == min(score((i,)) for i in range(len(values)))


def test_histogram_frequencies_affect_selection():
    palette = Palette("grey", tuple(Colour(str(v), (v, v, v)) for v in (0, 128, 255)))
    source = Image.new("RGB", (102, 1))
    source.putdata([(0, 0, 0)] + [(128, 128, 128)] * 100 + [(255, 255, 255)])
    assert select_palette_indices(source, palette, 2, max_samples=3) == (0, 1)


def test_palette_swaps_improve_greedy_fit():
    palette = Palette("grey", tuple(Colour(str(v), (v, v, v)) for v in (0, 51, 102, 153, 204, 255)))
    samples = [(v, v, v) for v in (87, 42, 205, 214, 240, 244, 196, 15, 42, 98, 133, 182)]
    source = Image.new("RGB", (12, 1))
    source.putdata(samples)
    greedy = select_palette_indices(source, palette, 3, max_swaps=0)
    refined = select_palette_indices(source, palette, 3)
    def error(indices):
        return sum(min(colour_distance(rgb, palette.colours[i].rgb) for i in indices) for rgb in samples)
    assert error(refined) < error(greedy)
    assert refined == select_palette_indices(source, palette, 3)


def test_large_histogram_sampling_is_deterministic_and_respects_limits():
    source = Image.new("RGB", (100, 100))
    source.putdata([(i % 256, i // 256, (i * 19) % 256) for i in range(10000)])
    result = select_palette_indices(source, CPC, 4, max_samples=64)
    assert result == select_palette_indices(source, CPC, 4, max_samples=64)
    assert 1 <= len(result) <= 4
    assert all(0 <= index < 27 for index in result)


@pytest.mark.parametrize("kwargs", [dict(colour_limit=0), dict(max_samples=0), dict(max_samples=1.5), dict(max_swaps=-1)])
def test_invalid_selection_options(kwargs):
    args = dict(colour_limit=4)
    args.update(kwargs)
    with pytest.raises(ValueError):
        select_palette_indices(palette_source(), CPC, **args)


def test_selection_rejects_empty_inputs_and_accepts_a_small_palette():
    with pytest.raises(ValueError, match="positive"):
        select_palette_indices(Image.new("RGB", (0, 1)), CPC, 4)
    with pytest.raises(ValueError, match="palette"):
        select_palette_indices(palette_source(), Palette("empty", ()), 4)
    palette = Palette("small", (Colour("black", (0, 0, 0)), Colour("white", (255, 255, 255))))
    assert select_palette_indices(palette_source(), palette, 16) == (0, 1)
