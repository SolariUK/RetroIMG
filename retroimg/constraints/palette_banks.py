"""Fit shared RGB palette banks, assigning exactly one bank to each tile."""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image

from retroimg.colour_spaces import RGBGrid, colour_distance
from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.constraints.global_palette import select_palette_indices
from retroimg.model import Colour, IndexedImage, Palette, RGB
from retroimg.ordered import validate_dither
from retroimg.quantize import quantize


@dataclass(frozen=True)
class BankedImage:
    """Local codes and bank selectors, optionally sharing a slot-zero backdrop."""

    width: int
    height: int
    palettes: tuple[tuple[RGB, ...], ...]
    tile_palettes: tuple[tuple[int, ...], ...]
    pixels: tuple[tuple[int, ...], ...]
    tile_size: int = 8
    shared_backdrop: bool = True

    def __post_init__(self):
        if type(self.tile_size) is not int or self.tile_size <= 0:
            raise ValueError('tile size must be a positive integer')
        if any(type(n) is not int or n <= 0 or n % self.tile_size for n in (self.width, self.height)):
            raise ValueError('dimensions must be positive multiples of tile size')
        if not self.palettes or not self.palettes[0]:
            raise ValueError('palette banks must not be empty')
        if type(self.shared_backdrop) is not bool:
            raise ValueError('shared_backdrop must be boolean')
        slots = len(self.palettes[0])
        for bank in self.palettes:
            if len(bank) != slots or (self.shared_backdrop and bank[0] != self.palettes[0][0]):
                raise ValueError('banks must have equal capacity and honour the shared-backdrop setting')
            if any(len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb) for rgb in bank):
                raise ValueError('bank colours must be RGB values in 0..255')
        if len(self.tile_palettes) != self.height // self.tile_size or any(
                len(row) != self.width // self.tile_size for row in self.tile_palettes):
            raise ValueError('tile palette grid does not match dimensions')
        if any(type(i) is not int or not 0 <= i < len(self.palettes) for row in self.tile_palettes for i in row):
            raise ValueError('tile palette selector out of range')
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError('local pixel grid does not match dimensions')
        if any(type(i) is not int or not 0 <= i < slots for row in self.pixels for i in row):
            raise ValueError('local pixel code out of range')


