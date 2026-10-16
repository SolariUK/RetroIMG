"""C64 multicolour bitmap cells; no video-memory encoding or raster tricks."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from retroimg.cellfit import fit_shared_background
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.builtin import C64
from retroimg.quantize import quantize


def _valid_colour(index: int) -> bool:
    return type(index) is int and 0 <= index < 16


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
    image: Image.Image, palette: Palette = C64, dither: str = "none"
) -> C64MulticolourImage:
    """Choose the global background and three local colours per 4x8 cell.

    Background and cell sets exactly minimise undithered weighted RGB error.
    Optional diffusion then uses those sets and resets at each cell boundary.
    """
    if palette != C64:
        raise ValueError("C64 multicolour mode requires the c64 palette")
    if image.width <= 0 or image.height <= 0 or image.width % 4 or image.height % 8:
        raise ValueError("C64 multicolour mode requires positive width divisible by 4 and height by 8")
    if dither not in {"none", "floyd-steinberg"}:
        raise ValueError(f"unknown dither mode: {dither}")
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
            indexed = quantize(crop, local_palette, dither)
            pattern = sum(slots.index(ordered[index]) << (2 * bit)
                          for bit, index in enumerate(index for row in indexed.pixels for index in row))
            cells.append(C64MulticolourCell(local, pattern))
        rows.append(tuple(cells))
    return C64MulticolourImage(fit.background, tuple(rows), source.width // 4, source.height // 8, palette)


def quantize_c64_multicolour(
    image: Image.Image, palette: Palette, dither: str = "none"
) -> IndexedImage:
    from retroimg.render import rasterize_c64_multicolour

    return rasterize_c64_multicolour(optimise_c64_multicolour(image, palette, dither))
