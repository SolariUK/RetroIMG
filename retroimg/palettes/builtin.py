"""Built-in palette registry and compatibility exports for earlier imports.

Definitions live in machine modules. Keep the registry order stable for callers.
"""
from retroimg.model import Palette
from .teletext import TELETEXT
from .c64 import C64
from .spectrum import SPECTRUM
from .cpc import CPC
from .bbc import BBC
from .amiga import AMIGA, AMIGA_RGB
from .atari import ATARI_NTSC, ATARI_PAL
from .megadrive import MEGADRIVE
from .snes import SNES

PALETTES = {p.name: p for p in (TELETEXT, C64, SPECTRUM, CPC, BBC, AMIGA, ATARI_NTSC, ATARI_PAL, MEGADRIVE, SNES)}


def get_palette(name: str) -> Palette:
    try:
        return PALETTES[name]
    except KeyError as exc:
        raise ValueError(f"unknown palette: {name}") from exc
