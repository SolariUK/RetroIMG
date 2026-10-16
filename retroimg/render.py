from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PIL import Image

from retroimg.model import IndexedImage


if TYPE_CHECKING:
    from retroimg.targets.teletext import TeletextPage
    from retroimg.targets.spectrum import SpectrumImage
    from retroimg.targets.c64 import C64MulticolourImage
    from retroimg.targets.cpc import CPCImage


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


def rasterize_teletext(page: TeletextPage) -> IndexedImage:
    """Compatibility entry point; prefer retroimg.targets.teletext.rasterize_teletext."""
    from retroimg.targets.teletext import rasterize_teletext as implementation
    return implementation(page)


def rasterize_spectrum(image: SpectrumImage) -> IndexedImage:
    """Compatibility entry point; prefer retroimg.targets.spectrum.rasterize_spectrum."""
    from retroimg.targets.spectrum import rasterize_spectrum as implementation
    return implementation(image)


def rasterize_c64_multicolour(image: C64MulticolourImage) -> IndexedImage:
    """Compatibility entry point; prefer retroimg.targets.c64.rasterize_c64_multicolour."""
    from retroimg.targets.c64 import rasterize_c64_multicolour as implementation
    return implementation(image)


def rasterize_cpc(image: CPCImage) -> IndexedImage:
    """Compatibility entry point; prefer retroimg.targets.cpc.rasterize_cpc."""
    from retroimg.targets.cpc import rasterize_cpc as implementation
    return implementation(image)
