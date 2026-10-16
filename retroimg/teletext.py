"""Visual Teletext mosaics, independent of transmission control-code state."""
from __future__ import annotations

from dataclasses import dataclass

from retroimg.model import IndexedImage, Palette


@dataclass(frozen=True)
class TeletextCell:
    """Palette indices and six row-major bits (bit 0 is the top left).

    A set bit selects foreground; a clear bit selects background. These are
    logical pattern bits, not encoded Teletext character bytes.
    """

    foreground: int
    background: int
    pattern: int

    def __post_init__(self) -> None:
        if any(type(value) is not int for value in
               (self.foreground, self.background, self.pattern)):
            raise ValueError("cell colours and pattern must be integers")
        if self.foreground < 0 or self.background < 0:
            raise ValueError("cell palette indices must be non-negative")
        if not 0 <= self.pattern < 64:
            raise ValueError("mosaic pattern must be a six-bit value")


@dataclass(frozen=True)
class TeletextPage:
    """A visual cell grid; columns/rows count cells, not logical pixels.

    The standard grid is 40x25, yielding an 80x75 logical raster. Custom grids
    remain useful for image conversion and are not broadcast page claims.
    """

    palette: Palette
    cells: tuple[tuple[TeletextCell, ...], ...]
    columns: int = 40
    rows: int = 25

    def __post_init__(self) -> None:
        if type(self.columns) is not int or type(self.rows) is not int:
            raise ValueError("page dimensions must be integers")
        if self.columns <= 0 or self.rows <= 0:
            raise ValueError("page dimensions must be positive")
        if len(self.cells) != self.rows or any(len(row) != self.columns for row in self.cells):
            raise ValueError("cell grid does not match page dimensions")
        limit = len(self.palette.colours)
        if any(cell.foreground >= limit or cell.background >= limit
               for row in self.cells for cell in row):
            raise ValueError("cell palette index out of range")


def page_from_indexed(image: IndexedImage) -> TeletextPage:
    """Losslessly represent a two-colour-per-cell raster with canonical cells.

    The lower used index becomes background. Solid cells use the same index
    for both colours and pattern zero. No transmission constraints are imposed.
    """
    image.validate()
    if image.width <= 0 or image.height <= 0 or image.width % 2 or image.height % 3:
        raise ValueError("mosaic raster dimensions must be positive multiples of 2x3")
    rows = []
    for y in range(0, image.height, 3):
        cells = []
        for x in range(0, image.width, 2):
            samples = [image.pixels[y + dy][x + dx] for dy in range(3) for dx in range(2)]
            colours = sorted(set(samples))
            if len(colours) > 2:
                raise ValueError("mosaic cell contains more than two colours")
            background, foreground = colours[0], colours[-1]
            pattern = (sum(1 << bit for bit, index in enumerate(samples) if index == foreground)
                       if foreground != background else 0)
            cells.append(TeletextCell(foreground, background, pattern))
        rows.append(tuple(cells))
    return TeletextPage(image.palette, tuple(rows), image.width // 2, image.height // 3)
