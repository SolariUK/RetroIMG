from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
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

    # Present only for a complete, red-major Cartesian palette. It enables
    # exact per-channel nearest-colour lookup without a full palette search.
    rgb_levels: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.rgb_levels is not None:
            levels = self.rgb_levels
            if (not levels or any(type(v) is not int or not 0 <= v <= 255 for v in levels)
                    or tuple(sorted(set(levels))) != levels):
                raise ValueError("RGB levels must be sorted unique integers in 0..255")
            if self.rgb_values() != tuple(product(levels, repeat=3)):
                raise ValueError("RGB grid palette must contain the complete red-major Cartesian grid")

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
    # Optional resolved display geometry for source-aspect matching. Ordinary
    # conversions retain their existing profile-based rendering behaviour.
    pixel_aspect: float | None = None

    def validate(self) -> None:
        if self.pixel_aspect is not None and (not math.isfinite(self.pixel_aspect) or self.pixel_aspect <= 0):
            raise ValueError('pixel aspect must be finite and positive')
        if len(self.pixels) != self.height:
            raise ValueError("row count does not match image height")
        limit = len(self.palette.colours)
        for row in self.pixels:
            if len(row) != self.width:
                raise ValueError("row width does not match image width")
            if any(index < 0 or index >= limit for index in row):
                raise ValueError("palette index out of range")
