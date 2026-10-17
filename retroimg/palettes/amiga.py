"""Amiga OCS/ECS idealised 12-bit RGB colour space."""
from retroimg.colour_spaces import RGBGrid

AMIGA_RGB = RGBGrid(tuple(range(0, 256, 17)))
AMIGA = AMIGA_RGB.palette("amiga", "Amiga OCS/ECS 4096-colour RGB space; 4 bits per channel.")
