"""Deterministic frequency-weighted RGB sampling for palette fitting."""
from collections import Counter

from PIL import Image
from retroimg.model import RGB


def rgb_histogram(image: Image.Image, max_samples: int | None) -> list[tuple[int, RGB]]:
    """Keep complete histograms when small; otherwise sample by RGB frequency.

    Weighted midpoint sampling of a sorted histogram avoids spatial aliasing
    and does not introduce blended colours. Rare colours can be omitted when
    sampling is required. Only palette selection uses this sample.
    """
    histogram = sorted(image.getcolors(maxcolors=image.width * image.height), key=lambda item: item[1])
    if max_samples is None or len(histogram) <= max_samples:
        return histogram
    total = image.width * image.height
    cumulative = 0
    sample = 0
    counts: Counter[RGB] = Counter()
    for count, rgb in histogram:
        cumulative += count
        while sample < max_samples and ((2 * sample + 1) * total) // (2 * max_samples) < cumulative:
            counts[rgb] += 1
            sample += 1
    return [(count, rgb) for rgb, count in sorted(counts.items())]

