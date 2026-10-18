"""Qt-free rendering jobs and per-window conversion cache for desktop workers."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time

from PIL import Image

from retroimg.cli import build_parser
from retroimg.convert import convert_to_indexed
from retroimg.model import Colour, IndexedImage, Palette
from retroimg.pixelate import pixelate_image
from retroimg.profiles import get_profile
from retroimg.render import render_indexed
from retroimg.settings import default_settings, normalize_settings

DISPLAY_OPTIONS = frozenset(('scale', 'display_effect', 'effect_strength', 'display_brightness',
                             'bloom_strength', 'bloom_radius', 'chromatic_strength', 'rf_strength'))


def atomic_json(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.retroimg-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fingerprint(source: Path) -> tuple:
    stat = source.stat()
    return (str(source.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)


def _encode_indexed(indexed: IndexedImage) -> dict:
    return dict(width=indexed.width, height=indexed.height, pixels=indexed.pixels,
                palette=dict(name=indexed.palette.name, description=indexed.palette.description,
                             rgb_levels=indexed.palette.rgb_levels,
                             colours=[dict(name=c.name, rgb=c.rgb) for c in indexed.palette.colours]))


def _decode_indexed(data: dict) -> IndexedImage:
    palette = data['palette']
    levels = palette['rgb_levels']
    result = IndexedImage(data['width'], data['height'],
                          Palette(palette['name'], tuple(Colour(c['name'], tuple(c['rgb'])) for c in palette['colours']),
                                  palette['description'], tuple(levels) if levels is not None else None),
                          tuple(tuple(row) for row in data['pixels']))
    result.validate()
    return result


def render_job(job: dict) -> dict:
    """Render full output pixels; only conversion settings invalidate the indexed cache."""
    start = time.monotonic()
    source = Path(job['source'])
    fingerprint = _fingerprint(source)
    reused = False
    if job['kind'] == 'pixelate':
        with Image.open(source) as image:
            result = pixelate_image(image, job['block_size'])
        logical_size = result.size
        palette_size = None
    elif job['kind'] == 'retro':
        settings = normalize_settings(job['settings'], default_settings(build_parser()))
        conversion = {key: value for key, value in settings.items() if key not in DISPLAY_OPTIONS}
        key = sha256(json.dumps([fingerprint, conversion], sort_keys=True).encode()).hexdigest()
        cache_path = Path(job['cache'])
        cached = None
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding='utf-8'))
                indexed = _decode_indexed(cached['indexed']) if cached['key'] == key else None
            except (OSError, ValueError, KeyError, TypeError):
                indexed = None
        else:
            indexed = None
        if indexed is None:
            conversion['profile_name'] = conversion.pop('profile')
            conversion['palette_name'] = conversion.pop('palette')
            indexed = convert_to_indexed(source, **conversion)
            if _fingerprint(source) != fingerprint:
                raise ValueError('The source image changed during conversion. Please refresh the preview.')
            atomic_json(cache_path, dict(key=key, indexed=_encode_indexed(indexed)))
        else:
            reused = True
        profile = get_profile(settings['profile'])
        aspect = profile.geometry.pixel_aspect if profile.aspect_correct_preview else 1
        result = render_indexed(indexed, pixel_aspect=aspect, **{key: settings[key] for key in DISPLAY_OPTIONS})
        logical_size = (indexed.width, indexed.height)
        palette_size = len(indexed.palette.colours)
    else:
        raise ValueError('Unknown desktop conversion type')
    if _fingerprint(source) != fingerprint:
        raise ValueError('The source image changed while rendering. Please refresh the preview.')
    target = Path(job['image'])
    temporary = target.with_suffix('.tmp')
    try:
        result.save(temporary, format='PNG')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(image=str(target), size=list(result.size), logical_size=list(logical_size),
                palette_size=palette_size, reused_conversion=reused, elapsed=time.monotonic() - start)


def run_job(path: Path) -> int:
    job = json.loads(path.read_text(encoding='utf-8'))
    response = Path(job['response'])
    try:
        result = render_job(job)
    except Exception as exc:
        atomic_json(response, dict(error=str(exc) or type(exc).__name__))
        return 1
    atomic_json(response, result)
    return 0
