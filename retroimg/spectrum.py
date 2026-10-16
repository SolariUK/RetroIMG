"""Compatibility exports; prefer retroimg.targets.spectrum for new code."""
from retroimg.targets.spectrum import (
    NORMAL_INDICES,
    BRIGHT_INDICES,
    LEGAL_PAIRS,
    spectrum_index,
    validate_spectrum_palette,
    SpectrumCell,
    SpectrumImage,
    spectrum_from_indexed,
    optimise_spectrum_attributes,
    quantize_spectrum_attributes,
    rasterize_spectrum,
)

__all__ = [
    "NORMAL_INDICES",
    "BRIGHT_INDICES",
    "LEGAL_PAIRS",
    "spectrum_index",
    "validate_spectrum_palette",
    "SpectrumCell",
    "SpectrumImage",
    "spectrum_from_indexed",
    "optimise_spectrum_attributes",
    "quantize_spectrum_attributes",
    "rasterize_spectrum",
]
