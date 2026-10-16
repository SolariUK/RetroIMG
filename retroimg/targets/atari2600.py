"""Visual TIA playfields: two colours per band, with 40 wide blocks.

This models image constraints, not CPU timing, sprites or a display program.
"""
from dataclasses import dataclass

from PIL import Image

from retroimg.ordered import validate_dither

from retroimg.constraints.binary_groups import fit_binary_groups
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.atari import ATARI_NTSC, ATARI_PAL
from retroimg.quantize import colour_distance, quantize

PLAYFIELD_MODES = ("playfield", "repeat", "mirror")


def _check_mode(mode: str) -> None:
    if mode not in PLAYFIELD_MODES:
        raise ValueError(f"unknown Atari playfield mode: {mode}")


@dataclass(frozen=True)
class AtariPlayfieldRow:
    """Even TIA colour-register values and a logical left-to-right bit pattern.

    Bit zero is the leftmost block. Independent playfields have 40 bits;
    repeated/mirrored rows have 20. These are not PF register byte layouts.
    """
    background: int
    foreground: int
    pattern: int

    def __post_init__(self) -> None:
        if any(type(code) is not int or not 0 <= code <= 254 or code % 2
               for code in (self.background, self.foreground)):
            raise ValueError("TIA colours must be even register values 0..254")
        if type(self.pattern) is not int or not 0 <= self.pattern < 1 << 40:
            raise ValueError("Atari pattern must be an unsigned 40-bit integer")


@dataclass(frozen=True)
class AtariPlayfield:
    height: int
    row_height: int
    mode: str
    rows: tuple[AtariPlayfieldRow, ...]
    palette: Palette = ATARI_NTSC

    def __post_init__(self) -> None:
        _check_mode(self.mode)
        if self.palette not in (ATARI_NTSC, ATARI_PAL):
            raise ValueError("Atari playfield requires an atari2600-ntsc or atari2600-pal palette")
        if any(type(value) is not int or value <= 0 for value in (self.height, self.row_height)):
            raise ValueError("Atari height and row height must be positive integers")
        if len(self.rows) != (self.height + self.row_height - 1) // self.row_height:
            raise ValueError("Atari row count does not match height")
        bits = 40 if self.mode == "playfield" else 20
        if any(not isinstance(row, AtariPlayfieldRow) or row.pattern >= 1 << bits for row in self.rows):
            raise ValueError("Atari row pattern exceeds mode width")


def _selector(x: int, mode: str) -> int:
    if x < 20 or mode == "playfield":
        return x
    return x - 20 if mode == "repeat" else 39 - x


def optimise_atari_playfield(image: Image.Image, palette: Palette = ATARI_NTSC,
                             dither: str = "none", *, mode: str = "playfield",
                             row_height: int = 2, bayer_size: int = 4) -> AtariPlayfield:
    _check_mode(mode)
    if palette not in (ATARI_NTSC, ATARI_PAL):
        raise ValueError("Atari playfield requires an atari2600-ntsc or atari2600-pal palette")
    if image.width != 160:
        raise ValueError("Atari playfield requires a logical width of 160")
    if type(row_height) is not int or row_height <= 0:
        raise ValueError("Atari row height must be a positive integer")
    validate_dither(dither, bayer_size)
    source = image.convert("RGB")
    values = palette.rgb_values()
    rows = []
    count = 40 if mode == "playfield" else 20
    for y0 in range(0, image.height, row_height):
        groups = [[] for _ in range(count)]
        for y in range(y0, min(image.height, y0 + row_height)):
            for x in range(160):
                groups[_selector(x // 4, mode)].append(source.getpixel((x, y)))
        pair, means = fit_binary_groups(tuple(map(tuple, groups)), palette)
        if dither == "none":
            selectors = tuple(min(range(2), key=lambda i: colour_distance(mean, values[pair[i]]))
                              for mean in means)
        else:
            # Dither the independent logical bits, retaining shared-block structure.
            strip = Image.new("RGB", (count, 1))
            strip.putdata([tuple(round(c) for c in mean) for mean in means])
            selected = Palette(palette.name, tuple(palette.colours[i] for i in pair))
            selectors = quantize(strip, selected, dither, bayer_size=bayer_size,
                                 bayer_origin=(0, y0 // row_height)).pixels[0]
        pattern = sum(bit << x for x, bit in enumerate(selectors))
        rows.append(AtariPlayfieldRow(pair[0] * 2, pair[1] * 2, pattern))
    return AtariPlayfield(image.height, row_height, mode, tuple(rows), palette)


def rasterize_atari_playfield(frame: AtariPlayfield) -> IndexedImage:
    pixels = []
    for row in frame.rows:
        colours = (row.background // 2, row.foreground // 2)
        raster = tuple(colours[(row.pattern >> _selector(x // 4, frame.mode)) & 1]
                       for x in range(160))
        pixels.extend([raster] * min(frame.row_height, frame.height - len(pixels)))
    return IndexedImage(160, frame.height, frame.palette, tuple(pixels))


def quantize_atari_playfield(image: Image.Image, palette: Palette, dither: str = "none", *,
                            mode: str = "playfield", row_height: int = 2, bayer_size: int = 4) -> IndexedImage:
    return rasterize_atari_playfield(optimise_atari_playfield(
        image, palette, dither, mode=mode, row_height=row_height, bayer_size=bayer_size))
