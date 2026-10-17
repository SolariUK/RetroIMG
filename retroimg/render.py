from __future__ import annotations

import math

from PIL import Image

from retroimg.model import IndexedImage
from retroimg.display_effects import gameboy_lcd, scanlines, validate_display_effect


def render_indexed(
    image: IndexedImage, scale: int = 1, *, nearest: bool = True, pixel_aspect: float = 1.0,
    display_effect: str = 'none', effect_strength: float | None = None,
) -> Image.Image:
    """Render with optional aspect correction by enlarging the longer axis.

    Narrow logical pixels are represented by taller preview pixels rather
    than downsampling away logical columns, even at scale 1.
    Optional display effects modify only the enlarged RGB result, after scaling.
    """
    image.validate()
    if scale <= 0:
        raise ValueError("scale must be positive")
    if not math.isfinite(pixel_aspect) or pixel_aspect <= 0:
        raise ValueError("pixel aspect must be finite and positive")
    strength = validate_display_effect(display_effect, effect_strength, scale)

    palette = image.palette.rgb_values()
    out = Image.new("RGB", (image.width, image.height))
    px = out.load()
    for y, row in enumerate(image.pixels):
        for x, index in enumerate(row):
            px[x, y] = palette[index]

    if scale != 1 or pixel_aspect != 1.0:
        resample = Image.Resampling.NEAREST if nearest else Image.Resampling.BICUBIC
        preview_width = max(1, round(out.width * scale * max(1.0, pixel_aspect)))
        preview_height = max(1, round(out.height * scale * max(1.0, 1.0 / pixel_aspect)))
        out = out.resize((preview_width, preview_height), resample)
    if display_effect == 'gameboy-lcd':
        background = max(palette, key=lambda rgb: 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
        out = gameboy_lcd(out, (image.width, image.height), background, strength)
    elif display_effect == 'scanlines':
        out = scanlines(out, image.height, strength)
    return out
