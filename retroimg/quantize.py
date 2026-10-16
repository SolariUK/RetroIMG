from __future__ import annotations

from typing import Callable

from PIL import Image

from retroimg.model import IndexedImage, Palette, RGB
from retroimg.colour_spaces import RGBGrid

RGB_WEIGHTS = (3, 4, 2)


def colour_distance(a: tuple[float, float, float], b: RGB) -> float:
    # Same simple weighted RGB metric as the IRC prototype.
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return RGB_WEIGHTS[0] * dr * dr + RGB_WEIGHTS[1] * dg * dg + RGB_WEIGHTS[2] * db * db


def _colour_lookup(palette: Palette) -> Callable[[tuple[float, float, float]], int]:
    if palette.rgb_levels is not None:
        return RGBGrid(palette.rgb_levels).nearest_index
    values = palette.rgb_values()
    return lambda rgb: min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))


def nearest_index(rgb: tuple[float, float, float], palette: Palette) -> int:
    return _colour_lookup(palette)(rgb)


def quantize_none(image: Image.Image, palette: Palette) -> IndexedImage:
    image = image.convert("RGB")
    lookup = _colour_lookup(palette)
    pixels = tuple(
        tuple(lookup(image.getpixel((x, y))) for x in range(image.width))
        for y in range(image.height)
    )
    out = IndexedImage(image.width, image.height, palette, pixels)
    out.validate()
    return out


def quantize_floyd_steinberg(image: Image.Image, palette: Palette) -> IndexedImage:
    image = image.convert("RGB")
    w, h = image.size
    work = [[list(map(float, image.getpixel((x, y)))) for x in range(w)] for y in range(h)]
    result = [[0] * w for _ in range(h)]
    values = palette.rgb_values()
    lookup = _colour_lookup(palette)

    def add_error(x: int, y: int, err: tuple[float, float, float], scale: float) -> None:
        if 0 <= x < w and 0 <= y < h:
            for c in range(3):
                work[y][x][c] = max(0.0, min(255.0, work[y][x][c] + err[c] * scale))

    for y in range(h):
        for x in range(w):
            old = tuple(work[y][x])
            idx = lookup(old)
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


def quantize(image: Image.Image, palette: Palette, dither: str = "none") -> IndexedImage:
    if dither == "none":
        return quantize_none(image, palette)
    if dither == "floyd-steinberg":
        return quantize_floyd_steinberg(image, palette)
    raise ValueError(f"unknown dither mode: {dither}")
