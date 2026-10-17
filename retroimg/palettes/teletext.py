"""Classic Teletext/Ceefax RGB primaries in existing palette-index order."""
from retroimg.model import Palette
from ._shared import RGB_PRIMARIES

TELETEXT = Palette('teletext', RGB_PRIMARIES, 'Classic 8-colour RGB Teletext/Ceefax palette.')
