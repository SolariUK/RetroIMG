"""Compatibility exports; prefer retroimg.targets.cpc for new code."""
from retroimg.targets.cpc import (
    CPC_COLOUR_LIMITS,
    CPCImage,
    optimise_cpc,
    quantize_cpc,
    rasterize_cpc,
)

__all__ = [
    "CPC_COLOUR_LIMITS",
    "CPCImage",
    "optimise_cpc",
    "quantize_cpc",
    "rasterize_cpc",
]
