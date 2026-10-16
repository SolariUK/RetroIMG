from __future__ import annotations

from PIL import Image

from retroimg.model import Geometry


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
