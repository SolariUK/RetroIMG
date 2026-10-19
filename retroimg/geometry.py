from __future__ import annotations

import math

from PIL import Image

from retroimg.model import Geometry, TargetProfile


ASPECT_MODES = ('native', 'source')


def validate_aspect_mode(profile: TargetProfile, aspect_mode: str,
                         width: int | None, height: int | None) -> None:
    if aspect_mode not in ASPECT_MODES:
        raise ValueError(f'unknown aspect mode: {aspect_mode}')
    if aspect_mode == 'source':
        if profile.name != 'teletext':
            raise ValueError('source aspect matching is currently available only for Teletext')
        if width is not None or height is not None:
            raise ValueError('source aspect matching cannot be combined with custom width/height')


def match_source_geometry(source_size: tuple[int, int], reference: Geometry,
                          cell_size: tuple[int, int] = (2, 3)) -> Geometry:
    """Find a nearby whole-cell canvas with at most 2% pixel-shape correction.

    Keep native height for landscape inputs, native width for portraits. Limit
    the canvas to twice the native pixel count and 512 pixels per edge. Search
    within 10% of that size for a better aspect match, preferring exact ratios.
    The resolved pixel aspect is used for both fitting and final rendering.
    """
    sw, sh = source_size
    cw, ch = cell_size
    if any(type(n) is not int or n <= 0 for n in (sw, sh, cw, ch)):
        raise ValueError('source and cell dimensions must be positive whole numbers')
    ratio = sw / sh / reference.pixel_aspect
    height = max(reference.height, reference.width / ratio)
    width = height * ratio
    pixel_limit = 2 * reference.width * reference.height
    shrink = min(1, math.sqrt(pixel_limit / (width * height)), 512 / width, 512 / height)
    height *= shrink
    first = max(ch, math.ceil(height * .9 / ch) * ch)
    last = max(first, math.floor(height * 1.1 / ch) * ch)
    candidates = []
    for h in range(first, min(512, last) + 1, ch):
        w = max(cw, round(h * ratio / cw) * cw)
        if w > 512 or w * h > pixel_limit:
            continue
        aspect = sw * h / (sh * w)
        correction = abs(math.log(aspect / reference.pixel_aspect))
        if correction <= math.log(1.02):
            candidates.append((correction, abs(h - height), w, h, aspect))
    if not candidates:
        raise ValueError('Source aspect is too extreme for a Teletext canvas near native resolution. '
                         'Use native or custom dimensions with Cover or Contain.')
    _, _, width, height, aspect = min(candidates)
    return Geometry(width, height, pixel_aspect=aspect)


def resize_to_geometry(image: Image.Image, geometry: Geometry, fit: str = "cover") -> Image.Image:
    """Resize an image to target geometry with pixel-aspect-aware fitting.

    fit='cover' fills the target and centre-crops overflow.
    fit='contain' letterboxes using black.
    fit='stretch' ignores source aspect ratio.
    """
    image = image.convert("RGB")
    tw, th = geometry.width, geometry.height

    if fit == "stretch":
        return image.resize((tw, th), Image.Resampling.LANCZOS)
    if fit not in {"cover", "contain"}:
        raise ValueError(f"unknown fit mode: {fit}")

    # Account for non-square target pixels when comparing visual aspect ratios.
    target_visual_aspect = (tw * geometry.pixel_aspect) / th
    source_aspect = image.width / image.height

    if fit == "cover":
        if source_aspect > target_visual_aspect:
            new_h = th
            new_w = max(tw, round(new_h * source_aspect / geometry.pixel_aspect))
        else:
            new_w = tw
            new_h = max(th, round((new_w * geometry.pixel_aspect) / source_aspect))
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return resized.crop((left, top, left + tw, top + th))

    if source_aspect > target_visual_aspect:
        new_w = tw
        new_h = max(1, round((new_w * geometry.pixel_aspect) / source_aspect))
    else:
        new_h = th
        new_w = max(1, round(new_h * source_aspect / geometry.pixel_aspect))
    resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (tw, th), (0, 0, 0))
    canvas.paste(resized, ((tw - new_w) // 2, (th - new_h) // 2))
    return canvas
