"""Optional display simulation for RGB previews, independent of conversion targets."""
from __future__ import annotations

import math

from PIL import Image

DISPLAY_EFFECTS = ('none', 'gameboy-lcd', 'scanlines', 'crt-aperture')
DEFAULT_EFFECT_STRENGTH = 0.35
MINIMUM_EFFECT_SCALES = {'none': 1, 'gameboy-lcd': 3, 'scanlines': 3, 'crt-aperture': 3}
_LINEAR_SRGB = tuple(v / 255 / 12.92 if v / 255 <= .04045 else ((v / 255 + .055) / 1.055) ** 2.4
                     for v in range(256))


def validate_display_brightness(value: float) -> None:
    valid = type(value) in (int, float)
    try:
        valid = valid and math.isfinite(value) and value >= 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('display brightness must be finite and non-negative')


def _light_table(multiplier: float) -> bytes:
    values = (min(1.0, value * multiplier) for value in _LINEAR_SRGB)
    return bytes(round(255 * (12.92 * value if value <= .0031308 else
                             1.055 * value ** (1 / 2.4) - .055)) for value in values)


def apply_display_brightness(preview: Image.Image, brightness: float) -> Image.Image:
    """Final linear-light gain after enlargement and display effects, before saving."""
    validate_display_brightness(brightness)
    if brightness == 1:
        return preview
    return preview.point(list(_light_table(brightness)) * 3)


def validate_display_effect(effect: str, strength: float | None, scale: int) -> float:
    if effect not in DISPLAY_EFFECTS:
        raise ValueError(f'unknown display effect: {effect}')
    if strength is not None:
        if type(strength) not in (int, float) or not 0 <= strength <= 1 or not math.isfinite(strength):
            raise ValueError('effect strength must be finite and between 0 and 1')
        if effect == 'none':
            raise ValueError('effect strength requires a display effect')
    if effect != 'none' and scale < MINIMUM_EFFECT_SCALES[effect]:
        raise ValueError(f'{effect} requires preview scale {MINIMUM_EFFECT_SCALES[effect]} or greater (6 or 8 recommended)')
    return DEFAULT_EFFECT_STRENGTH if strength is None else strength


def _coverage(length: int, cells: int, start: float, end: float) -> list[float]:
    """Area coverage of repeating cell rectangles, including fractional scaling."""
    step = cells / length

    def integral(position):
        whole = math.floor(position)
        return whole * (end - start) + min(end - start, max(0.0, position - whole - start))

    return [max(0.0, min(1.0, (integral((i + 1) * step) - integral(i * step)) / step))
            for i in range(length)]


def gameboy_lcd(preview: Image.Image, logical_size: tuple[int, int],
                background: tuple[int, int, int], strength: float) -> Image.Image:
    """Inset LCD cells over a tinted substrate with a small lower-right shadow.

    Geometry follows the original pixel grid, not a fixed output-pixel overlay.
    This is an aesthetic static approximation, without temporal LCD response.
    The caller validates settings and supplies the palette's lightest colour.
    """
    if strength == 0:
        return preview
    width, height = preview.size
    cell_x = _coverage(width, logical_size[0], 0.09, 0.91)
    cell_y = _coverage(height, logical_size[1], 0.09, 0.91)
    shadow_x = _coverage(width, logical_size[0], 0.15, 0.97)
    shadow_y = _coverage(height, logical_size[1], 0.15, 0.97)
    substrate = tuple(channel * 0.94 for channel in background)
    pixels = preview.load()
    output = bytearray(width * height * 3)
    position = 0
    for y in range(height):
        for x in range(width):
            colour = pixels[x, y]
            coverage = cell_x[x] * cell_y[y]
            shadow = shadow_x[x] * shadow_y[y]
            for channel, base in zip(colour, substrate):
                # Dark cells cast more visible shadows on the substrate.
                backdrop = base - max(0.0, base - channel) * shadow * 0.22
                lcd = channel * coverage + backdrop * (1 - coverage)
                output[position] = round(channel + strength * (lcd - channel))
                position += 1
    return Image.frombytes('RGB', preview.size, bytes(output))


def scanlines(preview: Image.Image, logical_height: int, strength: float) -> Image.Image:
    """One smooth beam per logical row, with area sampling in linear light.

    Row centres stay brightest and row boundaries are dimmed. Integration over
    each output pixel keeps the pattern tied to the logical grid even with
    fractional aspect correction. This does not interpolate source rows.
    """
    return _crt(preview, logical_height, strength, mask_strength=0)


def crt_aperture(preview: Image.Image, logical_height: int, strength: float) -> Image.Image:
    """Combine logical-row scanlines and an output-space RGB aperture grille.

    One output column per stripe, repeating R/G/B from the left image edge.
    Attenuate the other two channels in each stripe without boosting highlights.
    Apply both weights in linear light, with one final sRGB quantisation.
    """
    return _crt(preview, logical_height, strength, mask_strength=strength)


def _crt(preview: Image.Image, logical_height: int, strength: float, *, mask_strength: float) -> Image.Image:
    if strength == 0:
        return preview
    step = logical_height / preview.height
    output = Image.new('RGB', preview.size)
    tables = {}

    for y in range(preview.height):
        # Mean of (1 + cos(2*pi*t))/2 over this output pixel's footprint.
        start, end = y * step, (y + 1) * step
        trough = .5 + (math.sin(math.tau * end) - math.sin(math.tau * start)) / (2 * math.tau * step)
        weight = round(1 - strength * min(1.0, max(0.0, trough)), 12)
        if weight not in tables:
            bright = _light_table(weight)
            dim = _light_table(weight * (1 - mask_strength)) if mask_strength else bright
            tables[weight] = bright, dim
        bright, dim = tables[weight]
        row = preview.crop((0, y, preview.width, y + 1))
        if mask_strength:
            source = row.tobytes()
            masked = bytearray(len(source))
            # Each three-column RGB repeat occupies nine bytes in an RGB row.
            # Translate each channel at its stripe positions using the proper LUT.
            for stripe in range(3):
                for channel in range(3):
                    start = stripe * 3 + channel
                    table = bright if channel == stripe else dim
                    masked[start::9] = source[start::9].translate(table)
            row = Image.frombytes('RGB', row.size, bytes(masked))
        else:
            row = row.point(list(bright) * 3)
        output.paste(row, (0, y))
    return output
