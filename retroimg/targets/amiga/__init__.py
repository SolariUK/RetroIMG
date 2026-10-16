"""Amiga OCS/ECS screen models, fitting and logical rasterisation."""
from .indexed import (
    AMIGA_COLOUR_LIMITS, AmigaImage, optimise_amiga, quantize_amiga, rasterize_amiga,
)
from .ehb import (
    AmigaEHBImage, fit_ehb_registers, half_bright, optimise_ehb, quantize_ehb, rasterize_ehb,
)
from .ham import (
    AmigaHAMImage, decode_ham_code, optimise_ham, quantize_ham, rasterize_ham,
)

__all__ = [
    'AMIGA_COLOUR_LIMITS', 'AmigaImage', 'optimise_amiga', 'quantize_amiga', 'rasterize_amiga',
    'AmigaEHBImage', 'fit_ehb_registers', 'half_bright', 'optimise_ehb', 'quantize_ehb', 'rasterize_ehb',
    'AmigaHAMImage', 'decode_ham_code', 'optimise_ham', 'quantize_ham', 'rasterize_ham',
]
