from __future__ import annotations

from retroimg.model import Colour, Palette
from retroimg.colour_spaces import RGBGrid
from retroimg.palettes.atari import ATARI_NTSC, ATARI_PAL


def _palette(name: str, description: str, colours: tuple[tuple[str, tuple[int, int, int]], ...]) -> Palette:
    return Palette(
        name=name,
        description=description,
        colours=tuple(Colour(n, rgb) for n, rgb in colours),
    )


TELETEXT = _palette(
    "teletext",
    "Classic 8-colour RGB Teletext/Ceefax palette.",
    (
        ("black",   (0, 0, 0)),
        ("red",     (255, 0, 0)),
        ("green",   (0, 255, 0)),
        ("yellow",  (255, 255, 0)),
        ("blue",    (0, 0, 255)),
        ("magenta", (255, 0, 255)),
        ("cyan",    (0, 255, 255)),
        ("white",   (255, 255, 255)),
    ),
)

# The following are deliberately initial placeholders for architecture testing.
# Exact machine-specific palette variants can be refined independently later.
C64 = _palette(
    "c64",
    "Commodore 64-style 16-colour palette (common approximation).",
    (
        ("black", (0, 0, 0)), ("white", (255, 255, 255)),
        ("red", (136, 0, 0)), ("cyan", (170, 255, 238)),
        ("purple", (204, 68, 204)), ("green", (0, 204, 85)),
        ("blue", (0, 0, 170)), ("yellow", (238, 238, 119)),
        ("orange", (221, 136, 85)), ("brown", (102, 68, 0)),
        ("light-red", (255, 119, 119)), ("dark-grey", (51, 51, 51)),
        ("grey", (119, 119, 119)), ("light-green", (170, 255, 102)),
        ("light-blue", (0, 136, 255)), ("light-grey", (187, 187, 187)),
    ),
)

SPECTRUM = _palette(
    "spectrum",
    "ZX Spectrum normal + bright colours (black is shared).",
    (
        ("black", (0, 0, 0)),
        ("blue", (0, 0, 205)), ("red", (205, 0, 0)), ("magenta", (205, 0, 205)),
        ("green", (0, 205, 0)), ("cyan", (0, 205, 205)), ("yellow", (205, 205, 0)), ("white", (205, 205, 205)),
        ("bright-blue", (0, 0, 255)), ("bright-red", (255, 0, 0)), ("bright-magenta", (255, 0, 255)),
        ("bright-green", (0, 255, 0)), ("bright-cyan", (0, 255, 255)), ("bright-yellow", (255, 255, 0)), ("bright-white", (255, 255, 255)),
    ),
)

# Idealised three-level RGB, in firmware INK colour-number order (0..26).
# https://cpctech.cpcwiki.de/docs/garray.html#conversion-chart
# Actual analogue monitor colours may differ from these digital values.
CPC = _palette(
    "cpc",
    "Amstrad CPC 27-colour palette, firmware order; ideal RGB levels 0/128/255.",
    (
        ("black", (0, 0, 0)), ("blue", (0, 0, 128)),
        ("bright-blue", (0, 0, 255)), ("red", (128, 0, 0)),
        ("magenta", (128, 0, 128)), ("mauve", (128, 0, 255)),
        ("bright-red", (255, 0, 0)), ("purple", (255, 0, 128)),
        ("bright-magenta", (255, 0, 255)), ("green", (0, 128, 0)),
        ("cyan", (0, 128, 128)), ("sky-blue", (0, 128, 255)),
        ("yellow", (128, 128, 0)), ("white", (128, 128, 128)),
        ("pastel-blue", (128, 128, 255)), ("orange", (255, 128, 0)),
        ("pink", (255, 128, 128)), ("pastel-magenta", (255, 128, 255)),
        ("bright-green", (0, 255, 0)), ("sea-green", (0, 255, 128)),
        ("bright-cyan", (0, 255, 255)), ("lime", (128, 255, 0)),
        ("pastel-green", (128, 255, 128)), ("pastel-cyan", (128, 255, 255)),
        ("bright-yellow", (255, 255, 0)), ("pastel-yellow", (255, 255, 128)),
        ("bright-white", (255, 255, 255)),
    ),
)

# BBC physical colour numbers 0..7 use the same ideal RGB primaries as
# Teletext. Keep a separate named palette so target identity stays independent.
BBC = Palette("bbc", TELETEXT.colours, "BBC Micro eight steady physical colours, ideal RGB levels 0/255.")

AMIGA_RGB = RGBGrid(tuple(range(0, 256, 17)))
AMIGA = AMIGA_RGB.palette("amiga", "Amiga OCS/ECS 4096-colour RGB space; 4 bits per channel.")

PALETTES = {p.name: p for p in (TELETEXT, C64, SPECTRUM, CPC, BBC, AMIGA, ATARI_NTSC, ATARI_PAL)}


def get_palette(name: str) -> Palette:
    try:
        return PALETTES[name]
    except KeyError as exc:
        raise ValueError(f"unknown palette: {name}") from exc
