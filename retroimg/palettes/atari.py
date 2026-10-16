"""Independent idealised TIA colour approximations, in even-register order.

TIA produces analogue chroma/luma, not fixed RGB. These are deliberately our
own YIQ previews, not copied emulator tables or a simulation of a TV decoder.
NTSC follows the hue progression around the colour wheel; PAL interleaves
warm/cool hues and has four equivalent grayscale hue banks. See README.
"""
from math import cos, sin, radians

from retroimg.model import Colour, Palette

# Nominal NTSC hue phases in YIQ space. PAL hue order corresponds to the
# hardware's interleaved progression rather than NTSC register order.
_NTSC_PHASES = (None, -37, -15, 0, 15, 55, 90, 130,
                155, 180, 205, 230, 250, 275, 300, 330)
_PAL_PHASES = (None, None, -37, 275, -15, 250, 15, 230,
               55, 205, 90, 180, 130, 155, None, None)
_GRAY = (0, 74, 111, 142, 170, 192, 214, 236)


def _make_palette(standard: str, phases: tuple[float | None, ...]) -> Palette:
    colours = []
    for hue, phase in enumerate(phases):
        for level in range(8):
            if phase is None:
                rgb = (_GRAY[level],) * 3
            else:
                angle = radians(phase)
                chroma = 0.30 * (1 - 0.04 * level)
                i, q = chroma * cos(angle), chroma * sin(angle)
                y = 0.21 + 0.095 * level
                rgb = tuple(round(255 * max(0, min(1, value))) for value in (
                    y + 0.956 * i + 0.621 * q,
                    y - 0.272 * i - 0.647 * q,
                    y - 1.106 * i + 1.703 * q,
                ))
            code = (hue << 4) | (level << 1)
            colours.append(Colour(f"tia-{code:02x}", rgb))
    return Palette(f"atari2600-{standard.lower()}", tuple(colours),
                   f"Atari 2600 {standard} TIA; idealised YIQ approximation, 128 register slots.")


ATARI_NTSC = _make_palette("NTSC", _NTSC_PHASES)
ATARI_PAL = _make_palette("PAL", _PAL_PHASES)
