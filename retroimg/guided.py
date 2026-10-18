"""Interactive command builder. Conversion stays in the ordinary CLI path."""
from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import shlex
from typing import Callable, Sequence

from PIL import Image

from retroimg.conversion_modes import (
    COLOUR_COUNT_QUANTIZERS, CONSTRAINED_QUANTIZERS, MODE_OPTIONS,
    get_profile_quantizer,
)
from retroimg.model import TargetProfile
from retroimg.ordered import BAYER_SIZES, DITHER_MODES
from retroimg.palettes import PALETTES
from retroimg.profiles import PROFILES
from retroimg.targets.amiga import AMIGA_COLOUR_LIMITS
from retroimg.settings import CELL_DIMENSIONS, REQUIRED_PALETTES, CONSTRAINT_PALETTES
from retroimg.display_effects import DEFAULT_BLOOM_RADIUS, DEFAULT_EFFECT_STRENGTH, MINIMUM_EFFECT_SCALES
from retroimg.presets import list_presets, load_preset, preset_directory, preset_slug, save_preset

# Presentation and input hints only. Target adapters remain the authority on
# constraints; the wizard does not fit palettes, quantise, render or save images.
FAMILY_LABELS = {
    'teletext': 'Teletext', 'spectrum': 'ZX Spectrum', 'c64': 'Commodore 64',
    'cpc': 'Amstrad CPC', 'bbc': 'BBC Micro', 'amiga': 'Amiga', 'atari2600': 'Atari 2600',
    'megadrive': 'Sega Mega Drive / Genesis', 'snes': 'Super Nintendo / SNES',
    'nes': 'Nintendo / NES', 'mastersystem': 'Sega Master System', 'gameboy': 'Original Game Boy',
    'cga': 'IBM CGA', 'ega': 'IBM EGA',
}
MODE_HELP = {
    'bitmap': 'unrestricted palette conversion',
    'tiles': '8x8 tiles, each selecting one shared 16-entry palette bank and backdrop',
    'indexed': 'up to 256 image-selected colours for one 8bpp background layer',
    'mosaic': 'two colours per 2x3 cell',
    'attributes': 'ink/paper with shared brightness per 8x8 cell',
    'multicolour': 'shared background plus three local colours per 4x8 cell',
    'constrained': 'apply this display mode\'s screen-colour limit',
    'ehb': '32 base colours and their linked half-bright colours (lores)',
    'ham': 'HAM6: base colours and changes to the held colour (lores)',
    'playfield': '40 independent blocks with two colours per band',
    'repeat': '20 playfield blocks repeated in the right half',
    'mirror': '20 playfield blocks mirrored in the right half',
}


class GuidedCancelled(Exception):
    """The user ended the command builder without requesting conversion."""


class Prompts:
    """Small terminal UI, with injectable I/O and completion for path prompts."""

    def __init__(self, read: Callable[[str], str] | None = None,
                 write: Callable[[str], None] | None = None):
        self.read = input if read is None else read
        self.write = print if write is None else write
        self._complete_paths = read is None

    def answer(self, prompt: str, *, path: bool = False) -> str:
        if path and self._complete_paths:
            try:
                from retroimg.path_input import read_path
            except ModuleNotFoundError as exc:
                if exc.name != 'prompt_toolkit':
                    raise
                # The guide also works without the optional completion extra.
                prompt = prompt.replace('Tab to complete; ', '').replace(' (Tab to complete)', '')
                value = self.read(prompt).strip()
            else:
                value = read_path(prompt, fallback=self.read).strip()
        else:
            value = self.read(prompt).strip()
        if value.lower() in {'q', 'quit', 'cancel'}:
            raise GuidedCancelled
        return value

    def choice(self, title: str, choices: Sequence[tuple[str, str]], default: str) -> str:
        self.write('\n' + title)
        numeric_values = all(value.isdecimal() for value, _ in choices)
        for index, (value, label) in enumerate(choices, 1):
            prefix = '  ' if numeric_values else f'  {index}. '
            self.write(prefix + label + (' [default]' if value == default else ''))
        while True:
            answer = self.answer(f'Choose {title.lower()} [{default}]: ')
            if not answer:
                return default
            for value, label in choices:
                if answer.lower() in {value.lower(), label.lower()}:
                    return value
            if not numeric_values and answer.isdecimal() and 1 <= int(answer) <= len(choices):
                return choices[int(answer) - 1][0]
            self.write('Choose a listed number or value, or press Enter for the default.')

    def yes_no(self, title: str, default: bool = False) -> bool:
        while True:
            answer = self.answer(f'{title} [{"Y/n" if default else "y/N"}]: ').lower()
            if not answer:
                return default
            if answer in {'y', 'yes'}:
                return True
            if answer in {'n', 'no'}:
                return False
            self.write('Enter yes or no.')

    def number(self, title: str, default: int | float, *, integer: bool = False,
               valid: Callable[[float], bool] = lambda value: True,
               hint: str = 'Enter a finite number.') -> int | float:
        while True:
            answer = self.answer(f'{title} [{default}]: ')
            try:
                value = default if not answer else (int(answer) if integer else float(answer))
                if math.isfinite(value) and valid(value):
                    return value
            except (ValueError, OverflowError):
                pass
            self.write(hint)


