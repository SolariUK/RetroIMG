from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image, ImageEnhance, ImageFilter

from retroimg.adjustments import adjust_colours
from retroimg.convert import convert_file
from retroimg.palettes import get_palette
from retroimg.quantize import quantize
from retroimg.targets.teletext import quantize_teletext_mosaic


def sample():
    image = Image.new("RGB", (2, 3))
    image.putdata([(255, 0, 0), (128, 128, 128), (0, 0, 0),
                   (120, 160, 40), (20, 90, 250), (255, 255, 255)])
    return image


def pixels(image):
    return [image.getpixel((x, y)) for y in range(image.height) for x in range(image.width)]


def test_neutral_and_existing_saturation_preserved():
    source = sample()
    assert adjust_colours(source).tobytes() == source.tobytes()
    assert adjust_colours(source, hue_shift=360).tobytes() == source.tobytes()
    assert adjust_colours(source, saturation=1.5).tobytes() == ImageEnhance.Color(source).enhance(1.5).tobytes()


def test_hue_and_gain_semantics():
    source = sample()
    shifted = adjust_colours(source, hue_shift=120)
    assert shifted.getpixel((0, 0)) == (0, 255, 0)
    assert shifted.getpixel((1, 0)) == (128, 128, 128)
    assert shifted.getpixel((0, 1)) == (0, 0, 0)
    assert adjust_colours(source, hue_shift=-240).tobytes() == shifted.tobytes()
    balanced = adjust_colours(source, red_gain=0.5, green_gain=1.2, blue_gain=0)
    assert balanced.getpixel((1, 1)) == (60, 192, 0)
    assert balanced.getpixel((1, 2)) == (128, 255, 0)


def test_brightness_scales_channels_and_accepts_zero():
    source = sample()
    assert adjust_colours(source, brightness=0.5).getpixel((1, 1)) == (60, 80, 20)
    assert adjust_colours(source, brightness=2).getpixel((1, 1)) == (240, 255, 80)
    assert set(pixels(adjust_colours(source, brightness=0))) == {(0, 0, 0)}
    assert source.getpixel((1, 1)) == (120, 160, 40)


def test_contrast_centres_on_mean_luminance_and_accepts_zero():
    source = Image.new('RGB', (5, 1))
    source.putdata([(v, v, v) for v in (0, 64, 128, 192, 255)])
    assert pixels(adjust_colours(source, contrast=2)) == [
        (v, v, v) for v in (0, 0, 128, 255, 255)]
    assert set(pixels(adjust_colours(source, contrast=0))) == {(128, 128, 128)}
    assert pixels(adjust_colours(source, contrast=0.5)) == [
        (v, v, v) for v in (64, 96, 128, 160, 191)]


def test_tone_controls_precede_existing_colour_controls():
    source = sample()
    toned = ImageEnhance.Contrast(ImageEnhance.Brightness(source).enhance(1.2)).enhance(1.3)
    kwargs = dict(saturation=1.1, hue_shift=20, red_gain=0.9, green_gain=1.15)
    assert adjust_colours(source, brightness=1.2, contrast=1.3, **kwargs).tobytes() == (
        adjust_colours(toned, **kwargs).tobytes())


