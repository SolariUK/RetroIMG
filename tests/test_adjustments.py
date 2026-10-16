from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image, ImageEnhance

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


@pytest.mark.parametrize('kwargs', [dict(hue_shift=float('nan')), dict(hue_shift=float('inf')),
    dict(red_gain=-1), dict(green_gain=float('inf')), dict(blue_gain=float('nan')),
    dict(saturation=float('nan'))])
def test_invalid_adjustments(kwargs):
    with pytest.raises(ValueError):
        adjust_colours(sample(), **kwargs)


@pytest.mark.parametrize('mode', ['bitmap', 'mosaic'])
@pytest.mark.parametrize('dither', ['none', 'floyd-steinberg'])
def test_cli_adjusts_before_quantisation(tmp_path, mode, dither):
    source = sample()
    src, dst = tmp_path / 'source.png', tmp_path / 'result.png'
    source.save(src)
    subprocess.run([sys.executable, '-m', 'retroimg.cli', 'convert', str(src), str(dst),
                    '--width', '2', '--height', '3', '--scale', '1',
                    '--teletext-mode', mode, '--dither', dither, '--hue-shift', '10',
                    '--red-gain', '0.9', '--green-gain', '1.15', '--blue-gain', '1.05'], check=True)
    prepared = adjust_colours(source, hue_shift=10, red_gain=0.9, green_gain=1.15, blue_gain=1.05)
    palette = get_palette('teletext')
    expected = (quantize if mode == 'bitmap' else quantize_teletext_mosaic)(prepared, palette, dither)
    values = palette.rgb_values()
    with Image.open(dst) as actual:
        assert [actual.getpixel((x, y)) for y in range(3) for x in range(2)] == [values[i] for row in expected.pixels for i in row]
