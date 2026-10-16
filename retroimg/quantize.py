from __future__ import annotations

from PIL import Image

from retroimg.model import IndexedImage, Palette, RGB


def colour_distance(a: tuple[float, float, float], b: RGB) -> float:
    # Same simple weighted RGB metric as the IRC prototype.
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return 3 * dr * dr + 4 * dg * dg + 2 * db * db


def nearest_index(rgb: tuple[float, float, float], palette: Palette) -> int:
    values = palette.rgb_values()
    return min(range(len(values)), key=lambda i: colour_distance(rgb, values[i]))


def quantize_none(image: Image.Image, palette: Palette) -> IndexedImage:
    image = image.convert("RGB")
    pixels = tuple(
        tuple(nearest_index(image.getpixel((x, y)), palette) for x in range(image.width))
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

    def add_error(x: int, y: int, err: tuple[float, float, float], scale: float) -> None:
        if 0 <= x < w and 0 <= y < h:
            for c in range(3):
                work[y][x][c] = max(0.0, min(255.0, work[y][x][c] + err[c] * scale))

    for y in range(h):
        for x in range(w):
            old = tuple(work[y][x])
            idx = min(range(len(values)), key=lambda i: colour_distance(old, values[i]))
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