def test_neutral_tone_controls_bypass_enhancement(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('neutral tone controls must bypass Pillow enhancement')
    monkeypatch.setattr(ImageEnhance, 'Brightness', unexpected)
    monkeypatch.setattr(ImageEnhance, 'Contrast', unexpected)
    source = sample()
    assert adjust_colours(source, brightness=1, contrast=1).tobytes() == source.tobytes()


def test_sharpen_strengthens_soft_edges_without_changing_flat_regions_or_source():
    source = Image.new('RGB', (24, 12), (96, 96, 96))
    source.paste((160, 160, 160), (12, 0, 24, 12))
    source = source.filter(ImageFilter.GaussianBlur(.8))
    before = source.tobytes()
    actual = adjust_colours(source, sharpen=1)
    assert actual.size == source.size and actual.mode == 'RGB'
    assert actual.getpixel((12, 6))[0] - actual.getpixel((11, 6))[0] > (
        source.getpixel((12, 6))[0] - source.getpixel((11, 6))[0])
    assert actual.getpixel((0, 6)) == source.getpixel((0, 6))
    assert actual.getpixel((23, 6)) == source.getpixel((23, 6))
    assert source.tobytes() == before
    flat = Image.new('RGB', (12, 12), (90, 140, 180))
    assert adjust_colours(flat, sharpen=4).tobytes() == flat.tobytes()


def test_zero_sharpen_bypasses_filter(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail('zero sharpening must bypass the filter')
    monkeypatch.setattr(ImageFilter, 'UnsharpMask', unexpected)
    source = sample()
    assert adjust_colours(source, sharpen=0).tobytes() == source.tobytes()


@pytest.mark.parametrize('kwargs', [dict(hue_shift=float('nan')), dict(hue_shift=float('inf')),
    dict(red_gain=-1), dict(green_gain=float('inf')), dict(blue_gain=float('nan')),
    dict(saturation=float('nan')),
    *[dict(sharpen=value) for value in (-.1, 4.1, float('nan'), float('inf'), -float('inf'))],
    *[{key: value} for key in ('brightness', 'contrast')
      for value in (-0.1, float('nan'), float('inf'), -float('inf'))]])
def test_invalid_adjustments(kwargs):
    with pytest.raises(ValueError):
        adjust_colours(sample(), **kwargs)


@pytest.mark.parametrize('mode', ['bitmap', 'mosaic'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg', 'bayer'])
def test_cli_adjusts_before_quantisation(tmp_path, mode, dither):
    source = sample()
    src, dst = tmp_path / 'source.png', tmp_path / 'result.png'
    source.save(src)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(src), str(dst),
                    '--width', '2', '--height', '3', '--scale', '1',
                    '--teletext-mode', mode, '--dither', dither, '--hue-shift', '10',
                    '--brightness', '1.1', '--contrast', '1.2',
                    '--sharpen', '1.25',
                    '--red-gain', '0.9', '--green-gain', '1.15', '--blue-gain', '1.05'], check=True)
    prepared = adjust_colours(source, brightness=1.1, contrast=1.2, hue_shift=10, sharpen=1.25,
                              red_gain=0.9, green_gain=1.15, blue_gain=1.05)
    palette = get_palette('teletext')
    expected = (quantize if mode == 'bitmap' else quantize_teletext_mosaic)(prepared, palette, dither)
    values = palette.rgb_values()
    with Image.open(dst) as actual:
        assert [actual.getpixel((x, y)) for y in range(3) for x in range(2)] == [values[i] for row in expected.pixels for i in row]


def test_sharpen_runs_at_logical_resolution_after_colour_adjustments(tmp_path):
    from retroimg.geometry import resize_to_geometry
    from retroimg.model import Geometry
    source = Image.new('RGB', (48, 36))
    source.putdata([((x * 19 + y * 7) % 256, (x * 11) % 256, (y * 29) % 256)
                    for y in range(36) for x in range(48)])
    src, dst = tmp_path / 'input.png', tmp_path / 'output.png'
    source.save(src)
    resized = resize_to_geometry(source, Geometry(16, 12))
    toned = adjust_colours(resized, brightness=1.1, red_gain=.9)
    reference = toned.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    expected = quantize_teletext_mosaic(reference, get_palette('amiga'))
    actual = convert_file(src, dst, width=16, height=12, teletext_mode='mosaic',
                          palette_name='amiga', brightness=1.1, red_gain=.9, sharpen=1.5, scale=1)
    assert actual == expected
    plain = quantize_teletext_mosaic(toned, get_palette('amiga'))
    assert actual.pixels != plain.pixels


def test_invalid_sharpen_is_rejected_before_opening_source(tmp_path):
    with pytest.raises(ValueError, match='sharpen'):
        convert_file(tmp_path / 'missing.png', tmp_path / 'output.png', sharpen=-1)