def profile_families() -> dict[str, tuple[TargetProfile, ...]]:
    families: dict[str, list[TargetProfile]] = {}
    for profile in PROFILES.values():
        families.setdefault(profile.name.split('-', 1)[0], []).append(profile)
    return {name: tuple(profiles) for name, profiles in sorted(families.items())}


def profile_modes(profile: TargetProfile) -> tuple[str | None, tuple[str, ...]]:
    for option, spec in MODE_OPTIONS.items():
        if profile.constraint_model in spec.constraint_models:
            modes = tuple(mode for mode in spec.modes if mode == 'bitmap'
                          or (profile.constraint_model, mode) in CONSTRAINED_QUANTIZERS)
            return option, modes
    return None, ('bitmap',)


def palette_choices(profile: TargetProfile, mode: str, option: str | None) -> tuple[str, ...]:
    names = (CONSTRAINT_PALETTES.get(profile.constraint_model, REQUIRED_PALETTES.get(option, tuple(PALETTES))) if mode != 'bitmap'
             else tuple(PALETTES))
    return tuple(sorted(names, key=lambda name: (name != profile.default_palette, name)))


def _geometry_options(ui: Prompts, profile: TargetProfile, mode: str,
                      option: str | None, previous: dict) -> dict:
    same_profile = previous.get('profile') == profile.name
    dimensions: dict = {}
    geometry = profile.geometry
    ui.write(f'Logical resolution: {geometry.width}x{geometry.height}.')
    if ui.yes_no('Use a custom logical resolution?', same_profile and 'width' in previous):
        multiples = CELL_DIMENSIONS.get(profile.constraint_model, (1, 1)) if mode != 'bitmap' else (1, 1)
        fixed_width = 160 if option == 'atari_mode' and mode != 'bitmap' else None
        if fixed_width is not None:
            dimensions['width'] = fixed_width
            ui.write('Playfield width is fixed at 160 logical pixels.')
        else:
            step = multiples[0]
            default_width = previous.get('width', geometry.width) if same_profile else geometry.width
            if default_width % step:
                default_width = geometry.width
            dimensions['width'] = ui.number('Logical width', default_width,
                integer=True, valid=lambda n: n > 0 and n % step == 0,
                hint=f'Enter a positive whole number divisible by {step}.')
        step = multiples[1]
        default_height = previous.get('height', geometry.height) if same_profile else geometry.height
        if default_height % step:
            default_height = geometry.height
        dimensions['height'] = ui.number('Logical height', default_height,
            integer=True, valid=lambda n: n > 0 and n % step == 0,
            hint=f'Enter a positive whole number divisible by {step}.')
    return dimensions


def _adjustment_options(ui: Prompts, defaults: dict, preferred: dict) -> dict:
    result: dict = {}
    adjustments = ('brightness', 'contrast', 'saturation', 'hue_shift', 'red_gain', 'green_gain', 'blue_gain')
    adjusted = any(preferred[key] != defaults[key] for key in adjustments)
    if ui.yes_no('Adjust source colours?', adjusted):
        for key in ('brightness', 'contrast'):
            result[key] = ui.number(f'{key.title()} (source, before palette conversion; 1=neutral)', preferred[key], valid=lambda n: n >= 0,
                                    hint='Enter a finite non-negative number.')
        result['saturation'] = ui.number('Saturation (1=neutral)', preferred['saturation'], valid=lambda n: n > 0,
                                           hint='Enter a finite number greater than zero.')
        result['hue_shift'] = ui.number('Hue shift in degrees (0=neutral)', preferred['hue_shift'])
        for channel in ('red', 'green', 'blue'):
            key = channel + '_gain'
            result[key] = ui.number(f'{channel.title()} gain (1=neutral)', preferred[key], valid=lambda n: n >= 0,
                                     hint='Enter a finite non-negative number.')
    return result


