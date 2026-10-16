"""Reusable constraints plus compatibility entry points for Teletext callers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from retroimg.model import IndexedImage, Palette
from .cells import quantize_cells

if TYPE_CHECKING:
    from retroimg.targets.teletext import TeletextPage

__all__ = ["quantize_cells", "quantize_teletext_mosaic", "optimise_teletext_mosaic", "constrain_teletext_mosaic"]


def quantize_teletext_mosaic(image: Image.Image, palette: Palette, dither: str = "none") -> IndexedImage:
    """Compatibility entry point; new code should import the Teletext target."""
    from retroimg.targets.teletext import quantize_teletext_mosaic as implementation
    return implementation(image, palette, dither)


def optimise_teletext_mosaic(image: Image.Image, palette: Palette, dither: str = "none") -> TeletextPage:
    """Compatibility entry point; new code should import the Teletext target."""
    from retroimg.targets.teletext import optimise_teletext_mosaic as implementation
    return implementation(image, palette, dither)


def constrain_teletext_mosaic(image: IndexedImage) -> IndexedImage:
    """Compatibility entry point for an already indexed Teletext mosaic."""
    from retroimg.targets.teletext import constrain_teletext_mosaic as implementation
    return implementation(image)
