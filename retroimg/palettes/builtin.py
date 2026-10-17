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
from .nes import NES
from .mastersystem import MASTERSYSTEM
from .gameboy import GAMEBOY, GAMEBOY_GREY
from .cga import CGA, CGA_PALETTES, CGA_MONO
from .ega import EGA, EGA_DEFAULT

PALETTES = {p.name: p for p in (TELETEXT, C64, SPECTRUM, CPC, BBC, AMIGA, ATARI_NTSC, ATARI_PAL, MEGADRIVE, SNES, NES, MASTERSYSTEM, GAMEBOY, GAMEBOY_GREY, CGA, *CGA_PALETTES.values(), CGA_MONO, EGA, EGA_DEFAULT)}


def get_palette(name: str) -> Palette:
    try:
        return PALETTES[name]
    except KeyError as exc:
        raise ValueError(f"unknown palette: {name}") from exc
