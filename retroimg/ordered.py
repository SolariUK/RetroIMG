"""Bayer thresholds and palette-aware ordered colour selection."""
from bisect import bisect_right
from functools import lru_cache

from retroimg.model import Palette, RGB
from retroimg.colour_spaces import RGB_WEIGHTS

BAYER_SIZES = (2, 4, 8)
DITHER_MODES = ("none", "floyd-steinberg", "bayer")


def validate_dither(dither: str, bayer_size: int = 4) -> None:
    if dither not in DITHER_MODES:
        raise ValueError(f"unknown dither mode: {dither}")
    if type(bayer_size) is not int or bayer_size not in BAYER_SIZES:
        raise ValueError("Bayer size must be 2, 4 or 8")


@lru_cache(maxsize=3)
def bayer_matrix(size: int = 4) -> tuple[tuple[int, ...], ...]:
    if type(size) is not int or size not in BAYER_SIZES:
        raise ValueError("Bayer size must be 2, 4 or 8")
    matrix = ((0, 2), (3, 1))
    while len(matrix) < size:
        n = len(matrix)
        matrix = tuple(tuple(4 * matrix[y % n][x % n] + ((0, 2), (3, 1))[y // n][x // n]
                             for x in range(n * 2)) for y in range(n * 2))
    return matrix


def bayer_threshold(x: int, y: int, size: int = 4) -> float:
    return (bayer_matrix(size)[y % size][x % size] + 0.5) / (size * size)


def ordered_pair(rgb: tuple[float, float, float], values: tuple[RGB, ...]
                 ) -> tuple[int, int, float]:
    """Choose a nearest-colour anchor and its best weighted-RGB mixing partner.

    This is a bounded heuristic, not a search of every possible colour pair.
    Project onto each segment from the anchor and minimise reconstruction error.
    Canonical index order keeps threshold orientation stable as anchors change.
    """
    if not values:
        raise ValueError("palette must contain at least one colour")
    wr, wg, wb = RGB_WEIGHTS
    distances = tuple(wr * (rgb[0] - r)**2 + wg * (rgb[1] - g)**2 + wb * (rgb[2] - b)**2
                      for r, g, b in values)
    anchor = min(range(len(values)), key=distances.__getitem__)
    r0, g0, b0 = values[anchor]
    er, eg, eb = rgb[0] - r0, rgb[1] - g0, rgb[2] - b0
    best, fraction, score, best_length = anchor, 0.0, distances[anchor], 0.0
    for index, (r, g, b) in enumerate(values):
        dr, dg, db = r - r0, g - g0, b - b0
        length = wr * dr * dr + wg * dg * dg + wb * db * db
        if not length:
            continue
        dot = wr * er * dr + wg * eg * dg + wb * eb * db
        t = max(0.0, min(1.0, dot / length))
        error = distances[anchor] - 2 * t * dot + t * t * length
        # Equally accurate mixtures prefer less colour separation, avoiding
        # extreme partners whose tiny coverage vanishes in small matrices.
        if error < score - 1e-9 or (abs(error - score) <= 1e-9 and length < best_length):
            best, fraction, score, best_length = index, t, error, length
    if anchor <= best:
        return anchor, best, fraction
    return best, anchor, 1 - fraction


def ordered_index(rgb: tuple[float, float, float], values: tuple[RGB, ...], threshold: float) -> int:
    a, b, fraction = ordered_pair(rgb, values)
    return b if threshold < fraction else a


def ordered_lookup(palette: Palette):
    """Build a cached lookup; full RGB grids use per-channel ordered rounding."""
    if palette.rgb_levels is not None:
        levels = palette.rgb_levels
        n = len(levels)
        def grid_lookup(rgb, threshold):
            result = 0
            for value in rgb:
                lower = max(0, min(n - 1, bisect_right(levels, value) - 1))
                upper = min(n - 1, lower + 1)
                fraction = ((value - levels[lower]) / (levels[upper] - levels[lower])
                            if upper != lower else 0)
                index = upper if threshold < fraction else lower
                result = result * n + index
            return result
        return grid_lookup
    values = palette.rgb_values()
    @lru_cache(maxsize=65536)
    def choices(rgb):
        return ordered_pair(rgb, values)
    def lookup(rgb, threshold):
        a, b, fraction = choices(rgb)
        return b if threshold < fraction else a
    return lookup
