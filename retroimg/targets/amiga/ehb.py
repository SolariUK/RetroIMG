"""EHB register fitting with linked, hardware-rounded half-bright colours."""
from dataclasses import dataclass

from PIL import Image

from retroimg.ordered import validate_dither

from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.constraints.histogram import rgb_histogram
from retroimg.model import IndexedImage, Palette
from retroimg.palettes.amiga import AMIGA, AMIGA_RGB
from retroimg.quantize import colour_distance, quantize
from .common import validate_screen


def half_bright(value: int) -> int:
    """Shift each four-bit component right, without spilling between channels."""
    return (value >> 1) & 0x777


def _palette(registers: tuple[int, ...]) -> Palette:
    values = (*registers, *(half_bright(value) for value in registers))
    return Palette('amiga-ehb', tuple(AMIGA.colours[value] for value in values),
                   '32 EHB base colours and 32 linked half-bright colours.')


@dataclass(frozen=True)
class AmigaEHBImage:
    """Codes 0..31 select registers; codes 32..63 select their half-bright copy.

    Always retain all 32 physical register slots. Duplicate/unused colours
    are legal; a future encoder can write the codes as six planar bits.
    """
    width: int
    height: int
    registers: tuple[int, ...]
    codes: tuple[tuple[int, ...], ...]

    def __post_init__(self) -> None:
        validate_screen(self.width, self.height, self.registers, self.codes, 32)

    @property
    def bitplanes(self) -> int:
        return 6

    @property
    def palette(self) -> Palette:
        return _palette(self.registers)


def fit_ehb_registers(image: Image.Image, *, max_samples: int | None = 4096,
                      max_iterations: int = 8) -> tuple[int, ...]:
    """Refine a 32-colour seed against the combined base/half-bright palette.

    Full and half-bright assignments share a parent register. For each channel,
    evaluate all 16 legal base levels against both groups together. Accept only
    strictly improving palette updates on the fitting histogram. This bounded
    heuristic optimises EHB pairs, not 64 independent screen colours.
    """
    if type(max_iterations) is not int or max_iterations < 0:
        raise ValueError('max_iterations must be a non-negative integer')
    seed = fit_rgb_palette(image, AMIGA_RGB, 32, max_samples=max_samples)
    registers = tuple(AMIGA_RGB.nearest_index(rgb) for rgb in seed)
    registers += (0,) * (32 - len(registers))
    samples = rgb_histogram(image.convert('RGB'), max_samples)

    def score(table):
        values = _palette(table).rgb_values()
        return sum(n * min(colour_distance(rgb, value) for value in values) for n, rgb in samples)

    error = score(registers)
    for _ in range(max_iterations):
        values = _palette(registers).rgb_values()
        groups = [[] for _ in range(64)]
        for sample in samples:
            index = min(range(64), key=lambda i: colour_distance(sample[1], values[i]))
            groups[index].append(sample)
        updated = []
        for index, old in enumerate(registers):
            full, half = groups[index], groups[index + 32]
            if not full and not half:
                updated.append(old)
                continue
            word = 0
            for channel in range(3):
                # The squared sums are constant over candidates and cancel.
                nf, nh = sum(n for n, _ in full), sum(n for n, _ in half)
                sf = sum(n * rgb[channel] for n, rgb in full)
                sh = sum(n * rgb[channel] for n, rgb in half)
                def cost(level):
                    a, b = level * 17, (level >> 1) * 17
                    return nf * a * a - 2 * a * sf + nh * b * b - 2 * b * sh
                level = min(range(16), key=cost)
                word = (word << 4) | level
            updated.append(word)
        updated = tuple(updated)
        updated_error = score(updated)
        if updated_error >= error:
            break
        registers, error = updated, updated_error
    return registers


def optimise_ehb(image: Image.Image, palette: Palette = AMIGA, dither: str = 'none', *,
                 colours: int | None = None, bayer_size: int = 4) -> AmigaEHBImage:
    if palette != AMIGA:
        raise ValueError('Amiga EHB mode requires the amiga palette')
    if colours is not None:
        raise ValueError('--colours is not supported in EHB mode; it uses 32 linked base registers')
    validate_dither(dither, bayer_size)
    registers = fit_ehb_registers(image)
    indexed = quantize(image, _palette(registers), dither, bayer_size=bayer_size)
    return AmigaEHBImage(image.width, image.height, registers, indexed.pixels)


def rasterize_ehb(image: AmigaEHBImage) -> IndexedImage:
    return IndexedImage(image.width, image.height, image.palette, image.codes)


def quantize_ehb(image: Image.Image, palette: Palette, dither: str = 'none', *,
                 colours: int | None = None, bayer_size: int = 4) -> IndexedImage:
    return rasterize_ehb(optimise_ehb(image, palette, dither, colours=colours, bayer_size=bayer_size))
