"""C64 hires and multicolour bitmap cells, without memory packing or raster tricks."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from retroimg.ordered import validate_dither

from retroimg.constraints.shared_background import fit_shared_background
from retroimg.constraints.cells import quantize_cells
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.c64 import C64
from retroimg.quantize import quantize


def _valid_colour(index: int) -> bool:
    return type(index) is int and 0 <= index < 16


@dataclass(frozen=True)
class C64HiresCell:
    """Two local palette indices and 64 logical bits, left to right then down."""

    paper: int
    ink: int
    pattern: int

    def __post_init__(self):
        if any(not _valid_colour(index) for index in (self.paper, self.ink)):
            raise ValueError('C64 hires colours must be palette indices 0..15')
        if type(self.pattern) is not int or not 0 <= self.pattern < (1 << 64):
            raise ValueError('C64 hires pattern must be a 64-bit integer')


@dataclass(frozen=True)
class C64HiresImage:
    cells: tuple[tuple[C64HiresCell, ...], ...]
    columns: int = 40
    rows: int = 25
    palette: Palette = C64

    def __post_init__(self):
        if self.palette != C64:
            raise ValueError('C64 hires mode requires the c64 palette')
        if any(type(size) is not int or size <= 0 for size in (self.columns, self.rows)):
            raise ValueError('C64 hires cell-grid dimensions must be positive integers')
        if len(self.cells) != self.rows or any(len(row) != self.columns for row in self.cells):
            raise ValueError('C64 hires cell grid does not match dimensions')
        if any(not isinstance(cell, C64HiresCell) for row in self.cells for cell in row):
            raise ValueError('C64 hires cell grid must contain C64HiresCell values')


def optimise_c64_hires(image: Image.Image, palette: Palette = C64, dither='none', *, bayer_size=4):
    """Exactly fit two independent colours per 8x8 cell before optional dithering."""
    if palette != C64:
        raise ValueError('C64 hires mode requires the c64 palette')
    if image.width <= 0 or image.height <= 0 or image.width % 8 or image.height % 8:
        raise ValueError('C64 hires mode requires positive dimensions divisible by 8')
    indexed = quantize_cells(image, palette, cell_width=8, cell_height=8,
                             dither=dither, bayer_size=bayer_size)
    rows = []
    for y in range(0, image.height, 8):
        cells = []
        for x in range(0, image.width, 8):
            samples = [indexed.pixels[y + dy][x + dx] for dy in range(8) for dx in range(8)]
            paper, ink = min(samples), max(samples)
            pattern = sum(1 << bit for bit, index in enumerate(samples) if ink != paper and index == ink)
            cells.append(C64HiresCell(paper, ink, pattern))
        rows.append(tuple(cells))
    return C64HiresImage(tuple(rows), image.width // 8, image.height // 8, palette)


def rasterize_c64_hires(image: C64HiresImage) -> IndexedImage:
    pixels = []
    for cells in image.cells:
        for dy in range(8):
            row = []
            for cell in cells:
                row.extend(cell.ink if cell.pattern & (1 << (dy * 8 + dx)) else cell.paper
                           for dx in range(8))
            pixels.append(tuple(row))
    return IndexedImage(image.columns * 8, image.rows * 8, image.palette, tuple(pixels))


def quantize_c64_hires(image: Image.Image, palette: Palette, dither='none', *, bayer_size=4):
    return rasterize_c64_hires(optimise_c64_hires(image, palette, dither, bayer_size=bayer_size))


@dataclass(frozen=True)
class C64MulticolourCell:
    """Three local palette indices and 32 two-bit logical pixel selectors.

    Selector 0 uses the image-wide background; 1..3 use local colours. The
    first selector occupies the lowest two bits; pixels run left to right,
    then top to bottom across a 4x8 cell. This is not VIC-II memory order.
    """

    colours: tuple[int, int, int]
    pattern: int

    def __post_init__(self) -> None:
        if len(self.colours) != 3 or any(not _valid_colour(index) for index in self.colours):
            raise ValueError("C64 cell requires three local palette indices 0..15")
        if type(self.pattern) is not int or not 0 <= self.pattern < (1 << 64):
            raise ValueError("C64 pattern must be a 64-bit integer")


@dataclass(frozen=True)
class C64MulticolourImage:
    background: int
    cells: tuple[tuple[C64MulticolourCell, ...], ...]
    columns: int = 40
    rows: int = 25
    palette: Palette = C64

    def __post_init__(self) -> None:
        if self.palette != C64:
            raise ValueError("C64 multicolour mode requires the c64 palette")
        if not _valid_colour(self.background):
            raise ValueError("C64 background must be a palette index 0..15")
        if any(type(size) is not int or size <= 0 for size in (self.columns, self.rows)):
            raise ValueError("C64 cell-grid dimensions must be positive integers")
        if len(self.cells) != self.rows or any(len(row) != self.columns for row in self.cells):
            raise ValueError("C64 cell grid does not match dimensions")
        if any(not isinstance(cell, C64MulticolourCell) for row in self.cells for cell in row):
            raise ValueError("C64 cell grid must contain C64MulticolourCell values")


def optimise_c64_multicolour(
    image: Image.Image, palette: Palette = C64, dither: str = "none", *, bayer_size: int = 4
) -> C64MulticolourImage:
    """Choose the global background and three local colours per 4x8 cell.

    Background and cell sets exactly minimise undithered weighted RGB error.
    Optional diffusion then uses those sets and resets at each cell boundary.
    """
    if palette != C64:
        raise ValueError("C64 multicolour mode requires the c64 palette")
    if image.width <= 0 or image.height <= 0 or image.width % 4 or image.height % 8:
        raise ValueError("C64 multicolour mode requires positive width divisible by 4 and height by 8")
    validate_dither(dither, bayer_size)
    source = image.convert("RGB")
    fit = fit_shared_background(source, palette, cell_width=4, cell_height=8)
    rows = []
    for cy, choices in enumerate(fit.colours):
        cells = []
        for cx, choice in enumerate(choices):
            local = tuple(index for index in choice if index != fit.background)
            local += (fit.background,) * (3 - len(local))
            slots = (fit.background, *local)
            # Palette order breaks assignment ties, independently of selector
            # numbering, for consistency with unrestricted quantisation.
            ordered = tuple(sorted(set(slots)))
            local_palette = Palette(palette.name, tuple(palette.colours[i] for i in ordered))
            crop = source.crop((cx * 4, cy * 8, cx * 4 + 4, cy * 8 + 8))
            indexed = quantize(crop, local_palette, dither, bayer_size=bayer_size,
                               bayer_origin=(cx * 4, cy * 8))
            pattern = sum(slots.index(ordered[index]) << (2 * bit)
                          for bit, index in enumerate(index for row in indexed.pixels for index in row))
            cells.append(C64MulticolourCell(local, pattern))
        rows.append(tuple(cells))
    return C64MulticolourImage(fit.background, tuple(rows), source.width // 4, source.height // 8, palette)


def quantize_c64_multicolour(
    image: Image.Image, palette: Palette, dither: str = "none", *, bayer_size: int = 4
) -> IndexedImage:
    return rasterize_c64_multicolour(optimise_c64_multicolour(image, palette, dither, bayer_size=bayer_size))


def rasterize_c64_multicolour(image: C64MulticolourImage) -> IndexedImage:
    """Expand two-bit selectors to a logical raster, retaining wide pixels."""
    pixels = []
    for cells in image.cells:
        for dy in range(8):
            row = []
            for cell in cells:
                colours = (image.background, *cell.colours)
                row.extend(colours[(cell.pattern >> (2 * (dy * 4 + dx))) & 3]
                           for dx in range(4))
            pixels.append(tuple(row))
    return IndexedImage(image.columns * 4, image.rows * 8, image.palette, tuple(pixels))
