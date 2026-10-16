from __future__ import annotations

import math

from PIL import Image

from retroimg.model import IndexedImage


def render_indexed(
    image: IndexedImage, scale: int = 1, *, nearest: bool = True, pixel_aspect: float = 1.0
) -> Image.Image:
    """Render with optional aspect correction by enlarging the longer axis.

    Narrow logical pixels are represented by taller preview pixels rather
    than downsampling away logical columns, even at scale 1.
    """
    image.validate()
    if scale <= 0:
        raise ValueError("scale must be positive")
    if not math.isfinite(pixel_aspect) or pixel_aspect <= 0:
        raise ValueError("pixel aspect must be finite and positive")

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
    return out
