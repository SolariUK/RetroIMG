"""Optional display simulation for RGB previews, independent of conversion targets."""
from __future__ import annotations

import math
from array import array

from PIL import Image, ImageFilter

DISPLAY_EFFECTS = ('none', 'gameboy-lcd', 'scanlines', 'crt-aperture')
DEFAULT_EFFECT_STRENGTH = 0.35
DEFAULT_BLOOM_RADIUS = 1.0
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


def validate_bloom(strength: float, radius: float) -> None:
    if type(strength) not in (int, float) or not 0 <= strength <= 1:
        raise ValueError('bloom strength must be finite and between 0 and 1')
    if type(radius) not in (int, float) or not .25 <= radius <= 8:
        raise ValueError('bloom radius must be finite and between 0.25 and 8 logical pixel widths')


def validate_chromatic_strength(strength: float) -> None:
    if type(strength) not in (int, float) or not 0 <= strength <= 1:
        raise ValueError('chromatic strength must be finite and between 0 and 1')


def _extend_edges(channel: Image.Image, pad_x: int, pad_y: int) -> Image.Image:
    """Repeat the nearest edge sample without wrapping or introducing black borders."""
    width, height = channel.size
    padded = Image.new(channel.mode, (width + 2 * pad_x, height + 2 * pad_y))
    padded.paste(channel, (pad_x, pad_y))
    nearest = Image.Resampling.NEAREST
    padded.paste(channel.crop((0, 0, 1, height)).resize((pad_x, height), nearest), (0, pad_y))
    padded.paste(channel.crop((width - 1, 0, width, height)).resize((pad_x, height), nearest),
                 (pad_x + width, pad_y))
    padded.paste(padded.crop((0, pad_y, padded.width, pad_y + 1)).resize((padded.width, pad_y), nearest), (0, 0))
    padded.paste(padded.crop((0, pad_y + height - 1, padded.width, pad_y + height)).resize(
        (padded.width, pad_y), nearest), (0, pad_y + height))
    return padded


def chromatic_aberration(preview: Image.Image, logical_width: int, strength: float) -> Image.Image:
    """Radial RGB separation, before the display surface mask.

    Red expands by 1 + 2*strength/logical_width; blue contracts by its reciprocal.
    Green is unchanged. Floating-point linear-light bilinear sampling gives smooth
    fractional offsets and edge extension avoids spurious dark borders or wrapping.
    """
    if strength == 0 or preview.size == (1, 1):
        return preview
    zoom = 1 + 2 * strength / logical_width
    channels = list(preview.split())
    width, height = preview.size
    # This covers the largest inverse-map excursion, plus a bilinear sample.
    pad_x = math.ceil((zoom - 1) * width / 2) + 1
    pad_y = math.ceil((zoom - 1) * height / 2) + 1
    for index, factor in ((0, 1 / zoom), (2, zoom)):
        linear = channels[index].point(list(_LINEAR_SRGB), 'F')
        extended = _extend_edges(linear, pad_x, pad_y)
        shifted = extended.transform(preview.size, Image.Transform.AFFINE,
                                     (factor, 0, (1 - factor) * width / 2 + pad_x,
                                      0, factor, (1 - factor) * height / 2 + pad_y),
                                     Image.Resampling.BILINEAR)
        values = array('f')
        values.frombytes(shifted.tobytes())
        encoded = bytes(round(255 * (12.92 * value if value <= .0031308 else
                                    1.055 * value ** (1 / 2.4) - .055))
                        for value in (max(0.0, min(1.0, sample)) for sample in values))
        channels[index] = Image.frombytes('L', preview.size, encoded)
    return Image.merge('RGB', channels)


def bloom(preview: Image.Image, logical_width: int, strength: float, radius: float) -> Image.Image:
    """Add a blurred, hue-preserving highlight layer in linear light.

    Radius is Gaussian sigma in logical pixel widths, converted to output space.
    Extract energy above half the linear-light peak channel, preserving RGB ratios.
    Pillow blurs an 8-bit linear RGB highlight buffer; the original stays sharp.
    """
    if strength == 0:
        return preview
    source = preview.tobytes()
    highlights = bytearray(len(source))
    for pos in range(0, len(source), 3):
        rgb = tuple(_LINEAR_SRGB[value] for value in source[pos:pos + 3])
        peak = max(rgb)
        if peak > .5:
            fraction = (peak - .5) / peak
            highlights[pos:pos + 3] = bytes(round(255 * value * fraction) for value in rgb)
    if not any(highlights):
        return preview
    glow = Image.frombytes('RGB', preview.size, bytes(highlights)).filter(
        ImageFilter.GaussianBlur(radius * preview.width / logical_width))
    # A lookup avoids per-channel transfer-function arithmetic over the full image.
    encode = bytes(round(255 * (12.92 * value if value <= .0031308 else
                                1.055 * value ** (1 / 2.4) - .055))
                   for value in (i / 65535 for i in range(65536)))
    result = bytes(encode[round(min(1.0, _LINEAR_SRGB[value] + strength * halo / 255) * 65535)]
                   for value, halo in zip(source, glow.tobytes()))
    return Image.frombytes('RGB', preview.size, result)


def apply_display_effects(preview: Image.Image, logical_size: tuple[int, int],
                          background: tuple[int, int, int], *, effect: str, strength: float,
                          bloom_strength: float, bloom_radius: float, brightness: float,
                          chromatic_strength: float = 0.0) -> Image.Image:
    """Fixed chain: RGB separation, display surface, highlight bloom, final gain.

    The public rendering/conversion boundaries validate settings before reaching here.
    Independent stages allow further optical treatments without changing conversion.
    """
    preview = chromatic_aberration(preview, logical_size[0], chromatic_strength)
    if effect == 'gameboy-lcd':
        preview = gameboy_lcd(preview, logical_size, background, strength)
    elif effect == 'scanlines':
        preview = scanlines(preview, logical_size[1], strength)
    elif effect == 'crt-aperture':
        preview = crt_aperture(preview, logical_size[1], strength)
    preview = bloom(preview, logical_size[0], bloom_strength, bloom_radius)
    return apply_display_brightness(preview, brightness)


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
