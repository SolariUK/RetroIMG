"""Compatibility exports; prefer retroimg.targets.teletext for new code."""
from retroimg.targets.teletext import (
    TeletextCell,
    TeletextPage,
    page_from_indexed,
    constrain_teletext_mosaic,
    optimise_teletext_mosaic,
    quantize_teletext_mosaic,
    rasterize_teletext,
)

__all__ = [
    "TeletextCell",
    "TeletextPage",
    "page_from_indexed",
    "constrain_teletext_mosaic",
    "optimise_teletext_mosaic",
    "quantize_teletext_mosaic",
    "rasterize_teletext",
]
