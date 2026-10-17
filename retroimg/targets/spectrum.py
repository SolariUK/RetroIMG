"""ZX Spectrum static 8x8 attribute cells; no screen-file encoding or FLASH."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations_with_replacement

from PIL import Image


from retroimg.constraints.cells import quantize_cells
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.spectrum import SPECTRUM

# The shared palette stores black once, then normal 1..7 and bright 1..7.
# Hardware ink/paper codes remain 0..7, independently of palette storage.
NORMAL_INDICES = tuple(range(8))
BRIGHT_INDICES = (0, *range(8, 15))
LEGAL_PAIRS = tuple(dict.fromkeys(
    pair
    for bank in (NORMAL_INDICES, BRIGHT_INDICES)
    for pair in combinations_with_replacement(bank, 2)
))


def spectrum_index(colour: int, bright: bool) -> int:
    """Map a hardware colour code and brightness to the shared RGB palette."""
    return (BRIGHT_INDICES if bright else NORMAL_INDICES)[colour]


def validate_spectrum_palette(palette: Palette) -> None:
    if palette != SPECTRUM:
        raise ValueError("Spectrum attribute mode requires the spectrum palette")


@dataclass(frozen=True)
class SpectrumCell:
    """Hardware ink/paper codes, shared BRIGHT, and 64 logical pixel bits.

    Bit 0 is top left; bits run left to right then top to bottom. A set bit
    selects ink. This logical pattern is not Spectrum video-memory byte order.
    """

    ink: int
    paper: int
    bright: bool
    pattern: int

    def __post_init__(self) -> None:
        if any(type(code) is not int or not 0 <= code < 8 for code in (self.ink, self.paper)):
            raise ValueError("Spectrum ink and paper must be integer codes 0..7")
        if type(self.bright) is not bool:
            raise ValueError("Spectrum bright must be a bool")
        if type(self.pattern) is not int or not 0 <= self.pattern < (1 << 64):
            raise ValueError("Spectrum pattern must be a 64-bit integer")


@dataclass(frozen=True)
class SpectrumImage:
    """Static attribute grid; the standard screen is 32x24 cells (256x192)."""

    cells: tuple[tuple[SpectrumCell, ...], ...]
    columns: int = 32
    rows: int = 24
    palette: Palette = SPECTRUM

    def __post_init__(self) -> None:
        validate_spectrum_palette(self.palette)
        if any(type(size) is not int or size <= 0 for size in (self.columns, self.rows)):
            raise ValueError("Spectrum cell-grid dimensions must be positive integers")
        if len(self.cells) != self.rows or any(len(row) != self.columns for row in self.cells):
            raise ValueError("Spectrum cell grid does not match dimensions")
        if any(not isinstance(cell, SpectrumCell) for row in self.cells for cell in row):
            raise ValueError("Spectrum cell grid must contain SpectrumCell values")


def spectrum_from_indexed(image: IndexedImage) -> SpectrumImage:
    """Represent a legal raster losslessly, rejecting attribute violations."""
    image.validate()
    validate_spectrum_palette(image.palette)
    if image.width <= 0 or image.height <= 0 or image.width % 8 or image.height % 8:
        raise ValueError("Spectrum attribute mode requires positive dimensions divisible by 8")
    rows = []
    for y in range(0, image.height, 8):
        cells = []
        for x in range(0, image.width, 8):
            samples = [image.pixels[y + dy][x + dx] for dy in range(8) for dx in range(8)]
            colours = sorted(set(samples))
            if len(colours) > 2:
                raise ValueError("Spectrum attribute cell contains more than two colours")
            bright = any(index >= 8 for index in colours)
            bank = BRIGHT_INDICES if bright else NORMAL_INDICES
            if any(index not in bank for index in colours):
                raise ValueError("Spectrum cell cannot mix normal and bright colours")
            paper, ink = colours[0], colours[-1]
            pattern = (sum(1 << bit for bit, index in enumerate(samples) if index == ink)
                       if ink != paper else 0)
            cells.append(SpectrumCell(bank.index(ink), bank.index(paper), bright, pattern))
        rows.append(tuple(cells))
    return SpectrumImage(tuple(rows), image.width // 8, image.height // 8, image.palette)


def optimise_spectrum_attributes(
    image: Image.Image, palette: Palette = SPECTRUM, dither: str = "none", *, bayer_size: int = 4
) -> SpectrumImage:
    """Fit all legal shared-brightness pairs to RGB, then dither within cells.

    Without dithering the selected pair/pattern minimises weighted RGB error.
    With dithering the pair is chosen by that same objective. Floyd–Steinberg
    resets at each cell; Bayer uses the pair with global logical matrix phase.
    """
    validate_spectrum_palette(palette)
    if image.width <= 0 or image.height <= 0 or image.width % 8 or image.height % 8:
        raise ValueError("Spectrum attribute mode requires positive dimensions divisible by 8")
    indexed = quantize_cells(image, palette, cell_width=8, cell_height=8,
                             dither=dither, allowed_pairs=LEGAL_PAIRS, bayer_size=bayer_size)
    return spectrum_from_indexed(indexed)


def quantize_spectrum_attributes(
    image: Image.Image, palette: Palette, dither: str = "none", *, bayer_size: int = 4
) -> IndexedImage:
    """Raster adapter for the common conversion pipeline."""
    return rasterize_spectrum(optimise_spectrum_attributes(image, palette, dither, bayer_size=bayer_size))


def rasterize_spectrum(image: SpectrumImage) -> IndexedImage:
    """Expand static ink/paper patterns without scaling or display effects."""
    pixels = []
    for cells in image.cells:
        for dy in range(8):
            row = []
            for cell in cells:
                ink = spectrum_index(cell.ink, cell.bright)
                paper = spectrum_index(cell.paper, cell.bright)
                row.extend(ink if cell.pattern & (1 << (dy * 8 + dx)) else paper
                           for dx in range(8))
            pixels.append(tuple(row))
    return IndexedImage(image.columns * 8, image.rows * 8, image.palette, tuple(pixels))
