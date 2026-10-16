"""Compatibility exports; prefer retroimg.targets.c64 for new code."""
from retroimg.targets.c64 import (
    C64MulticolourCell,
    C64MulticolourImage,
    optimise_c64_multicolour,
    quantize_c64_multicolour,
    rasterize_c64_multicolour,
)

__all__ = [
    "C64MulticolourCell",
    "C64MulticolourImage",
    "optimise_c64_multicolour",
    "quantize_c64_multicolour",
    "rasterize_c64_multicolour",
]
