"""Bounded greedy HAM6 encoding and an independent hardware-code decoder."""
from dataclasses import dataclass

from PIL import Image

from retroimg.ordered import bayer_threshold, ordered_index, validate_dither

from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.amiga import AMIGA, AMIGA_RGB
from retroimg.quantize import colour_distance, quantize
from .common import validate_screen


def decode_ham_code(previous: int, registers: tuple[int, ...], code: int) -> int:
    """00=palette, 01=blue, 10=red, 11=green; low nibble is the value."""
    operation, value = code >> 4, code & 15
    if operation == 0:
        return registers[value]
    shift = (0, 0, 8, 4)[operation]
    return (previous & ~(15 << shift)) | (value << shift)


@dataclass(frozen=True)
class AmigaHAMImage:
    """Six-bit HAM6 codes and 16 RGB12 base registers, retaining scan order.

    Each scanline starts from register 0, independently of the preceding row.
    Duplicate/unused register slots are legal. Pixel codes are not RGB indices.
    """
    width: int
    height: int
    registers: tuple[int, ...]
    codes: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        validate_screen(self.width, self.height, self.registers, self.codes, 16)

    @property
    def bitplanes(self) -> int:
        return 6


def optimise_ham(image: Image.Image, palette: Palette = AMIGA, dither: str = 'none', *,
                 colours: int | None = None, bayer_size: int = 4) -> AmigaHAMImage:
    """Choose the best immediate legal pixel; no whole-row state search.

    In plain/FS mode a fixed previous colour makes each modification separable:
    only its nearest channel level need be tested. The resulting 19 choices
    (16 base entries and three modifications) give the same immediate minimum
    as all 64 codes, with lower code values breaking ties. This is greedy and
    can trade later-pixel error for a better current-pixel match. Bayer instead
    mixes decoded colours from all 64 legal codes using the ordered selector.
    """
    if palette != AMIGA:
        raise ValueError('Amiga HAM mode requires the amiga palette')
    if colours is not None:
        raise ValueError('--colours is not supported in HAM mode; it uses 16 base registers')
    validate_dither(dither, bayer_size)
    selected = fit_rgb_palette(image, AMIGA_RGB, 16)
    registers = tuple(AMIGA_RGB.nearest_index(rgb) for rgb in selected)
    registers += (0,) * (16 - len(registers))
    values = tuple(AMIGA.colours[word].rgb for word in registers)
    codes = [[0] * image.width for _ in range(image.height)]
    previous = registers[0]

    def lookup(x, y, rgb):
        nonlocal previous
        if x == 0:
            previous = registers[0]
        if dither == "bayer":
            # All 64 legal operations are available to the ordered mixer.
            words = tuple(decode_ham_code(previous, registers, code) for code in range(64))
            candidates = tuple(AMIGA.colours[word].rgb for word in words)
            code = ordered_index(rgb, candidates, bayer_threshold(x, y, bayer_size), bayer_size=bayer_size)
            codes[y][x] = code
            previous = words[code]
            return previous
        base = min(range(16), key=lambda i: colour_distance(rgb, values[i]))
        nearest = AMIGA_RGB.nearest_index(rgb)
        candidates = ((base, registers[base]),
                      (16 | (nearest & 15), (previous & 0xff0) | (nearest & 15)),
                      (32 | (nearest >> 8), (previous & 0x0ff) | (nearest & 0xf00)),
                      (48 | ((nearest >> 4) & 15), (previous & 0xf0f) | (nearest & 0x0f0)))
        code, word = min(candidates, key=lambda pair: (colour_distance(rgb, AMIGA.colours[pair[1]].rgb), pair[0]))
        codes[y][x] = code
        previous = word
        return word

    quantize(image, AMIGA, dither, pixel_lookup=lookup, bayer_size=bayer_size)
    return AmigaHAMImage(image.width, image.height, registers, tuple(tuple(row) for row in codes))


def rasterize_ham(image: AmigaHAMImage) -> IndexedImage:
    pixels = []
    for row in image.codes:
        previous = image.registers[0]
        output = []
        for code in row:
            previous = decode_ham_code(previous, image.registers, code)
            output.append(previous)
        pixels.append(tuple(output))
    return IndexedImage(image.width, image.height, AMIGA, tuple(pixels))


def quantize_ham(image: Image.Image, palette: Palette, dither: str = 'none', *,
                 colours: int | None = None, bayer_size: int = 4) -> IndexedImage:
    return rasterize_ham(optimise_ham(image, palette, dither, colours=colours, bayer_size=bayer_size))
