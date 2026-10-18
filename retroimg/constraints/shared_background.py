"""Machine-independent fitting of local colour sets with one shared colour."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from PIL import Image

from retroimg.model import Palette, RGB
from retroimg.quantize import colour_distance


@dataclass(frozen=True)
class SharedBackgroundFit:
    background: int
    colours: tuple[tuple[tuple[int, ...], ...], ...]


def _fit_cell(
    samples: tuple[RGB, ...], values: tuple[RGB, ...], colour_limit: int,
) -> tuple[tuple[float, tuple[int, ...]], ...]:
    """Find the best local set for every possible shared palette index."""
    errors = tuple(tuple(colour_distance(sample, rgb) for sample in samples) for rgb in values)
    nearest = tuple(min(range(len(values)), key=lambda i: errors[i][p])
                    for p in range(len(samples)))
    lower_bound = sum(errors[index][p] for p, index in enumerate(nearest))
    needed = set(nearest)
    best: list[tuple[float, tuple[int, ...]] | None] = [None] * len(values)
    unresolved = set()
    for background in range(len(values)):
        required = tuple(sorted(needed | {background}))
        if len(required) <= colour_limit:
            # This achieves unrestricted per-pixel error: no search can beat it.
            best[background] = (lower_bound, required)
        else:
            unresolved.add(background)

    if unresolved:
        pair_errors = {}
        def pair_costs(a, b):
            key = (a, b)
            if key not in pair_errors:
                pair_errors[key] = tuple(map(min, errors[a], errors[b]))
            return pair_errors[key]
        # Each set is scored once and contributes to every background it
        # contains. Enumerating full sets also covers solutions using fewer
        # colours: unused slots cannot increase minimum assignment error.
        for choice in combinations(range(len(values)), min(colour_limit, len(values))):
            relevant = unresolved.intersection(choice)
            if not relevant:
                continue
            if len(choice) == 4:
                score = sum([left if left < right else right for left, right in
                             zip(pair_costs(*choice[:2]), pair_costs(*choice[2:]))])
            else:
                score = (sum(errors[choice[0]]) if len(choice) == 1 else
                         sum(map(min, *(errors[index] for index in choice))))
            for background in relevant:
                previous = best[background]
                if previous is None or score < previous[0]:
                    best[background] = (score, choice)
    assert all(entry is not None for entry in best)
    return tuple(entry for entry in best if entry is not None)


def fit_shared_background(
    image: Image.Image,
    palette: Palette,
    *,
    cell_width: int,
    cell_height: int,
    colour_limit: int = 4,
) -> SharedBackgroundFit:
    """Exactly minimise undithered RGB error over a shared colour and cell sets.

    Every cell may use the shared palette index plus colour_limit-1 additional
    colours. The shared colour need not actually appear in a cell's pixels.
    All possible shared colours and local sets are considered. Ties select the
    lowest shared palette index; local selection is deterministic. This fitting
    stage precedes any optional dithering.
    """
    if any(type(size) is not int or size <= 0 for size in (cell_width, cell_height, colour_limit)):
        raise ValueError("cell dimensions and colour limit must be positive integers")
    if image.width <= 0 or image.height <= 0 or image.width % cell_width or image.height % cell_height:
        raise ValueError("image dimensions must be positive multiples of cell dimensions")
    if not palette.colours:
        raise ValueError("palette must contain at least one colour")
    source = image.convert("RGB")
    values = palette.rgb_values()
    totals = [0.0] * len(values)
    fits = []
    cache = {}
    for y in range(0, source.height, cell_height):
        row = []
        for x in range(0, source.width, cell_width):
            samples = tuple(source.getpixel((x + dx, y + dy))
                            for dy in range(cell_height) for dx in range(cell_width))
            if samples not in cache:
                cache[samples] = _fit_cell(samples, values, colour_limit)
            candidates = cache[samples]
            for index, (score, _) in enumerate(candidates):
                totals[index] += score
            row.append(candidates)
        fits.append(row)
    background = min(range(len(values)), key=lambda index: totals[index])
    colours = tuple(tuple(candidates[background][1] for candidates in row) for row in fits)
    return SharedBackgroundFit(background, colours)
