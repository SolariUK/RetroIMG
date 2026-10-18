"""Exact palette acceleration retains weighted error and palette index ties."""
from random import Random

from PIL import Image
import pytest

from retroimg.colour_spaces import RGBPaletteLookup, RGBPaletteTree, colour_distance, palette_errors
from retroimg.model import Colour, Palette
from retroimg.palettes.atari import ATARI_NTSC, ATARI_PAL
from retroimg.palettes.ega import EGA_DEFAULT
from retroimg.quantize import quantize


@pytest.mark.parametrize('palette', [ATARI_NTSC, ATARI_PAL, EGA_DEFAULT,
    Palette('ties', tuple(Colour(str(i), rgb) for i, rgb in enumerate(
        ((0, 0, 0), (2, 2, 2), (255, 255, 255), (0, 0, 0)))))])
def test_integer_lookup_matches_exhaustive_weighted_rgb_search(palette):
    random = Random(2600)
    values = palette.rgb_values()
    samples = [(0, 0, 0), (255, 255, 255), (1, 1, 1), *values,
               *(tuple(random.randrange(256) for _ in range(3)) for _ in range(250))]
    lookup = RGBPaletteLookup(values)
    for rgb in samples:
        expected = min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))
        assert lookup(rgb) == (expected, colour_distance(rgb, values[expected]))


@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
@pytest.mark.parametrize('palette', [ATARI_PAL, EGA_DEFAULT])
def test_palette_quantization_keeps_exhaustive_reference_pixels(dither, palette):
    random = Random(128)
    image = Image.new('RGB', (16, 12))
    image.putdata([tuple(random.randrange(256) for _ in range(3)) for _ in range(16 * 12)])
    values = palette.rgb_values()
    def exhaustive(x, y, rgb):
        return min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))
    assert quantize(image, palette, dither) == quantize(
        image, palette, dither, pixel_lookup=exhaustive)


@pytest.mark.parametrize('count', [16, 128, 256])
def test_spatial_search_matches_exhaustive_fractional_rgb_and_ties(count):
    from math import inf, nextafter
    random = Random(count)
    values = tuple(tuple(random.randrange(256) for _ in range(3)) for _ in range(count - 2))
    values += (values[0], values[1])
    tree = RGBPaletteTree(values)
    samples = [tuple(random.random() * 255 for _ in range(3)) for _ in range(400)]
    samples.extend(values)
    for a, b in zip(values[:12], values[1:13]):
        middle = tuple((x + y) / 2 for x, y in zip(a, b))
        samples.extend((middle, (nextafter(middle[0], -inf), *middle[1:]),
                        (nextafter(middle[0], inf), *middle[1:])))
    for rgb in samples:
        assert tree.nearest_index(rgb) == min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))


@pytest.mark.parametrize('fallback', [False, True])
def test_batched_integer_errors_match_exhaustive_metric(monkeypatch, fallback):
    from PIL import ImageMath
    if fallback:
        monkeypatch.delattr(ImageMath, 'lambda_eval', raising=False)
    random = Random(16)
    values = EGA_DEFAULT.rgb_values()
    samples = ((0, 0, 0), (255, 255, 255), *((tuple(random.randrange(256) for _ in range(3))) for _ in range(5000)))
    actual = palette_errors(samples, values)
    assert actual == tuple(min(colour_distance(rgb, value) for value in values) for rgb in samples)


def test_batched_errors_keep_chunk_boundaries_and_maximum_rgb_error():
    samples = tuple((index % 256, index * 37 % 256, index * 71 % 256) for index in range(65539))
    assert palette_errors(samples, ((255, 255, 255),)) == tuple(
        colour_distance(rgb, (255, 255, 255)) for rgb in samples)
    assert palette_errors(((0, 0, 0),), ((255, 255, 255),)) == (585225,)
