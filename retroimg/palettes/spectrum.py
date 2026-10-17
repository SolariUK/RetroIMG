"""ZX Spectrum normal and bright colours; black is shared."""
from ._shared import make_palette

SPECTRUM = make_palette(
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
