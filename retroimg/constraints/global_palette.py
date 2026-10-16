"""Deterministic, machine-independent selection from a fixed colour palette."""
from __future__ import annotations

from itertools import combinations

from PIL import Image

from retroimg.model import Palette
from retroimg.constraints.histogram import rgb_histogram as _histogram
from retroimg.quantize import colour_distance


def select_palette_indices(
    image: Image.Image,
    palette: Palette,
    colour_limit: int,
    *,
    max_samples: int | None = 4096,
    max_swaps: int = 8,
) -> tuple[int, ...]:
    """Choose at most colour_limit colours against weighted source RGB error.

    One/two-colour selection is exhaustive on the fitting histogram. Larger
    selections use greedy additions followed by up to max_swaps improving
    one-colour swaps; they are not guaranteed global optima. Ties are stable
    in palette order. Set max_samples=None to fit the complete RGB histogram.
    Quantisation/dithering should still use the full original image.
    """
    if type(colour_limit) is not int or colour_limit <= 0:
        raise ValueError("colour limit must be a positive integer")
    if max_samples is not None and (type(max_samples) is not int or max_samples <= 0):
        raise ValueError("max_samples must be a positive integer or None")
    if type(max_swaps) is not int or max_swaps < 0:
        raise ValueError("max_swaps must be a non-negative integer")
    if not palette.colours:
        raise ValueError("palette must contain at least one colour")
    if image.width <= 0 or image.height <= 0:
        raise ValueError("image dimensions must be positive")
    values = palette.rgb_values()
    limit = min(colour_limit, len(values))
    if limit == len(values):
        return tuple(range(len(values)))
    histogram = _histogram(image.convert("RGB"), max_samples)
    errors = tuple(tuple(count * colour_distance(rgb, value) for count, rgb in histogram)
                   for value in values)
    count = len(histogram)

    def costs(indices: tuple[int, ...]) -> tuple[float, ...]:
        if len(indices) == 1:
            return errors[indices[0]]
        return tuple(map(min, *(errors[index] for index in indices)))

    nearest = tuple(min(range(len(values)), key=lambda i: errors[i][p]) for p in range(count))
    needed = tuple(sorted(set(nearest)))
    if len(needed) <= limit:
        return needed

    first = min(range(len(values)), key=lambda i: sum(errors[i]))
    selected = (first,)
    current = errors[first]
    score = sum(current)
    if limit == 1:
        return selected
    if limit == 2:
        for pair in combinations(range(len(values)), 2):
            candidate_score = sum(map(min, errors[pair[0]], errors[pair[1]]))
            if candidate_score < score:
                selected, score = pair, candidate_score
        return selected

    while len(selected) < limit:
        candidate = min(
            (i for i in range(len(values)) if i not in selected),
            key=lambda i: (sum(map(min, current, errors[i])), i),
        )
        improved = tuple(map(min, current, errors[candidate]))
        if sum(improved) >= score:
            break
        selected = tuple(sorted((*selected, candidate)))
        current, score = improved, sum(improved)

    for _ in range(max_swaps):
        best_score, best_set = score, selected
        outside = tuple(i for i in range(len(values)) if i not in selected)
        for removed in selected:
            remaining = tuple(i for i in selected if i != removed)
            if not remaining:
                continue
            base = costs(remaining)
            for added in outside:
                candidate_score = sum(map(min, base, errors[added]))
                candidate_set = tuple(sorted((*remaining, added)))
                if (candidate_score, candidate_set) < (best_score, best_set):
                    best_score, best_set = candidate_score, candidate_set
        if best_score >= score:
            break
        selected, score = best_set, best_score
    return selected