def rasterize_banks(image: BankedImage, name: str) -> IndexedImage:
    slots = len(image.palettes[0])
    palette = Palette(name, tuple(Colour(f'bank-{b}-slot-{i}', rgb)
                                 for b, bank in enumerate(image.palettes) for i, rgb in enumerate(bank)))
    pixels = tuple(tuple(code + slots * image.tile_palettes[y // image.tile_size][x // image.tile_size]
                         for x, code in enumerate(row)) for y, row in enumerate(image.pixels))
    return IndexedImage(image.width, image.height, palette, pixels)


def fit_palette_banks(image: Image.Image, grid: RGBGrid | None, bank_count: int, *,
                      slots: int = 16, tile_size: int = 8, dither: str = 'none',
                      bayer_size: int = 4, palette: Palette | None = None,
                      shared_backdrop: bool = True) -> BankedImage:
    """Deterministic bounded alternating fit, not a globally optimal search.

    Farthest-error tile palettes seed banks, then full tile histograms select banks
    by weighted RGB error. Each bank is refitted from its assigned source
    pixels. A grid or fixed palette supplies legal colours. Where required,
    the most frequent nearest source colour is the shared backdrop; otherwise
    all slots are independently fitted.
    Fitting is independent of dithering; diffusion resets at tile boundaries.
    """
    validate_dither(dither, bayer_size)
    if type(bank_count) is not int or bank_count <= 0:
        raise ValueError('bank count must be a positive integer')
    if (grid is None) == (palette is None):
        raise ValueError('supply either an RGB grid or a fixed palette')
    if type(shared_backdrop) is not bool:
        raise ValueError('shared_backdrop must be boolean')
    capacity = len(grid.levels) ** 3 if grid is not None else len(palette.colours)
    if type(slots) is not int or not 2 <= slots <= capacity:
        raise ValueError('bank capacity must be at least two and within colour-space capacity')
    if type(tile_size) is not int or tile_size <= 0 or any(n <= 0 or n % tile_size for n in image.size):
        raise ValueError('dimensions must be positive multiples of tile size')
    source = image.convert('RGB')
    positions = [(x, y) for y in range(0, image.height, tile_size) for x in range(0, image.width, tile_size)]
    tiles = [source.crop((x, y, x + tile_size, y + tile_size)) for x, y in positions]
    tile_pixels = [tuple(tile.getpixel((x, y)) for y in range(tile_size) for x in range(tile_size))
                   for tile in tiles]
    histograms = [tile.getcolors(tile_size ** 2) for tile in tiles]
    counts = Counter()
    if grid is not None:
        snap = grid.snap
    else:
        candidate_values = palette.rgb_values()
        @lru_cache(maxsize=None)
        def snap(rgb):
            return min(candidate_values, key=lambda value: colour_distance(rgb, value))
    for histogram in histograms:
        for count, rgb in histogram:
            counts[snap(rgb)] += count
    backdrop = min(counts, key=lambda rgb: (-counts[rgb], rgb))
    def fit_members(members):
        # The fixed backdrop already represents these samples; do not spend
        # an independently selectable slot fitting it again.
        samples = [rgb for t in members for rgb in tile_pixels[t]
                   if not shared_backdrop or snap(rgb) != backdrop]
        if samples:
            pool = Image.new('RGB', (len(samples), 1))
            pool.putdata(samples)
            limit = slots - int(shared_backdrop)
            if grid is not None:
                selected = fit_rgb_palette(pool, grid, limit, max_samples=512, max_iterations=6)
            else:
                indices = select_palette_indices(pool, palette, limit, max_samples=512, max_swaps=2)
                selected = tuple(palette.colours[i].rgb for i in indices)
            colours = ((backdrop, *(rgb for rgb in selected if rgb != backdrop))
                       if shared_backdrop else selected)
        else:
            colours = (backdrop,)
        return colours + (backdrop,) * (slots - len(colours))

    def fit(assignments):
        banks = []
        for bank in range(bank_count):
            members = [t for t, b in enumerate(assignments) if b == bank]
            banks.append(fit_members(members))
        return tuple(banks)

    def assign(banks):
        unique = [tuple(dict.fromkeys(bank)) for bank in banks]
        @lru_cache(maxsize=None)
        def errors(rgb):
            return tuple(min(colour_distance(rgb, v) for v in bank) for bank in unique)
        scores = [tuple(sum(n * errors(rgb)[b] for n, rgb in hist) for b in range(len(banks)))
                  for hist in histograms]
        chosen = [min(range(len(banks)), key=score.__getitem__) for score in scores]
        return chosen, sum(score[b] for score, b in zip(scores, chosen))

    # Seed by palette error rather than mean colour: two tiles can have the
    # same mean yet need completely different colours.
    seeds = []
    residuals = [sum(n * colour_distance(rgb, backdrop) for n, rgb in hist) for hist in histograms]
    for _ in range(bank_count):
        seed = max(range(len(tiles)), key=residuals.__getitem__)
        bank = fit_members([seed])
        seeds.append(bank)
        values = tuple(dict.fromkeys(bank))
        @lru_cache(maxsize=None)
        def distance(rgb):
            return min(colour_distance(rgb, value) for value in values)
        residuals = [min(old, sum(n * distance(rgb) for n, rgb in hist))
                     for old, hist in zip(residuals, histograms)]
    assignments, _ = assign(seeds)
    best = None
    for _ in range(4):
        banks = fit(assignments)
        updated, error = assign(banks)
        if best is None or error < best[0]:
            best = error, banks, updated
        if updated == assignments:
            break
        assignments = updated
    _, banks, assignments = best
    pixels = [[0] * image.width for _ in range(image.height)]
    for tile, (x, y), bank in zip(tiles, positions, assignments):
        palette = Palette('bank', tuple(Colour(str(i), rgb) for i, rgb in enumerate(banks[bank])))
        indexed = quantize(tile, palette, dither, bayer_size=bayer_size, bayer_origin=(x, y))
        for dy, row in enumerate(indexed.pixels):
            pixels[y + dy][x:x + tile_size] = row
    columns = image.width // tile_size
    selectors = tuple(tuple(assignments[i:i + columns]) for i in range(0, len(assignments), columns))
    return BankedImage(image.width, image.height, banks, selectors, tuple(tuple(row) for row in pixels),
                       tile_size, shared_backdrop)
