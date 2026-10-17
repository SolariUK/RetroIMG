"""Amstrad CPC idealised RGB levels, in firmware INK number order."""
from ._shared import make_palette

# https://cpctech.cpcwiki.de/docs/garray.html#conversion-chart
# Actual analogue monitor colours may differ from these digital values.
CPC = make_palette(
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
