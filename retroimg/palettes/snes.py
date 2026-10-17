"""SNES 15-bit RGB colour space; idealised digital channel levels."""
from retroimg.colour_spaces import RGBGrid

SNES_RGB = RGBGrid(tuple(round(i * 255 / 31) for i in range(32)))
SNES = SNES_RGB.palette('snes', 'SNES 15-bit RGB; 32 levels per channel.')
