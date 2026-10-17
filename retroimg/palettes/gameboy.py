"""Four light-to-dark shades for original monochrome Game Boy previews."""
from ._shared import make_palette

GAMEBOY = make_palette('gameboy', 'Original Game Boy four-shade green LCD approximation.', (
    ('lightest', (155, 188, 15)), ('light', (139, 172, 15)),
    ('dark', (48, 98, 48)), ('darkest', (15, 56, 15)),
))
GAMEBOY_GREY = make_palette('gameboy-grey', 'Original Game Boy four neutral greys, light to dark.', (
    ('white', (255, 255, 255)), ('light-grey', (170, 170, 170)),
    ('dark-grey', (85, 85, 85)), ('black', (0, 0, 0)),
))
