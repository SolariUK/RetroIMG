from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Colour:
    name: str
    rgb: RGB


@dataclass(frozen=True)
class Palette:
    name: str
    colours: tuple[Colour, ...]
    description: str = ""

    def rgb_values(self) -> tuple[RGB, ...]:
        return tuple(c.rgb for c in self.colours)


@dataclass(frozen=True)
class Geometry:
    width: int
    height: int
    pixel_aspect: float = 1.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("geometry dimensions must be positive")
        if self.pixel_aspect <= 0:
            raise ValueError("pixel_aspect must be positive")


@dataclass(frozen=True)
class TargetProfile:
    name: str
    geometry: Geometry
    default_palette: str
    description: str = ""
    constraint_model: str = "none"
    # Legacy profiles retain their existing square-pixel PNG previews.
    aspect_correct_preview: bool = False


@dataclass(frozen=True)
class IndexedImage:
    width: int
    height: int
    palette: Palette
    pixels: tuple[tuple[int, ...], ...]

    def validate(self) -> None:
        if len(self.pixels) != self.height:
            raise ValueError("row count does not match image height")
        limit = len(self.palette.colours)
        for row in self.pixels:
            if len(row) != self.width:
                raise ValueError("row width does not match image width")
            if any(index < 0 or index >= limit for index in row):
                raise ValueError("palette index out of range")
