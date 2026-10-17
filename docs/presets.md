# Conversion presets

Presets are named, portable collections of conversion options. They use the same
converter as ordinary CLI commands. Source/output filenames and directory
preferences stay outside the preset.

## Guided use

Run `retroimg guided /path/to/image.jpg output.png`, choose **Load a preset**,
and select a name from the list. Built-in and user entries show their identifiers
and descriptions. The loaded settings open at the review screen; convert
immediately, revise settings, or keep the expanded command.

At review, **Save as a new preset** asks for a name and optional description.
Names become safe filenames, such as `My blue style` → `my-blue-style.json`.
An existing user filename is preserved; choose another name or load that preset
and explicitly update it. **Update loaded preset** requires confirmation and
writes to that file. Built-ins offer save-as-copy, and are never updated.

Saving a preset does not convert the image. After saving, the guide returns to
review so you can convert or leave with just the command. `--print-only` shows
loaded/collected settings without entering the final action menu or saving files.
Enter `q` or use Ctrl-C to cancel an interactive prompt.

## CLI use

```bash
retroimg presets
retroimg convert /path/to/image.jpg output.png --preset builtin:cpc-macaws-bayer2
retroimg guided /path/to/image.jpg output.png --preset user:my-blue-style
retroimg guided /path/to/image.jpg output.png \
    --preset /path/to/my-blue-style.json --print-only
retroimg convert /path/to/image.jpg output.png \
    --preset /path/to/my-blue-style.json --blue-gain 1.0 --scale 2
```

Identifiers include `builtin:` or `user:`. A short identifier also works when
unique; if both collections contain it, use its full identifier. Explicit JSON
filenames are loaded directly. Preset names/descriptions are display metadata;
use the listed identifier or filename on the CLI.

Explicit conversion flags override saved settings, including values equal to
normal defaults. For example, `--blue-gain 1.0` resets a saved blue boost.
Changing dithering clears an inherited Bayer size when it no longer applies.
Changing profiles clears inherited mode flags unsupported by the new profile
and selects its default palette unless a palette override is supplied. Changing
profile or screen mode also resets an inherited screen-colour count when needed.
An inherited Atari band height is cleared outside playfield conversion.
Display effects are retained when changing profiles for experimentation.
`--display-effect none` disables an inherited effect and clears its strength;
an explicitly supplied strength still requires an active effect.
Explicitly invalid combinations and incompatible custom dimensions produce an
error before image conversion begins.

Built-in examples:

| Identifier | Settings |
| --- | --- |
| `builtin:cpc-macaws-bayer2` | CPC mode 1 constrained, Bayer 2x2, saturation 1.1, blue gain 1.5, scale 2 |
| `builtin:c64-landscape-green` | C64 multicolour, Floyd–Steinberg, hue +20, green gain 1.15, scale 2 |
| `builtin:teletext-mosaic-bayer4` | Teletext mosaic, Bayer 4x4, neutral colour adjustments, scale 6 |

## Storage and format

Linux uses `$XDG_CONFIG_HOME/retroimg/presets`, falling back to
`~/.config/retroimg/presets`. Windows uses `%APPDATA%\retroimg\presets`, falling
back to the user's `AppData\Roaming` directory. Use `--presets-dir` with `guided`,
`convert` or `presets` for another directory. No directory is created until a
preset is saved. Files directly inside it with a `.json` extension appear in
the guide and listing. Invalid files are reported and skipped; loading one
explicitly reports its error.

A hand-written version-1 preset can contain a subset of conversion settings:

```json
{
  "version": 1,
  "name": "CPC blue boost",
  "description": "A starting point for the bundled macaws image",
  "settings": {
    "profile": "cpc-mode1",
    "cpc_mode": "constrained",
    "palette": "cpc",
    "fit": "cover",
    "dither": "bayer",
    "bayer_size": 2,
    "brightness": 1.1,
    "contrast": 1.2,
    "saturation": 1.1,
    "blue_gain": 1.5,
    "scale": 2
  }
}
```

Setting names follow CLI option names with underscores in place of hyphens.
Omitted settings use ordinary CLI defaults. Loading/saving resolves implicit
target defaults, including palette, Bayer size, Amiga screen-colour count and
Atari row height. Files saved by the guide include neutral source adjustments
and applicable mode flags so they reproduce the chosen settings.

Integer controls require JSON integers; colour adjustments accept finite JSON
numbers. Boolean values, unknown fields, duplicate keys, unsupported versions,
non-finite numbers, and image-path settings are rejected. Description is optional.
Brightness and contrast must be non-negative; both default to `1.0` when omitted,
so existing version-1 presets retain their previous output. Explicit CLI values
of `1.0` reset either saved adjustment to neutral.
The format stores data only; it cannot execute commands or reference other presets.
