"""Commodore 64 colour approximation, in existing palette-index order."""
from ._shared import make_palette

C64 = make_palette(
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
