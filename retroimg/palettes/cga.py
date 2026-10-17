"""Standard RGBI and four black-background CGA graphics palette variants."""
from retroimg.model import Palette
from ._shared import RGBI_COLOURS

CGA = Palette('cga', RGBI_COLOURS, 'PC sixteen-colour RGBI gamut, with brown correction.')
CGA_PALETTES = {}
CGA_COLOUR_SELECT = {}
for number, indices in ((0, (2, 4, 6)), (1, (3, 5, 7))):
    for intensity, label in ((0, 'low'), (1, 'high')):
        name = f'cga-pal{number}-{label}'
        colours = (RGBI_COLOURS[0], *(RGBI_COLOURS[i + intensity * 8] for i in indices))
        CGA_PALETTES[name] = Palette(name, colours, f'CGA 320x200 palette {number}, {label} intensity, black background.')
        CGA_COLOUR_SELECT[name] = (number << 5) | (intensity << 4)
CGA_MONO = Palette('cga-mono', (RGBI_COLOURS[0], RGBI_COLOURS[15]), 'CGA 640x200 black and white.')
CGA_COLOUR_SELECT['cga-mono'] = 0x0f
