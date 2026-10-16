"""Regular RGB colour spaces, independent of display targets."""
from bisect import bisect_left
from dataclasses import dataclass
from itertools import product

from retroimg.model import Colour, Palette, RGB


@dataclass(frozen=True)
class RGBGrid:
    """Cartesian RGB grid with equal channel levels and red-major ordering."""

    levels: tuple[int, ...]

    def __post_init__(self) -> None:
        if (not self.levels or any(type(v) is not int or not 0 <= v <= 255 for v in self.levels)
                or tuple(sorted(set(self.levels))) != self.levels):
            raise ValueError('RGB levels must be sorted unique integers in 0..255')

    def _channel(self, value: float) -> int:
        upper = bisect_left(self.levels, value)
        if upper == 0:
            return 0
        if upper == len(self.levels):
            return upper - 1
        # Ties choose the lower palette index, like exhaustive quantisation.
        return upper - 1 if value - self.levels[upper - 1] <= self.levels[upper] - value else upper

    def nearest_index(self, rgb: tuple[float, float, float]) -> int:
        size = len(self.levels)
        r, g, b = (self._channel(value) for value in rgb)
        return (r * size + g) * size + b

    def snap(self, rgb: tuple[float, float, float]) -> RGB:
        r, g, b = (self.levels[self._channel(value)] for value in rgb)
        return r, g, b

    def palette(self, name: str, description: str = '') -> Palette:
        colours = tuple(Colour(f'rgb-{r:02x}{g:02x}{b:02x}', (r, g, b))
                        for r, g, b in product(self.levels, repeat=3))
        return Palette(name, colours, description, rgb_levels=self.levels)
