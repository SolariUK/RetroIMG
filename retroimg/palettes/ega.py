"""EGA RGB6 colour space and the standard sixteen-colour PC palette."""
from retroimg.colour_spaces import RGBGrid
from retroimg.model import Palette
from ._shared import RGBI_COLOURS

EGA_RGB = RGBGrid((0, 85, 170, 255))
EGA = EGA_RGB.palette('ega', 'EGA 64-colour RGB6 gamut; 350-line screens select at most sixteen.')
EGA_DEFAULT = Palette('ega-default', RGBI_COLOURS, 'Standard sixteen-colour EGA/RGBI screen palette.')
