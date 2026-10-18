"""Fit a small palette within a regular RGB grid, without target rules."""
from PIL import Image

from retroimg.colour_spaces import RGBGrid, RGBPaletteLookup
from retroimg.constraints.histogram import rgb_histogram
from retroimg.model import RGB
from retroimg.quantize import RGB_WEIGHTS, colour_distance


def fit_rgb_palette(
    image: Image.Image, grid: RGBGrid, colour_limit: int, *,
    max_samples: int | None = 4096, max_iterations: int = 12,
) -> tuple[RGB, ...]:
    """Weighted median-cut seeds and grid-snapped Lloyd refinement.

    Fit original RGB samples, weighted by frequency. Each cluster centre is
    the nearest grid colour to its weighted mean. This is a deterministic
    heuristic, not a global optimum. Sampling affects fitting only; callers
    should quantise the complete prepared source using the resulting palette.
    """
    if type(colour_limit) is not int or not 1 <= colour_limit <= len(grid.levels) ** 3:
        raise ValueError('colour limit must be a positive integer within RGB grid capacity')
    if max_samples is not None and (type(max_samples) is not int or max_samples <= 0):
        raise ValueError('max_samples must be a positive integer or None')
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError('max_iterations must be a non-negative integer')
    if image.width <= 0 or image.height <= 0:
        raise ValueError('image dimensions must be positive')
    samples = rgb_histogram(image.convert('RGB'), max_samples)
    nearest = tuple(sorted({grid.snap(rgb) for _, rgb in samples}))
    if len(nearest) <= colour_limit:
        return nearest

    def centre(box):
        count = sum(n for n, _ in box)
        return tuple(sum(n * rgb[c] for n, rgb in box) / count for c in range(3))

    def variance(box):
        mean = centre(box)
        return tuple(weight * sum(n * (rgb[c] - mean[c]) ** 2 for n, rgb in box)
                     for c, weight in enumerate(RGB_WEIGHTS))

    boxes = [samples]
    scores = [variance(samples)]
    while len(boxes) < colour_limit:
        index = max(range(len(boxes)), key=lambda i: (sum(scores[i]), -i))
        if sum(scores[index]) == 0:
            break
        channel = max(range(3), key=lambda c: (scores[index][c], -c))
        box = sorted(boxes.pop(index), key=lambda item: (item[1][channel], item[1]))
        scores.pop(index)
        total, cumulative, split = sum(n for n, _ in box), 0, 1
        for split, (n, _) in enumerate(box, 1):
            cumulative += n
            if cumulative * 2 >= total:
                break
        split = min(split, len(box) - 1)
        boxes.extend((box[:split], box[split:]))
        scores.extend((variance(box[:split]), variance(box[split:])))
    colours = tuple(sorted({grid.snap(centre(box)) for box in boxes}))
    # Snapping median-cut centres may merge them. Recover useful free slots
    # from the highest weighted residuals before refinement.
    snapped = [grid.snap(rgb) for _, rgb in samples]
    lookup = RGBPaletteLookup(colours)
    residuals = [lookup(rgb)[1] for _, rgb in samples]
    while len(colours) < colour_limit:
        candidates = [(n * error, snap) for (n, _), error, snap in zip(samples, residuals, snapped)
                      if snap not in colours]
        if not candidates:
            break
        _, extra = max(candidates, key=lambda item: (item[0], tuple(-v for v in item[1])))
        colours = tuple(sorted((*colours, extra)))
        residuals = [min(error, colour_distance(rgb, extra))
                     for (_, rgb), error in zip(samples, residuals)]

    def score(nearest):
        return sum(n * nearest(rgb)[1] for n, rgb in samples)

    lookup = RGBPaletteLookup(colours)
    error = score(lookup)
    for _ in range(max_iterations):
        clusters = [[] for _ in colours]
        for sample in samples:
            index = lookup(sample[1])[0]
            clusters[index].append(sample)
        updated = tuple(sorted({grid.snap(centre(cluster)) for cluster in clusters if cluster}))
        updated_lookup = RGBPaletteLookup(updated)
        updated_error = score(updated_lookup)
        if updated_error >= error:
            break
        colours, error, lookup = updated, updated_error, updated_lookup
    return colours
