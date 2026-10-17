"""BBC Micro steady physical colours 0..7, using standard RGB primaries."""
from retroimg.model import Palette
from ._shared import RGB_PRIMARIES

BBC = Palette('bbc', RGB_PRIMARIES, 'BBC Micro eight steady physical colours, ideal RGB levels 0/255.')
