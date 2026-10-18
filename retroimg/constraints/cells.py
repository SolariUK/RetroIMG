"""Reusable two-colour cell constraints, independent of target hardware."""
from __future__ import annotations

from bisect import bisect_left
from itertools import combinations_with_replacement

from PIL import Image

from retroimg.ordered import validate_dither

from retroimg.model import IndexedImage, Palette
from retroimg.quantize import colour_distance, quantize
from retroimg.colour_spaces import RGB_WEIGHTS


def _fit_small_grid_cell(samples, levels):
    """Exact pair search over sample partitions instead of Cartesian colours.

    For any assignment of samples to two colours, each group's optimum is its
    mean snapped to the RGB grid. Enumerating the assignments therefore covers
    the global pair optimum. Fixing the last sample in the second group removes
    symmetric assignments; an empty first group covers solid cells. Integer
    sufficient statistics retain exact error and lexicographic palette ties.
    """
    count = len(samples)
    total = tuple(sum(rgb[channel] for rgb in samples) for channel in range(3))
    size = len(levels)

    def fit_group(sums, number):
        if not number:
            return 0, 0  # An unused colour takes the earliest palette index.
        index, error = 0, 0
        for value, weight in zip(sums, RGB_WEIGHTS):
            upper = bisect_left(levels, (value + number - 1) // number)
            if upper == size or (upper and 2 * value <= number * (levels[upper - 1] + levels[upper])):
                upper -= 1
            colour = levels[upper]
            index = index * size + upper
            # Sum of squared source values is constant across all partitions.
            error += weight * (number * colour * colour - 2 * colour * value)
        return index, error

    sums = [(0, 0, 0)] * (1 << (count - 1))
    best_pair, best_error = (0, 0), float('inf')
    for mask in range(len(sums)):
        if mask:
            bit = mask & -mask
            previous, sample = sums[mask ^ bit], samples[bit.bit_length() - 1]
            sums[mask] = tuple(a + b for a, b in zip(previous, sample))
        number = mask.bit_count()
        left, left_error = fit_group(sums[mask], number)
        right, right_error = fit_group(tuple(a - b for a, b in zip(total, sums[mask])), count - number)
        pair = (left, right) if left <= right else (right, left)
        error = left_error + right_error
        if error < best_error or (error == best_error and pair < best_pair):
            best_pair, best_error = pair, error
    return best_pair


def quantize_cells(
    image: Image.Image,
    palette: Palette,
    *,
    cell_width: int,
    cell_height: int,
    dither: str = "none",
    bayer_size: int = 4,
    allowed_pairs: tuple[tuple[int, int], ...] | None = None,
) -> IndexedImage:
    """Fit at most two colours per cell directly to the RGB source.

    Exact unordered pair search minimises summed weighted RGB error. Small
    cells with large Cartesian palettes search equivalent sample partitions
    instead, avoiding the quadratic number of palette pairs.
    Equal scores retain palette order, making results reproducible. Dithering
    uses only the selected pair. Floyd–Steinberg resets at each cell boundary,
    so errors cannot leak into independently optimised neighbouring cells.
    Bayer retains global matrix phase across cell boundaries.

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
    validate_dither(dither, bayer_size)

    source = image.convert("RGB")
    values = palette.rgb_values()
    use_partitions = (allowed_pairs is None and palette.rgb_levels is not None
                      and cell_width * cell_height <= 8 and len(values) >= 32)
    if not use_partitions:
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
            pixels = cell.load()
            samples = tuple(pixels[x, y] for y in range(cell_height) for x in range(cell_width))
            if use_partitions:
                pair = _fit_small_grid_cell(samples, palette.rgb_levels)
            else:
                # Calculate each sample-to-colour distance once, rather than
                # for every candidate pair, including colours absent in source.
                errors = tuple(zip(*[
                    tuple(colour_distance(sample, value) for value in values)
                    for sample in samples
                ]))
                pair = min(
                    pairs,
                    key=lambda pair: sum([left if left < right else right for left, right in
                                          zip(errors[pair[0]], errors[pair[1]])]),
                )
            local_palette = Palette(
                name=palette.name,
                colours=tuple(palette.colours[index] for index in pair),
            )
            indexed = quantize(cell, local_palette, dither=dither, bayer_size=bayer_size,
                               bayer_origin=(x0, y0))
            for dy, row in enumerate(indexed.pixels):
                for dx, index in enumerate(row):
                    result[y0 + dy][x0 + dx] = pair[index]

    out = IndexedImage(source.width, source.height, palette, tuple(map(tuple, result)))
    out.validate()
    return out
