"""Small palette constructors and standard RGB primaries shared by targets."""
from retroimg.model import Colour, Palette


def make_palette(name: str, description: str, colours: tuple[tuple[str, tuple[int, int, int]], ...]) -> Palette:
    return Palette(name, tuple(Colour(label, rgb) for label, rgb in colours), description)


RGB_PRIMARIES = tuple(Colour(label, rgb) for label, rgb in (
    ("black", (0, 0, 0)),
    ("red", (255, 0, 0)),
    ("green", (0, 255, 0)),
    ("yellow", (255, 255, 0)),
    ("blue", (0, 0, 255)),
    ("magenta", (255, 0, 255)),
    ("cyan", (0, 255, 255)),
    ("white", (255, 255, 255)),
))
