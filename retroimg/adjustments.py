"""Optional source-image adjustments, independent of palettes and targets."""
from __future__ import annotations

import colorsys
import math

from PIL import Image, ImageEnhance, ImageFilter


MAX_SHARPEN = 4.0


def validate_sharpen(value: float) -> None:
    if not math.isfinite(value) or not 0 <= value <= MAX_SHARPEN:
        raise ValueError('sharpen must be finite and between 0 and 4')


def adjust_colours(
    image: Image.Image,
    *,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    hue_shift: float = 0.0,
    red_gain: float = 1.0,
    green_gain: float = 1.0,
    blue_gain: float = 1.0,
    sharpen: float = 0.0,
) -> Image.Image:
    """Apply tone/colour controls, then optional sharpening at the working size.

    Gains multiply channel values and clip to 0..255. Neutral settings bypass
    colour-space round trips, preserving existing conversion output exactly.
    """
    validate_sharpen(sharpen)
    for name, value in (('brightness', brightness), ('contrast', contrast)):
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")
    if not math.isfinite(saturation) or saturation <= 0:
        raise ValueError("saturation must be finite and positive")
    if not math.isfinite(hue_shift):
        raise ValueError("hue shift must be finite")
    gains = (red_gain, green_gain, blue_gain)
    if any(not math.isfinite(gain) or gain < 0 for gain in gains):
        raise ValueError("colour gains must be finite and non-negative")

    result = image.convert("RGB")
    if brightness != 1.0:
        result = ImageEnhance.Brightness(result).enhance(brightness)
    if contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(contrast)
    if saturation != 1.0:
        result = ImageEnhance.Color(result).enhance(saturation)
    rotation = (hue_shift % 360) / 360
    if rotation:
        pixels = []
        for y in range(result.height):
            for x in range(result.width):
                rgb = result.getpixel((x, y))
                h, s, v = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
                shifted = colorsys.hsv_to_rgb((h + rotation) % 1.0, s, v)
                pixels.append(tuple(round(channel * 255) for channel in shifted))
        result = Image.new("RGB", result.size)
        result.putdata(pixels)
    if gains != (1.0, 1.0, 1.0):
        channels = [channel.point([round(min(255, value * gain)) for value in range(256)])
                    for channel, gain in zip(result.split(), gains)]
        result = Image.merge("RGB", channels)
    if sharpen:
        result = result.filter(ImageFilter.UnsharpMask(radius=1, percent=round(100 * sharpen), threshold=3))
    return result
