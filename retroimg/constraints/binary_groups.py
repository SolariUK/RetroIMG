"""Exact two-colour fitting when several source samples share one selector."""
from itertools import combinations_with_replacement

from retroimg.model import Palette, RGB
from retroimg.quantize import RGB_WEIGHTS


def fit_binary_groups(groups: tuple[tuple[RGB, ...], ...], palette: Palette
                      ) -> tuple[tuple[int, int], tuple[tuple[float, float, float], ...]]:
    """Return a minimum-error pair and group means, with stable palette ties.

    All samples in each group must use the same output colour. Sufficient
    statistics retain the original RGB squared-error objective, including
    unequal group sizes. Duplicate palette RGBs are searched only once.
    Target layout and dithering are independent of this fitter.
    """
    if not groups or any(not group for group in groups) or not palette.colours:
        raise ValueError("groups and palette must be non-empty")
    values = palette.rgb_values()
    unique = tuple(dict.fromkeys(values))
    indices = tuple(values.index(value) for value in unique)
    errors, means = [], []
    for group in groups:
        sums = tuple(sum(rgb[c] for rgb in group) for c in range(3))
        squares = tuple(sum(rgb[c] ** 2 for rgb in group) for c in range(3))
        means.append(tuple(value / len(group) for value in sums))
        errors.append(tuple(sum(weight * (squares[c] - 2 * rgb[c] * sums[c]
                                         + len(group) * rgb[c] ** 2)
                                for c, weight in enumerate(RGB_WEIGHTS)) for rgb in unique))
    best, best_score = (0, 0), float("inf")
    for a, b in combinations_with_replacement(range(len(unique)), 2):
        score = 0
        for row in errors:
            score += min(row[a], row[b])
            if score >= best_score:
                break
        if score < best_score:
            best, best_score = (indices[a], indices[b]), score
    return best, tuple(means)
