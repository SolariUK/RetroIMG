"""Regular RGB colour spaces, independent of display targets."""
from bisect import bisect_left
from dataclasses import dataclass
from itertools import product

from retroimg.model import Colour, Palette, RGB


RGB_WEIGHTS = (3, 4, 2)


def colour_distance(a: tuple[float, float, float], b: RGB) -> float:
    # Same simple weighted RGB metric as the IRC prototype.
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return RGB_WEIGHTS[0] * dr * dr + RGB_WEIGHTS[1] * dg * dg + RGB_WEIGHTS[2] * db * db


class RGBPaletteLookup:
    """Exact nearest palette search for integer RGB samples, with stable ties.

    Reuse the three small channel-error tables across samples instead of
    recalculating squared distances for every pixel and palette entry.
    Floating-point diffusion samples should use ``colour_distance`` directly.
    """

    def __init__(self, values: tuple[RGB, ...]):
        if not values:
            raise ValueError('palette must contain at least one colour')
        self.red, self.green, self.blue = (
            tuple(tuple(weight * (value - rgb[channel]) ** 2 for rgb in values)
                  for value in range(256))
            for channel, weight in enumerate(RGB_WEIGHTS)
        )
        self.count = len(values)

    def __call__(self, rgb: RGB) -> tuple[int, int]:
        red, green, blue = self.red[rgb[0]], self.green[rgb[1]], self.blue[rgb[2]]
        best, error = 0, red[0] + green[0] + blue[0]
        for index in range(1, self.count):
            score = red[index] + green[index] + blue[index]
            if score < error:
                best, error = index, score
        return best, error


def palette_errors(samples: tuple[RGB, ...], values: tuple[RGB, ...]) -> tuple[int, ...]:
    """Exact integer weighted-RGB errors, batching large searches in Pillow.

    Every component and minimum stays in signed 32-bit integer images (the
    largest RGB error is 585225). No RGB resampling or palette approximation is
    involved. Older Pillow versions and small inputs use the scalar lookup.
    """
    from PIL import Image, ImageMath

    if not values:
        raise ValueError('palette must contain at least one colour')
    evaluate = getattr(ImageMath, 'lambda_eval', None)
    if len(samples) < 4096 or evaluate is None:
        lookup = RGBPaletteLookup(values)
        return tuple(lookup(rgb)[1] for rgb in samples)
    tables = [tuple(tuple(weight * (value - channel) ** 2 for value in range(256))
                    for channel, weight in zip(rgb, RGB_WEIGHTS)) for rgb in values]
    result = []
    for offset in range(0, len(samples), 65536):
        chunk = samples[offset:offset + 65536]
        source = Image.new('RGB', (len(chunk), 1))
        source.putdata(chunk)
        channels = source.split()
        best = None
        for table in tables:
            red, green, blue = (channel.point(costs, mode='I') for channel, costs in zip(channels, table))
            error = evaluate(lambda a: a['r'] + a['g'] + a['b'], r=red, g=green, b=blue)
            best = error if best is None else evaluate(lambda a: a['min'](a['a'], a['b']), a=best, b=error)
        data = getattr(best, 'get_flattened_data', None)
        result.extend(data() if data is not None else best.getdata())
    return tuple(result)


class RGBPaletteTree:
    """Exact weighted nearest search for fractional diffusion samples.

    Balanced spatial splits prune only branches whose channel-distance lower
    bound exceeds the current error. Equality is always searched so palette
    index ties match exhaustive search, including duplicate RGB entries.
    """

    def __init__(self, values: tuple[RGB, ...]):
        if not values:
            raise ValueError('palette must contain at least one colour')
        self.values = values

        def build(items):
            if len(items) <= 8:
                return (None, items)
            axis = max(range(3), key=lambda c: RGB_WEIGHTS[c] *
                       (max(rgb[c] for _, rgb in items) - min(rgb[c] for _, rgb in items)) ** 2)
            items = sorted(items, key=lambda item: item[1][axis])
            middle = len(items) // 2
            return axis, items[middle][1][axis], build(items[:middle]), build(items[middle:])

        self.root = build(tuple(enumerate(values)))

    def nearest_index(self, rgb: tuple[float, float, float]) -> int:
        best, error = 0, colour_distance(rgb, self.values[0])
        wr, wg, wb = RGB_WEIGHTS
        r, g, b = rgb
        stack = [(self.root, 0)]
        while stack:
            node, bound = stack.pop()
            if bound > error:
                continue
            if node[0] is None:
                for index, (pr, pg, pb) in node[1]:
                    dr, dg, db = r - pr, g - pg, b - pb
                    score = wr * dr * dr + wg * dg * dg + wb * db * db
                    if score < error or (score == error and index < best):
                        best, error = index, score
            else:
                axis, split, left, right = node
                delta = rgb[axis] - split
                near, far = (left, right) if delta < 0 else (right, left)
                plane = RGB_WEIGHTS[axis] * delta * delta
                if plane <= error:
                    stack.append((far, max(bound, plane)))
                stack.append((near, bound))
        return best


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
