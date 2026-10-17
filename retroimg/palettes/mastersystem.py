"""Master System Mode 4 idealised six-bit RGB colour space."""
from retroimg.colour_spaces import RGBGrid

MASTERSYSTEM_RGB = RGBGrid((0, 85, 170, 255))
MASTERSYSTEM = MASTERSYSTEM_RGB.palette('mastersystem', 'Master System Mode 4 RGB6; idealised two bits per channel.')
