from __future__ import annotations

from typing import Callable

from PIL import Image

from retroimg.model import IndexedImage, Palette, RGB
from retroimg.colour_spaces import RGBGrid, RGB_WEIGHTS, colour_distance
from retroimg.ordered import bayer_threshold, ordered_lookup, validate_dither

PixelLookup = Callable[[int, int, tuple[float, float, float]], int]


def _colour_lookup(palette: Palette) -> Callable[[tuple[float, float, float]], int]:
    if palette.rgb_levels is not None:
        return RGBGrid(palette.rgb_levels).nearest_index
    values = palette.rgb_values()
    return lambda rgb: min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))


def nearest_index(rgb: tuple[float, float, float], palette: Palette) -> int:
    return _colour_lookup(palette)(rgb)


def quantize_none(image: Image.Image, palette: Palette, *, pixel_lookup: PixelLookup | None = None) -> IndexedImage:
    image = image.convert("RGB")
    nearest = _colour_lookup(palette)
    lookup = pixel_lookup if pixel_lookup is not None else lambda x, y, rgb: nearest(rgb)
    pixels = tuple(
        tuple(lookup(x, y, image.getpixel((x, y))) for x in range(image.width))
        for y in range(image.height)
    )
    out = IndexedImage(image.width, image.height, palette, pixels)
    out.validate()
    return out


def quantize_floyd_steinberg(image: Image.Image, palette: Palette, *, pixel_lookup: PixelLookup | None = None) -> IndexedImage:
    image = image.convert("RGB")
    w, h = image.size
    work = [[list(map(float, image.getpixel((x, y)))) for x in range(w)] for y in range(h)]
    result = [[0] * w for _ in range(h)]
    values = palette.rgb_values()
    nearest = _colour_lookup(palette)
    lookup = pixel_lookup if pixel_lookup is not None else lambda x, y, rgb: nearest(rgb)

    def add_error(x: int, y: int, err: tuple[float, float, float], scale: float) -> None:
        if 0 <= x < w and 0 <= y < h:
            for c in range(3):
                work[y][x][c] = max(0.0, min(255.0, work[y][x][c] + err[c] * scale))

    for y in range(h):
        for x in range(w):
            old = tuple(work[y][x])
            idx = lookup(x, y, old)
            new = values[idx]
            result[y][x] = idx
            err = tuple(old[c] - new[c] for c in range(3))
            add_error(x + 1, y, err, 7 / 16)
            add_error(x - 1, y + 1, err, 3 / 16)
            add_error(x, y + 1, err, 5 / 16)
            add_error(x + 1, y + 1, err, 1 / 16)

    out = IndexedImage(w, h, palette, tuple(tuple(row) for row in result))
    out.validate()
    return out


def quantize_bayer(image: Image.Image, palette: Palette, *, bayer_size: int = 4,
                   bayer_origin: tuple[int, int] = (0, 0),
                   pixel_lookup: PixelLookup | None = None) -> IndexedImage:
    """Ordered rounding; custom lookups own their position-aware Bayer choice."""
    validate_dither("bayer", bayer_size)
    source = image.convert("RGB")
    lookup = ordered_lookup(palette)
    ox, oy = bayer_origin
    pixels = tuple(tuple(
        pixel_lookup(x, y, source.getpixel((x, y))) if pixel_lookup is not None
        else lookup(source.getpixel((x, y)), bayer_threshold(x + ox, y + oy, bayer_size))
        for x in range(source.width)) for y in range(source.height))
    result = IndexedImage(source.width, source.height, palette, pixels)
    result.validate()
    return result


def quantize(image: Image.Image, palette: Palette, dither: str = "none", *,
             pixel_lookup: PixelLookup | None = None, bayer_size: int = 4,
             bayer_origin: tuple[int, int] = (0, 0)) -> IndexedImage:
    """Quantise with shared diffusion or palette-aware ordered dithering."""
    validate_dither(dither, bayer_size)
    if dither == "none":
        return quantize_none(image, palette, pixel_lookup=pixel_lookup)
    if dither == "floyd-steinberg":
        return quantize_floyd_steinberg(image, palette, pixel_lookup=pixel_lookup)
    return quantize_bayer(image, palette, pixel_lookup=pixel_lookup,
                          bayer_size=bayer_size, bayer_origin=bayer_origin)
