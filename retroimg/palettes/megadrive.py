"""Mega Drive/Genesis normal 9-bit RGB; idealised digital channel levels."""
from retroimg.colour_spaces import RGBGrid

MEGADRIVE_RGB = RGBGrid(tuple(round(i * 255 / 7) for i in range(8)))
MEGADRIVE = MEGADRIVE_RGB.palette('megadrive', 'Mega Drive/Genesis normal 9-bit RGB; idealised 8 levels per channel.')
