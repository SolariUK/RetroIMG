"""Reusable two-colour cell constraints, independent of target hardware."""
from __future__ import annotations

from itertools import combinations_with_replacement

from PIL import Image

from retroimg.model import IndexedImage, Palette
from retroimg.quantize import colour_distance, quantize


def quantize_cells(
    image: Image.Image,
    palette: Palette,
    *,
    cell_width: int,
    cell_height: int,
    dither: str = "none",
    allowed_pairs: tuple[tuple[int, int], ...] | None = None,
) -> IndexedImage:
    """Fit at most two colours per cell directly to the RGB source.

    Exhaustive unordered pair search minimises summed weighted RGB error.
    Equal scores retain palette order, making results reproducible. Dithering
    uses only the selected pair and resets at each cell boundary, so errors
    cannot leak into independently optimised neighbouring cells.

    Targets may supply legal palette-index pairs (including solid pairs).
    Candidate order breaks ties; by default all unordered pairs are searched.
    This is a reusable visual constraint, not a machine's attribute or control
    code encoder. Such rules belong in target-specific constraint layers.
    """
    if cell_width <= 0 or cell_height <= 0:
        raise ValueError("cell dimensions must be positive")
    if image.width % cell_width or image.height % cell_height:
        raise ValueError("image dimensions must be divisible by cell dimensions")
    if not palette.colours:
        raise ValueError("palette must contain at least one colour")
    if dither not in {"none", "floyd-steinberg"}:
        raise ValueError(f"unknown dither mode: {dither}")

    source = image.convert("RGB")
    values = palette.rgb_values()
    pairs = (tuple(combinations_with_replacement(range(len(values)), 2))
             if allowed_pairs is None else allowed_pairs)
    if not pairs or any(
        len(pair) != 2 or any(type(index) is not int or not 0 <= index < len(values)
                              for index in pair)
        for pair in pairs
    ):
        raise ValueError("allowed pairs must contain valid palette-index pairs")
    result = [[0] * source.width for _ in range(source.height)]
    for y0 in range(0, source.height, cell_height):
        for x0 in range(0, source.width, cell_width):
            cell = source.crop((x0, y0, x0 + cell_width, y0 + cell_height))
            # Calculate each sample-to-colour distance once, rather than for
            # every candidate pair. Search all colours, including absent ones.
            errors = [
                tuple(colour_distance(sample, value) for value in values)
                for sample in (cell.getpixel((x, y))
                               for y in range(cell_height) for x in range(cell_width))
            ]
            pair = min(
                pairs,
                key=lambda pair: sum(min(row[pair[0]], row[pair[1]]) for row in errors),
            )
            local_palette = Palette(
                name=palette.name,
                colours=tuple(palette.colours[index] for index in pair),
            )
            indexed = quantize(cell, local_palette, dither=dither)
            for dy, row in enumerate(indexed.pixels):
                for dx, index in enumerate(row):
                    result[y0 + dy][x0 + dx] = pair[index]

    out = IndexedImage(source.width, source.height, palette, tuple(map(tuple, result)))
    out.validate()
    return out
