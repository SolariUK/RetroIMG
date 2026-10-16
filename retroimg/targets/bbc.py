"""Static BBC Micro bitmap screens, independent of video-memory encoding."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from retroimg.model import IndexedImage, Palette
from retroimg.constraints.global_palette import select_palette_indices
from retroimg.palettes.builtin import BBC
from retroimg.quantize import quantize

BBC_COLOUR_LIMITS = {0: 2, 1: 4, 2: 8, 4: 2, 5: 4}


def _validate_mode(mode: int) -> None:
    if type(mode) is not int or mode not in BBC_COLOUR_LIMITS:
        raise ValueError("BBC mode must be 0, 1, 2, 4 or 5")


@dataclass(frozen=True)
class BBCImage:
    """Logical pixel values map to steady physical colours (0..7).

    colours[logical] is the physical colour selected for a logical slot, as
    with VDU 19. Mode 2 has 16 hardware slots but only eight steady colours;
    this static model uses unique steady colours and excludes flashing pairs.
    Custom dimensions are permitted; no border or raster palette changes.
    """

    width: int
    height: int
    mode: int
    colours: tuple[int, ...]
    pixels: tuple[tuple[int, ...], ...]
    palette: Palette = BBC

    def __post_init__(self) -> None:
        _validate_mode(self.mode)
        if self.palette != BBC:
            raise ValueError("BBC constrained mode requires the bbc palette")
        if any(type(size) is not int or size <= 0 for size in (self.width, self.height)):
            raise ValueError("BBC dimensions must be positive integers")
        if not 1 <= len(self.colours) <= BBC_COLOUR_LIMITS[self.mode]:
            raise ValueError("BBC colour count exceeds mode limit or is empty")
        if any(type(colour) is not int or not 0 <= colour < 8 for colour in self.colours):
            raise ValueError("BBC colours must be physical colour numbers 0..7")
        if len(set(self.colours)) != len(self.colours):
            raise ValueError("BBC colours must be unique")
        if len(self.pixels) != self.height or any(len(row) != self.width for row in self.pixels):
            raise ValueError("BBC pixel grid does not match dimensions")
        if any(type(logical) is not int or not 0 <= logical < len(self.colours) for row in self.pixels for logical in row):
            raise ValueError("BBC logical index out of range")


def optimise_bbc(
    image: Image.Image, palette: Palette = BBC, dither: str = "none", *, mode: int = 0
) -> BBCImage:
    """Select image-wide colours, then quantise/dither the full RGB source."""
    _validate_mode(mode)
    if palette != BBC:
        raise ValueError("BBC constrained mode requires the bbc palette")
    if dither not in {"none", "floyd-steinberg"}:
        raise ValueError(f"unknown dither mode: {dither}")
    colours = select_palette_indices(image, palette, BBC_COLOUR_LIMITS[mode])
    selected = Palette(palette.name, tuple(palette.colours[index] for index in colours))
    indexed = quantize(image, selected, dither)
    return BBCImage(image.width, image.height, mode, colours, indexed.pixels, palette)


def quantize_bbc(
    image: Image.Image, palette: Palette, dither: str = "none", *, mode: int = 0
) -> IndexedImage:
    return rasterize_bbc(optimise_bbc(image, palette, dither, mode=mode))


def rasterize_bbc(image: BBCImage) -> IndexedImage:
    """Map logical pixel values to physical palette indices, without scaling."""
    pixels = tuple(tuple(image.colours[logical] for logical in row) for row in image.pixels)
    return IndexedImage(image.width, image.height, image.palette, pixels)
