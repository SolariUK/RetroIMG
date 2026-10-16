from __future__ import annotations

import math

from PIL import Image

from retroimg.model import IndexedImage
from retroimg.teletext import TeletextPage
from retroimg.spectrum import SpectrumImage, spectrum_index
from retroimg.c64 import C64MulticolourImage
from retroimg.cpc import CPCImage


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
    """Expand logical cell patterns without scaling or display effects."""
    pixels = []
    for cells in page.cells:
        for dy in range(3):
            row = []
            for cell in cells:
                for dx in range(2):
                    bit = dy * 2 + dx
                    row.append(cell.foreground if cell.pattern & (1 << bit) else cell.background)
            pixels.append(tuple(row))
    return IndexedImage(page.columns * 2, page.rows * 3, page.palette, tuple(pixels))


def rasterize_spectrum(image: SpectrumImage) -> IndexedImage:
    """Expand static ink/paper patterns without scaling or display effects."""
    pixels = []
    for cells in image.cells:
        for dy in range(8):
            row = []
            for cell in cells:
                ink = spectrum_index(cell.ink, cell.bright)
                paper = spectrum_index(cell.paper, cell.bright)
                row.extend(ink if cell.pattern & (1 << (dy * 8 + dx)) else paper
                           for dx in range(8))
            pixels.append(tuple(row))
    return IndexedImage(image.columns * 8, image.rows * 8, image.palette, tuple(pixels))


def rasterize_c64_multicolour(image: C64MulticolourImage) -> IndexedImage:
    """Expand two-bit selectors to a logical raster, retaining wide pixels."""
    pixels = []
    for cells in image.cells:
        for dy in range(8):
            row = []
            for cell in cells:
                colours = (image.background, *cell.colours)
                row.extend(colours[(cell.pattern >> (2 * (dy * 4 + dx))) & 3]
                           for dx in range(4))
            pixels.append(tuple(row))
    return IndexedImage(image.columns * 4, image.rows * 8, image.palette, tuple(pixels))


def rasterize_cpc(image: CPCImage) -> IndexedImage:
    """Map screen pens to firmware palette indices, without display scaling."""
    pixels = tuple(tuple(image.inks[pen] for pen in row) for row in image.pixels)
    return IndexedImage(image.width, image.height, image.palette, pixels)
