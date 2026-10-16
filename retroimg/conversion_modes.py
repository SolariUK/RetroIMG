"""Resolve profile constraint modes without target rules in the file pipeline."""
from __future__ import annotations

from typing import Callable
from functools import partial

from PIL import Image

from retroimg.constraints import quantize_teletext_mosaic
from retroimg.c64 import quantize_c64_multicolour
from retroimg.cpc import quantize_cpc
from retroimg.model import IndexedImage, Palette
from retroimg.quantize import quantize
from retroimg.spectrum import quantize_spectrum_attributes

Quantizer = Callable[[Image.Image, Palette, str], IndexedImage]

CONSTRAINED_QUANTIZERS: dict[tuple[str, str], Quantizer] = {
    ("teletext-mosaic", "mosaic"): quantize_teletext_mosaic,
    ("spectrum-attributes", "attributes"): quantize_spectrum_attributes,
    ("c64-multicolour", "multicolour"): quantize_c64_multicolour,
    **{(f"cpc-mode{mode}", "constrained"): partial(quantize_cpc, mode=mode) for mode in range(3)},
}


def get_quantizer(constraint_model: str, mode: str) -> Quantizer:
    if mode == "bitmap":
        return quantize
    try:
        return CONSTRAINED_QUANTIZERS[constraint_model, mode]
    except KeyError as exc:
        raise ValueError(f"unsupported mode {mode!r} for constraint model {constraint_model!r}") from exc
