"""Static Amstrad CPC screen inks, independent of hardware file encoding."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from retroimg.model import IndexedImage, Palette
from retroimg.palettefit import select_palette_indices
from retroimg.palettes.builtin import CPC
from retroimg.quantize import quantize

CPC_COLOUR_LIMITS = {0: 16, 1: 4, 2: 2}


def _validate_mode(mode: int) -> None:
    if type(mode) is not int or mode not in CPC_COLOUR_LIMITS:
        raise ValueError("CPC mode must be 0, 1 or 2")


@dataclass(frozen=True)
class CPCImage:
    """Pens map to firmware colours, with pen-indexed logical pixels.

    inks[pen] is a firmware colour number (0..26), not a Gate Array register
    value. This model permits custom dimensions but enforces the global ink
    limit for its mode. No flashing inks, border or raster palette changes.
    """

    width: int
    height: int
    mode: int
    inks: tuple[int, ...]
    pixels: tuple[tuple[int, ...], ...]
    palette: Palette = CPC

    def __post_init__(self) -> None:
        _validate_mode(self.mode)
        if self.palette != CPC:
            raise ValueError("CPC constrained mode requires the cpc palette")
        if any(type(size) is not int or size <= 0 for size in (self.width, self.height)):
            raise ValueError("CPC dimensions must be positive integers")
        if not 1 <= len(self.inks) <= CPC_COLOUR_LIMITS[self.mode]:
            raise ValueError("CPC ink count exceeds mode limit or is empty")
        if any(type(ink) is not int or not 0 <= ink < 27 for ink in self.inks):
            raise ValueError("CPC inks must be firmware colour numbers 0..26")
        if len(set(self.inks)) != len(self.inks):
            raise ValueError("CPC inks must be unique")
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError("CPC pixel grid does not match dimensions")
        if any(type(pen) is not int or not 0 <= pen < len(self.inks) for row in self.pixels for pen in row):
            raise ValueError("CPC pen index out of range")


def optimise_cpc(
    image: Image.Image, palette: Palette = CPC, dither: str = "none", *, mode: int = 0
) -> CPCImage:
    """Select image-wide inks, then quantise/dither the full RGB source."""
    _validate_mode(mode)
    if palette != CPC:
        raise ValueError("CPC constrained mode requires the cpc palette")
    if dither not in {"none", "floyd-steinberg"}:
        raise ValueError(f"unknown dither mode: {dither}")
    inks = select_palette_indices(image, palette, CPC_COLOUR_LIMITS[mode])
    selected = Palette(palette.name, tuple(palette.colours[index] for index in inks))
    indexed = quantize(image, selected, dither)
    return CPCImage(image.width, image.height, mode, inks, indexed.pixels, palette)


def quantize_cpc(
    image: Image.Image, palette: Palette, dither: str = "none", *, mode: int = 0
) -> IndexedImage:
    from retroimg.render import rasterize_cpc

    return rasterize_cpc(optimise_cpc(image, palette, dither, mode=mode))