def collect_options(ui: Prompts, defaults: dict, previous: dict | None = None) -> dict:
    previous = {} if previous is None else previous
    preferred = dict(defaults, **previous)
    families = profile_families()
    family = ui.choice('Machine', [(name, FAMILY_LABELS.get(name, name)) for name in families],
                       preferred['profile'].split('-', 1)[0])
    profiles = families[family]
    default_profile = next((p for p in profiles if p.name == preferred['profile']), profiles[0])
    if len(profiles) > 1:
        name = ui.choice('Profile', [(p.name, f'{p.name}: {p.description}') for p in profiles],
                         default_profile.name)
    else:
        name = profiles[0].name
    profile = PROFILES[name]
    ui.write(f'\nProfile: {name}. {profile.description}')
    options: dict = {'profile': name}
    option, modes = profile_modes(profile)
    mode = 'bitmap'
    if option is not None:
        default_mode = preferred.get(option, 'bitmap')
        if default_mode not in modes:
            default_mode = 'bitmap'
        help_text = dict(MODE_HELP)
        if option == 'nes_mode':
            help_text['attributes'] = 'four shared palettes, three local colours plus backdrop per 16x16 region'
        elif option == 'mastersystem_mode':
            help_text['tiles'] = '8x8 tiles selecting either of two 16-colour palettes; all slots usable'
        elif option == 'gameboy_mode':
            help_text['tiles'] = 'four luminance shades, retained 2-bit codes; green or grey preview'
        elif option == 'cga_mode':
            help_text['constrained'] = 'standard four-colour palettes at 320x200, monochrome at 640x200'
        elif option == 'ega_mode':
            help_text['constrained'] = 'sixteen RGBI colours in 200 lines, or sixteen selected RGB6 colours in 350 lines'
        mode = ui.choice('Conversion mode', [(m, f'{m}: {help_text.get(m, m)}') for m in modes], default_mode)
        options[option] = mode
    else:
        ui.write('Conversion mode: bitmap (unrestricted palette conversion).')

    same_profile = previous.get('profile') == name
    palettes = palette_choices(profile, mode, option)
    default_palette = preferred.get('palette') if same_profile else profile.default_palette
    if default_palette not in palettes:
        default_palette = profile.default_palette
    if len(palettes) > 1:
        options['palette'] = ui.choice('Palette', [
            (p, f'{p}: {len(PALETTES[p].colours)} entries; {PALETTES[p].description}') for p in palettes
        ], default_palette)
    else:
        options['palette'] = palettes[0]
        ui.write(f'Palette: {palettes[0]} (required by this constraint).')

    if (profile.constraint_model, mode) in COLOUR_COUNT_QUANTIZERS:
        limit = AMIGA_COLOUR_LIMITS[profile.constraint_model.removeprefix('amiga-')]
        counts = tuple(2**n for n in range(1, limit.bit_length()))
        default_count = preferred.get('colours')
        if default_count not in counts:
            default_count = limit
        options['colours'] = int(ui.choice('Screen colours', [(str(n), str(n)) for n in counts], str(default_count)))
    if option == 'atari_mode' and mode != 'bitmap':
        options['atari_row_height'] = ui.number(
            'Row height in scanlines (1=finer, 4/8=chunkier)', preferred.get('atari_row_height') or 2,
            integer=True, valid=lambda n: n > 0, hint='Enter a positive whole number.')

    options.update(_geometry_options(ui, profile, mode, option, previous))
    options['fit'] = ui.choice('Image fitting', [
        ('cover', 'cover: fill the image and crop overflow'),
        ('contain', 'contain: keep the whole image, with black padding'),
        ('stretch', 'stretch: fill without preserving source proportions'),
    ], preferred['fit'])
    descriptions = {'none': 'nearest colour, no dithering', 'floyd-steinberg': 'spread error into neighbouring pixels',
                    'bayer': 'a regular repeating threshold pattern'}
    options['dither'] = ui.choice('Dithering', [(d, f'{d}: {descriptions[d]}') for d in DITHER_MODES], preferred['dither'])
    if options['dither'] == 'bayer':
        options['bayer_size'] = int(ui.choice('Bayer matrix', [(str(n), f'{n}x{n}') for n in BAYER_SIZES],
                                              str(preferred.get('bayer_size') or 4)))
    options.update(_adjustment_options(ui, defaults, preferred))
    effect = ui.choice('Display effect', [
        ('none', 'none: plain converted pixels'),
        ('gameboy-lcd', 'gameboy-lcd: pixel cells and shadows; recommended for Game Boy, available for any machine'),
        ('scanlines', 'scanlines: smooth horizontal beams aligned to the original image rows'),
        ('crt-aperture', 'crt-aperture: RGB aperture grille combined with scanlines'),
    ], preferred.get('display_effect', 'none'))
    minimum_scale = 1
    if effect != 'none':
        options['display_effect'] = effect
        options['effect_strength'] = ui.number(
            'Display effect strength (0 to 1)',
            preferred.get('effect_strength') if preferred.get('effect_strength') is not None else DEFAULT_EFFECT_STRENGTH,
            valid=lambda n: 0 <= n <= 1, hint='Enter a number between 0 and 1.')
        minimum_scale = MINIMUM_EFFECT_SCALES[effect]
        ui.write(f'{effect} needs scale {minimum_scale} or greater; 6 or 8 is recommended for close inspection.')
    geometry = profile.geometry
    width, height = options.get('width', geometry.width), options.get('height', geometry.height)
    aspect = geometry.pixel_aspect if profile.aspect_correct_preview else 1
    longest = max(width * max(1, aspect), height * max(1, 1 / aspect))
    suggested = max(minimum_scale, min(defaults['scale'], int(640 // longest)))
    scale_default = max(minimum_scale, previous.get('scale', suggested)) if same_profile else suggested
    options['scale'] = ui.number('Preview scale (integer enlargement)', scale_default,
                                 integer=True, valid=lambda n: n >= minimum_scale,
                                 hint=f'Enter a whole number of at least {minimum_scale}.')
    if preferred.get('bloom_radius', DEFAULT_BLOOM_RADIUS) != DEFAULT_BLOOM_RADIUS:
        options['bloom_radius'] = preferred['bloom_radius']
    if ui.yes_no('Add highlight bloom after the display effect?', preferred.get('bloom_strength', 0) > 0):
        options['bloom_strength'] = ui.number(
            'Bloom strength (0 to 1; 0=off)', preferred.get('bloom_strength') or .25,
            valid=lambda n: 0 <= n <= 1, hint='Enter a number between 0 and 1.')
        options['bloom_radius'] = ui.number(
            'Bloom radius (logical pixel widths, 0.25 to 8)', preferred.get('bloom_radius', DEFAULT_BLOOM_RADIUS),
            valid=lambda n: .25 <= n <= 8, hint='Enter a number between 0.25 and 8.')
    display_brightness = ui.number('Display brightness (after effects, linear-light gain; 1=neutral)',
                                   preferred['display_brightness'], valid=lambda n: n >= 0,
                                   hint='Enter a finite non-negative number.')
    if display_brightness != 1:
        options['display_brightness'] = display_brightness
    return options


def build_convert_arguments(input_path: Path, output_path: Path, options: dict) -> list[str]:
    """Produce ordinary argparse tokens, never shell-executed text.

    Absolute paths protect leading-dash filenames and make the printed command
    independent of the current directory. Equals syntax handles negative values
    in scientific notation as well as ordinary numeric settings.
    """
    return ['convert', str(input_path.expanduser().absolute()), str(output_path.expanduser().absolute()),
            *(f'--{key.replace("_", "-")}={value}' for key, value in options.items())]


def format_command(arguments: Sequence[str], *, platform: str | None = None) -> str:
    """Quote a copyable POSIX-shell or Windows PowerShell command."""
    tokens = ['retroimg', *arguments]
    if (os.name if platform is None else platform) == 'nt':
        return '& ' + ' '.join("'" + token.replace("'", "''") + "'" for token in tokens)
    return shlex.join(tokens)


def _input_path(ui: Prompts, supplied: Path | None) -> Path:
    value = supplied
    while True:
        if value is None:
            answer = ui.answer('Input image path (Tab to complete): ', path=True)
            if not answer:
                ui.write('Enter an image path.')
                continue
            value = Path(answer)
        path = value.expanduser().absolute()
        try:
            with Image.open(path) as image:
                size = image.size
                image.verify()
            ui.write(f'Input: {path} ({size[0]}x{size[1]})')
            return path
        except (OSError, ValueError) as exc:
            ui.write(f'Cannot read input image: {exc}')
            value = None


def _output_path(ui: Prompts, supplied: Path | None, source: Path) -> Path:
    value = supplied
    default = source.with_name(source.stem + '-retro.png')
    while True:
        if value is None:
            answer = ui.answer(f'Output image path (Tab to complete; PNG recommended) [{default}]: ', path=True)
            value = Path(answer) if answer else default
        path = value.expanduser().absolute()
        if path.resolve() == source.resolve():
            ui.write('Choose an output path different from the input image.')
        elif not path.parent.is_dir():
            ui.write('The output directory does not exist; choose an existing directory.')
        elif path.is_dir():
            ui.write('The output path is a directory; enter an image filename.')
        elif Image.registered_extensions().get(path.suffix.lower()) not in Image.SAVE:
            ui.write('Choose a supported output image extension, such as .png or .jpg.')
        else:
            return path
        value = None


def _summary(ui: Prompts, source: Path, output: Path, options: dict, defaults: dict) -> None:
    profile = PROFILES[options['profile']]
    width, height = options.get('width', profile.geometry.width), options.get('height', profile.geometry.height)
    aspect = profile.geometry.pixel_aspect if profile.aspect_correct_preview else 1
    scale = options['scale']
    preview = (round(width * scale * max(1, aspect)), round(height * scale * max(1, 1 / aspect)))
    ui.write('\nSettings summary')
    ui.write(f'  Input: {source}\n  Output: {output}')
    ui.write(f'  Profile: {profile.name}; palette: {options["palette"]}')
    labels = {'colours': 'Screen colours', 'atari_row_height': 'Row height in scanlines'}
    for key, value in options.items():
        if key in MODE_OPTIONS or key in labels:
            label = MODE_OPTIONS[key].label + ' mode' if key in MODE_OPTIONS else labels[key]
            ui.write(f'  {label}: {value}')
    ui.write(f'  Logical image: {width}x{height}; fitting: {options["fit"]}')
    ui.write(f'  Dithering: {options["dither"]}' + (f'; matrix: {options["bayer_size"]}x{options["bayer_size"]}'
                                                       if 'bayer_size' in options else ''))
    ui.write(f'  Source brightness: {options.get("brightness", defaults["brightness"])}; '
             f'contrast: {options.get("contrast", defaults["contrast"])}')
    ui.write(f'  Saturation: {options.get("saturation", defaults["saturation"])}; '
             f'hue shift: {options.get("hue_shift", defaults["hue_shift"])} degrees')
    ui.write('  RGB gains: ' + ', '.join(str(options.get(c + '_gain', defaults[c + '_gain'])) for c in ('red', 'green', 'blue')))
    ui.write(f'  Preview: {preview[0]}x{preview[1]} (scale {scale})')
    effect = options.get('display_effect', 'none')
    ui.write(f'  Display effect: {effect}' + (
        f'; strength: {options.get("effect_strength", DEFAULT_EFFECT_STRENGTH)}' if effect != 'none' else ''))
    ui.write(f'  Display brightness: {options.get("display_brightness", 1.0)} (after display effects)')
    ui.write(f'  Bloom: {options.get("bloom_strength", 0)}; radius: '
             f'{options.get("bloom_radius", DEFAULT_BLOOM_RADIUS)} logical pixel widths '
             '(after display treatment, before display brightness)')


def _save_new_preset(ui: Prompts, directory: Path, options: dict, parser, loaded):
    while True:
        suggested = loaded.name + ' copy' if loaded is not None else ''
        name = ui.answer(f'Preset name [{suggested}]: ') or suggested
        if not name:
            ui.write('Enter a non-empty preset name.')
            continue
        description = ui.answer('Preset description (optional): ')
        path = directory / (preset_slug(name) + '.json')
        try:
            saved = save_preset(path, name, description, options, parser)
            ui.write(f'Saved preset: {path}')
            return saved
        except FileExistsError:
            ui.write('A user preset with that filename already exists. Choose another name; no file replaced.')
        except (OSError, ValueError) as exc:
            ui.write(f'Could not save preset: {exc}')
            return None


def _guided_pixelation(ui: Prompts, source: Path, output: Path, *, print_only: bool) -> list[str] | None:
    block_size = 8
    while True:
        block_size = ui.number('Pixel block size (source pixels, 1=neutral)', block_size,
                               integer=True, valid=lambda n: n > 0, hint='Enter a positive whole number.')
        arguments = ['pixelate', str(source), str(output), f'--block-size={block_size}']
        ui.write(f'\nPixelation: original RGB colours; {block_size}x{block_size} blocks; image dimensions preserved.')
        ui.write('Each block uses its average source colour; no system palette or dithering is applied.')
        ui.write('\nEquivalent command:\n' + format_command(arguments))
        if print_only:
            ui.write('Command only; no image written.')
            return None
        action = ui.choice('Next action', [('convert', 'Pixelate now'), ('edit', 'Revise block size'),
                                          ('command', 'Keep the command only'), ('cancel', 'Cancel')], 'convert')
        if action == 'edit':
            continue
        if action == 'convert':
            if output.exists() and not ui.yes_no('Output already exists. Replace it?'):
                ui.write('No image written.')
                return None
            return arguments
        ui.write('Command only; no image written.' if action == 'command' else 'Cancelled; no image written.')
        return None


def run_guided(input_path: Path | None, output_path: Path | None, *,
               parser: argparse.ArgumentParser, print_only: bool = False,
               ui: Prompts | None = None, preset_reference: str | None = None,
               presets_dir: Path | None = None) -> list[str] | None:
    """Return confirmed CLI arguments, or None after printing/cancellation."""
    ui = Prompts() if ui is None else ui
    ui.write('retroimg guided command builder\nPress Enter for defaults. Enter q at any prompt to cancel.')
    try:
        source = _input_path(ui, input_path)
        output = _output_path(ui, output_path, source)
        defaults = vars(parser.parse_args(['convert', str(source), str(output)]))
        directory = preset_directory() if presets_dir is None else presets_dir.expanduser()
        loaded = None
        if preset_reference:
            loaded = load_preset(preset_reference, parser, directory)
        else:
            start = ui.choice('Starting point', [('fresh', 'Start a retro conversion'), ('load', 'Load a preset'),
                                                 ('pixelate', 'Pixelate original image colours')], 'fresh')
            if start == 'pixelate':
                return _guided_pixelation(ui, source, output, print_only=print_only)
            if start == 'load':
                entries, errors = list_presets(parser, directory)
                for error in errors:
                    ui.write('Skipping unavailable preset: ' + error)
                selected = ui.choice('Preset', [(entry.identifier, f'{entry.name} [{entry.identifier}] - {entry.description}')
                                                for entry in entries], entries[0].identifier)
                loaded = next(entry for entry in entries if entry.identifier == selected)
        options = dict(loaded.settings) if loaded else collect_options(ui, defaults)
        if loaded:
            ui.write(f'Loaded preset: {loaded.name}. {loaded.description}')
        while True:
            arguments = build_convert_arguments(source, output, options)
            parsed = vars(parser.parse_args(arguments))
            get_profile_quantizer(PROFILES[parsed['profile']], colours=parsed['colours'],
                atari_row_height=parsed['atari_row_height'], bayer_size=parsed['bayer_size'],
                **{key: parsed[key] for key in MODE_OPTIONS})
            _summary(ui, source, output, options, defaults)
            shell = 'PowerShell' if os.name == 'nt' else 'POSIX shell'
            ui.write(f'\nEquivalent command ({shell}):\n' + format_command(arguments))
            if print_only:
                ui.write('Command only; no image written.')
                return None
            actions = [('convert', 'Convert now'), ('edit', 'Revise settings'),
                       ('command', 'Keep the command only'), ('cancel', 'Cancel'),
                       ('save', 'Save as a new preset')]
            if loaded is not None and loaded.path is not None:
                actions.append(('update', f'Update loaded preset: {loaded.name}'))
            action = ui.choice('Next action', actions, 'convert')
            if action == 'edit':
                options = collect_options(ui, defaults, options)
                continue
            if action == 'save':
                saved = _save_new_preset(ui, directory, options, parser, loaded)
                if saved is not None:
                    loaded = saved
                continue
            if action == 'update':
                if ui.yes_no(f'Update {loaded.name} at {loaded.path}?'):
                    try:
                        loaded = save_preset(loaded.path, loaded.name, loaded.description, options, parser, replace=True)
                        ui.write(f'Updated preset: {loaded.path}')
                    except (OSError, ValueError) as exc:
                        ui.write(f'Could not update preset: {exc}')
                continue
            if action == 'convert':
                if output.exists() and not ui.yes_no('Output already exists. Replace it?'):
                    ui.write('No image written.')
                    return None
                return arguments
            ui.write('Command only; no image written.' if action == 'command' else 'Cancelled; no image written.')
            return None
    except (GuidedCancelled, EOFError, KeyboardInterrupt):
        ui.write('\nCancelled; no image written.')
        return None
