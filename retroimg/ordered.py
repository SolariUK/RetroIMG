"""Bayer thresholds and palette-aware ordered colour selection."""
from bisect import bisect_right
from functools import lru_cache

from retroimg.model import Palette, RGB
from retroimg.colour_spaces import RGBPaletteLookup, RGB_WEIGHTS

BAYER_SIZES = (2, 4, 8)
DITHER_MODES = ("none", "floyd-steinberg", "bayer")
MIXING_CONTRAST_WEIGHT = 0.25


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


def ordered_pair(rgb: tuple[float, float, float], values: tuple[RGB, ...], *, bayer_size: int = 4
                 ) -> tuple[int, int, float]:
    """Choose a nearest-colour anchor and its best weighted-RGB mixing partner.

    This is a bounded heuristic, not a search of every possible colour pair.
    Score realizable matrix coverage, balancing mean colour error against
    contrast beyond the anchor's nearest available colour spacing. Adjacent
    shades and two-colour palettes retain ordinary ordered rounding.
    Canonical index order keeps threshold orientation stable as anchors change.
    """
    if not values:
        raise ValueError("palette must contain at least one colour")
    validate_dither('bayer', bayer_size)
    return _ordered_pair(rgb, values, bayer_size, lambda anchor: _anchor_geometry(values, anchor))


def _anchor_geometry(values, anchor):
    r0, g0, b0 = values[anchor]
    wr, wg, wb = RGB_WEIGHTS
    segments = tuple((r - r0, g - g0, b - b0) for r, g, b in values)
    lengths = tuple(wr * dr * dr + wg * dg * dg + wb * db * db for dr, dg, db in segments)
    spacing = min((length for length in lengths if length), default=0)
    return tuple((index, *segment, length, max(0, length - spacing))
                 for index, (segment, length) in enumerate(zip(segments, lengths)) if length)


def _ordered_pair(rgb, values, bayer_size, geometry, nearest=None):
    coverage_steps = bayer_size * bayer_size
    wr, wg, wb = RGB_WEIGHTS
    if nearest is not None and all(type(value) is int for value in rgb):
        anchor, anchor_error = nearest(rgb)
    else:
        distances = tuple(wr * (rgb[0] - r)**2 + wg * (rgb[1] - g)**2 + wb * (rgb[2] - b)**2
                          for r, g, b in values)
        anchor = min(range(len(values)), key=distances.__getitem__)
        anchor_error = distances[anchor]
    r0, g0, b0 = values[anchor]
    er, eg, eb = rgb[0] - r0, rgb[1] - g0, rgb[2] - b0
    best, fraction, score, best_length = anchor, 0.0, anchor_error, 0.0
    for index, dr, dg, db, length, excess in geometry(anchor):
        dot = wr * er * dr + wg * eg * dg + wb * eb * db
        # E(t)-E(0) = t*(penalty-2*dot) + t*t*(length-penalty).
        # Both terms are non-negative here, so this partner cannot improve
        # the anchor at any coverage. This prunes distant, high-contrast pairs
        # without reducing the palette or approximating the Bayer objective.
        if 2 * dot <= MIXING_CONTRAST_WEIGHT * excess:
            continue
        t = max(0.0, min(1.0, dot / length))
        t = round(t * coverage_steps) / coverage_steps
        error = anchor_error - 2 * t * dot + t * t * length
        # Mixing variance measures speckle contrast. Subtract the local palette
        # spacing so sparse palettes still dither and nearby shade ramps remain
        # smooth, while isolated black/white flecks need a worthwhile benefit.
        error += MIXING_CONTRAST_WEIGHT * t * (1 - t) * excess
        if error < score - 1e-9 or (abs(error - score) <= 1e-9 and length < best_length):
            best, fraction, score, best_length = index, t, error, length
    if anchor <= best:
        return anchor, best, fraction
    return best, anchor, 1 - fraction


def ordered_index(rgb: tuple[float, float, float], values: tuple[RGB, ...], threshold: float,
                  *, bayer_size: int = 4) -> int:
    a, b, fraction = ordered_pair(rgb, values, bayer_size=bayer_size)
    return b if threshold < fraction else a


def ordered_lookup(palette: Palette, *, bayer_size: int = 4):
    """Build a cached lookup; full RGB grids use per-channel ordered rounding."""
    validate_dither('bayer', bayer_size)
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
    nearest = RGBPaletteLookup(values) if len(values) >= 16 else None
    @lru_cache(maxsize=128)
    def geometry(anchor):
        return _anchor_geometry(values, anchor)
    @lru_cache(maxsize=65536)
    def choices(rgb):
        return _ordered_pair(rgb, values, bayer_size, geometry, nearest)
    def lookup(rgb, threshold):
        a, b, fraction = choices(rgb)
        return b if threshold < fraction else a
    return lookup
