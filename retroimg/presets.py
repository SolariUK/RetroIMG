"""Versioned, portable JSON presets; no image paths or conversion implementation."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from retroimg.settings import compact_settings, default_settings, normalize_settings

VERSION = 1
BUILTINS = {
    'cpc-macaws-bayer2': ('CPC macaws - blue boost',
        'CPC mode 1, Bayer 2x2, saturation 1.1 and blue gain 1.5; tuned on the bundled macaws.',
        dict(profile='cpc-mode1', cpc_mode='constrained', palette='cpc', fit='cover', dither='bayer',
             bayer_size=2, saturation=1.1, blue_gain=1.5, scale=2)),
    'c64-landscape-green': ('C64 landscape - green boost',
        'Multicolour with Floyd-Steinberg, hue +20 and green gain 1.15; a landscape starting point.',
        dict(profile='c64-multicolour', c64_mode='multicolour', dither='floyd-steinberg',
             hue_shift=20, green_gain=1.15, scale=2)),
    'teletext-mosaic-bayer4': ('Teletext mosaic - Bayer',
        'Two colours per 2x3 cell, with a 4x4 Bayer matrix and neutral source colours.',
        dict(profile='teletext', teletext_mode='mosaic', dither='bayer', bayer_size=4, scale=6)),
}


@dataclass(frozen=True)
class Preset:
    identifier: str
    name: str
    description: str
    settings: dict
    path: Path | None = None


def preset_directory() -> Path:
    if os.name == 'nt':
        root = Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming')
    else:
        root = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return root.expanduser() / 'retroimg' / 'presets'


def preset_slug(name: str) -> str:
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]+', '-', ascii_name).strip('-')[:80] or 'preset'


def _metadata(name, description) -> None:
    if type(name) is not str or not name.strip():
        raise ValueError('preset name must be a non-empty string')
    if type(description) is not str:
        raise ValueError('preset description must be a string')


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'duplicate preset key: {key}')
        value[key] = item
    return value


def load_file(path: Path, parser, *, identifier: str | None = None) -> Preset:
    def invalid_constant(value):
        raise ValueError(f'non-finite JSON value: {value}')
    try:
        data = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_object,
                          parse_constant=invalid_constant)
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot load preset {path}: {exc}') from exc
    if not isinstance(data, dict) or data.keys() - {'version', 'name', 'description', 'settings'}:
        raise ValueError('preset must be an object containing version, name, description and settings')
    if type(data.get('version')) is not int or data['version'] != VERSION:
        raise ValueError('unsupported preset version (expected 1)')
    _metadata(data.get('name'), data.get('description', ''))
    settings = normalize_settings(data.get('settings'), default_settings(parser))
    return Preset(identifier or str(path.absolute()), data['name'].strip(), data.get('description', ''),
                  compact_settings(settings), path.absolute())


def list_presets(parser, directory: Path | None = None) -> tuple[list[Preset], list[str]]:
    defaults = default_settings(parser)
    result = [Preset('builtin:' + key, name, description, compact_settings(normalize_settings(settings, defaults)))
              for key, (name, description, settings) in BUILTINS.items()]
    directory = preset_directory() if directory is None else directory.expanduser()
    errors = []
    try:
        paths = sorted(directory.glob('*.json')) if directory.exists() else []
        if directory.exists() and not directory.is_dir():
            raise OSError('preset location is not a directory')
        for path in paths:
            try:
                result.append(load_file(path, parser, identifier='user:' + path.stem))
            except ValueError as exc:
                errors.append(f'{path}: {exc}')
    except OSError as exc:
        errors.append(f'Cannot list presets in {directory}: {exc}')
    return result, errors


def load_preset(reference: str, parser, directory: Path | None = None) -> Preset:
    # An explicit filename must not silently fall back to a similarly named preset.
    path = Path(reference).expanduser()
    if path.is_file() or path.suffix.lower() == '.json' or '/' in reference or '\\' in reference:
        return load_file(path, parser)
    entries, errors = list_presets(parser, directory)
    matches = [p for p in entries if reference in (p.identifier, p.identifier.split(':', 1)[-1])]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError('ambiguous preset name; use builtin: or user: to select it')
    detail = ('; ' + '; '.join(errors)) if errors else ''
    raise ValueError(f'unknown preset: {reference}{detail}')


def save_preset(path: Path, name: str, description: str, settings: dict, parser, *, replace: bool = False) -> Preset:
    _metadata(name, description)
    values = compact_settings(normalize_settings(settings, default_settings(parser)))
    payload = json.dumps(dict(version=VERSION, name=name.strip(), description=description,
                              settings=values), indent=2, allow_nan=False) + '\n'
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(payload)
    else:
        # Replace a complete file, so an interrupted update retains the old preset.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                             prefix='.retroimg-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return Preset('user:' + path.stem, name.strip(), description, values, path)
