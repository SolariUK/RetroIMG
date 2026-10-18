# Display effects

Display effects are optional treatments of the enlarged RGB preview. They run
after conversion and aspect correction. Indexed pixels, hardware constraints,
palette entries and the `IndexedImage` returned by `convert_file` stay unchanged.
The resulting PNG can contain additional colours from the display simulation
or display brightness adjustment. Defaults preserve existing output exactly.

## Source brightness and display brightness

The pipeline order is:

**Resize and source adjustments → palette conversion and dithering → preview
enlargement/aspect correction → display treatment → highlight bloom → display
brightness → save PNG.**

Effects combine in this fixed order. `--display-effect` selects a surface treatment
(LCD, scanlines or CRT grille); the independent bloom controls add glow after it.
Bloom can also run by itself with `--display-effect none`. Display brightness is
always last. Each stage has its own controls; argument order does not change the
rendering order. Defaults leave all effects off and brightness neutral.

| Option | Position in the pipeline | Result |
| --- | --- | --- |
| `--brightness` | Source adjustment, before palette conversion | Can change fitted colours, pixel indices and dithering |
| `--display-brightness` | Final RGB adjustment, after display effects | Changes the finished preview without refitting colours or dithering |

Display brightness defaults to `1.0` (neutral). Values above 1 brighten the
display, values between 0 and 1 dim it, and 0 produces black. It is a finite,
non-negative **linear-light multiplier**: 2 doubles the light level, rather than
doubling the encoded RGB values. Channels exceeding the display range are clipped.
Black remains black. It works with every profile, including when no display
effect is selected, and does not change output dimensions.

For example, brighten a strong CRT treatment without changing its conversion:

```bash
retroimg convert photo.jpg crt-brighter.png --profile megadrive-320 --megadrive-mode tiles \
    --dither bayer --bayer-size 4 --scale 4 --display-effect crt-aperture \
    --effect-strength 0.85 --display-brightness 2
```

The guide asks for **Display brightness (after effects)** separately from the
source colour controls, and labels both stages in its summary. Both settings
can be saved in ordinary presets. `--display-brightness 1` resets an inherited
display gain while retaining source adjustments. Disabling an effect leaves
display brightness independent: also reset it to 1 for an unmodified preview.
Python callers can pass `display_brightness=2` to `convert_file` or `render_indexed`.

## Game Boy LCD

```bash
retroimg convert photo.jpg gameboy-lcd.png --profile gameboy --gameboy-mode tiles \
    --dither bayer --bayer-size 4 --scale 8 \
    --display-effect gameboy-lcd --effect-strength 0.35
```

`gameboy-lcd` draws inset rectangular pixel cells, gaps revealing an LCD
substrate, and a small lower-right cell shadow. The substrate takes its tint
from the lightest palette entry by luminance, including entries unused in the
image. Green Game Boy output stays green; `--palette gameboy-grey` stays neutral.
It is a static aesthetic approximation, without motion ghosting, reflections,
screen bezels or measured LCD colour calibration. Monochrome cells have no RGB
subpixel mask.

`--effect-strength` ranges from `0` (plain pixels) to `1` (full treatment),
defaulting to `0.35`. It requires an enabled effect. `gameboy-lcd` requires
`--scale 3` or greater; 6 or 8 is recommended to resolve the cell borders.
Smaller scales are rejected rather than silently enlarged. The effect preserves
the requested output dimensions and aspect ratio. Borders are calculated from
the logical grid, with area coverage at fractional aspect-corrected cell sizes.
Viewing the exported PNG at 100% avoids additional browser scaling of the grid.

The effect is recommended for Game Boy, but is available with **every profile**.
It neither selects the Game Boy profile nor switches palettes. For example:

```bash
retroimg convert photo.jpg cga-lcd.png --profile cga-320 --cga-mode constrained \
    --palette cga-pal1-high --scale 6 --display-effect gameboy-lcd
```

No profile enables display effects automatically. `--display-effect none`
disables the effect, including one inherited from a preset.
Changing a preset's platform retains its explicitly chosen display effect,
allowing experimentation; the minimum scale still applies.

The guide offers **Display effect**, strength and preview scale for every
machine. Effects can be saved in ordinary version-1 presets. Python callers can
pass `display_effect='gameboy-lcd'` and `effect_strength=0.35` to either
`convert_file` or `render_indexed`.

## Scanlines

```bash
retroimg convert photo.jpg scanlines.png --profile megadrive-320 --megadrive-mode tiles \
    --dither bayer --bayer-size 4 --scale 4 --display-effect scanlines
```

`scanlines` draws one smooth horizontal brightness profile per logical image
row. Row centres are brightest and boundaries are dimmer. The profile is
averaged over each output pixel, so the spacing follows logical rows through
aspect correction and fractional enlargement, rather than alternating fixed
output rows. It keeps the converted image's detail, dimensions and palette
indices; only the rendered RGB brightness changes.

Strength defaults to the subtle `0.35`, with `--effect-strength 0` preserving
plain output and `1` giving the strongest modulation. Scanlines require
`--scale 3` or greater. Dimming is computed in linear light and converted back
to sRGB; black stays black and highlights are never boosted or clipped. The
overall image gets slightly darker as strength increases. There is no automatic
brightness compensation, blur, phosphor mask, bloom or curvature.

Like LCD cells, scanlines are an explicit choice available with every profile,
including through the guide and presets. This first version selects one display
effect at a time. A 224-row Mega Drive image receives 224 beams; this is a
static treatment of logical rows, without interlace or video-timing simulation.

[Plain, subtle and stronger scanline examples](../samples/scanlines/README.md)
use the same macaws conversion at 320×224, displayed at 1280×960 after scale 4
and aspect correction. Full-size PNGs and unscaled crops are provided; inspect
them at 100% to avoid browser scaling of the pattern. Regenerate with:

```bash
python examples/generate_display_effects.py --effect scanlines --replace
```

## CRT aperture grille

```bash
retroimg convert photo.jpg crt.png --profile megadrive-320 --megadrive-mode tiles \
    --dither bayer --bayer-size 4 --scale 4 \
    --display-effect crt-aperture --effect-strength 0.35
```

`crt-aperture` combines the existing row-aligned scanlines with vertical RGB
phosphor stripes. Each three-column output repeat contains a red, green and
blue stripe, starting at the image's left edge. Each stripe preserves its named
channel's scanline brightness and dims the other two channels. The mask stays
at one output pixel per stripe, independent of logical pixels and aspect ratio;
scanline spacing still follows the logical image rows. The pattern is applied
after enlargement and never changes the native conversion resolution.

The existing `--effect-strength` control adjusts both scanline and mask strength
together. It defaults to subtle `0.35`; `0` gives plain output and `1` gives the
strongest treatment. The mask retains `1-strength` of the other channels' light.
Both weights are applied in linear light before a single conversion back to
sRGB, avoiding intermediate rounding. Black stays black, colour channels absent
in the source stay absent, and highlights are never boosted. Stronger settings
darken the image further; there is no automatic brightness compensation.

The effect is available with every profile through CLI, guided mode and
presets, and requires scale 3 or greater. It remains an aesthetic flat-screen
approximation, without curvature, reflections or a measured tube model.
Bloom is a separate optional stage rather than part of the grille strength.
`--display-effect scanlines` remains available for scanlines without a mask.

[CRT examples and unscaled crops](../samples/crt-aperture/README.md) show the
same Mega Drive macaws conversion plain, with scanlines alone, with subtle CRT,
with stronger CRT, and with stronger CRT plus display brightness 2.0.
Output remains 1280×960 from the 320×224 logical image.
Inspect the original PNGs at 100%; fitting a fine phosphor mask to a browser
window can create colour shifts or moiré. Crops retain the full image's mask phase.

```bash
python examples/generate_display_effects.py --effect crt-aperture --replace
```

## Highlight bloom and combined effects

```bash
# Bloom alone; the default display treatment is none.
retroimg convert photo.jpg bloom.png --profile megadrive-320 --megadrive-mode tiles \
    --scale 4 --bloom-strength 0.25

# CRT grille + scanlines, then bloom, then display brightness.
retroimg convert photo.jpg crt-bloom.png --profile megadrive-320 --megadrive-mode tiles \
    --dither bayer --bayer-size 4 --scale 4 --display-effect crt-aperture \
    --effect-strength 0.35 --bloom-strength 0.25 --bloom-radius 1 \
    --display-brightness 1
```

| Control | Default | Meaning |
| --- | --- | --- |
| `--bloom-strength` | `0` (off) | Added highlight glow, from 0 to 1; try subtle `0.25` |
| `--bloom-radius` | `1` | Gaussian spread (sigma), from 0.25 to 8 logical pixel widths |

Bloom extracts highlights whose brightest channel exceeds half the linear-light
range, preserving their RGB proportions. It blurs that highlight layer and adds
it to the sharp preview in linear light, clipping channels at the display range.
Dark areas can receive glow from nearby highlights; an entirely dark image has
no bloom. It never dims the image or blurs the original pixels. Strong settings
can soften contrast near highlights and clip bright colours.

Radius follows the enlarged logical pixel width: radius 1 at scale 4 is a
four-output-pixel Gaussian sigma for square or narrow source pixels. The halo is
circular in output space even when aspect correction makes logical cells taller.
If aspect correction widens logical pixels, the radius grows with their width.
Output dimensions and indexed conversion data do not change. Bloom alone has no
minimum enlargement requirement; combined treatments retain their existing
minimum scale. Its 8-bit linear RGB blur buffer is a small CPU approximation,
not an HDR or measured CRT optical model. It adds no dependencies beyond Pillow.

The guide offers bloom independently after selecting a display treatment, and
both controls are saved in version-1 presets. Older presets keep bloom off.
`--bloom-strength 0` disables inherited bloom while retaining the surface effect;
`--display-effect none` disables the surface effect while retaining bloom.
For plain output, disable both and reset display brightness to 1. A saved radius
is retained when bloom is disabled, allowing it to be re-enabled later.
Python callers pass `bloom_strength` and `bloom_radius` to `convert_file` or
`render_indexed` with the same defaults and units.

[Full-size bloom examples and unscaled crops](../samples/bloom/README.md) compare
plain, bloom alone, CRT alone, CRT with subtle bloom, and CRT with stronger bloom.
All use the same Mega Drive night-scene conversion and neutral display brightness.
Bright window lights against dark brickwork make the surrounding glow easier to
judge than the macaws image. The detail crop isolates a lit window; strength and
radius are unchanged from the initial examples in the regular comparisons.
An additional wider-glow example explicitly increases radius to 3 at strength
0.85 to demonstrate the spread control.

```bash
python examples/generate_display_effects.py --effect bloom --replace
```

## LCD examples and implementation references

[Full-size examples and unscaled crops](../samples/display-effects/README.md)
show the macaws conversion plain, at strength `0.35`, and at strength `0.85`.
The conversion uses native Game Boy resolution, 160×144. Output is deliberately
enlarged 8× to 1280×1152: each native pixel occupies an 8×8 output area, giving
the LCD borders and shadows room to resolve without increasing image detail.
These are separate from the conversion comparison sheets. Regenerate them with:

```bash
python examples/generate_display_effects.py --replace
```

The implementation uses Python/Pillow on the CPU and needs no GPU runtime or
additional dependencies. Libretro's [Game Boy shader](https://github.com/libretro/slang-shaders/blob/master/handheld/shaders/gameboy/shader-files/gb-pass0.slang)
is a useful reference for dot geometry, coverage and the distinction between
static appearance and temporal response. This first treatment uses original
code for a small rectangular-cell model; it does not include or port that
shader.

For scanlines and aperture grilles, [CRT EasyMode](https://github.com/libretro/glsl-shaders/blob/master/crt/shaders/crt-easymode.glsl)
is a useful reference for periodic beams, RGB stripe masks and brightness handling. Our
small implementation uses an original, analytically averaged cosine profile
and a basic repeating RGB attenuation mask with sRGB transfer functions. It does
not port that shader's code, brightness-dependent beam or interpolation.
More elaborate shader adaptations should retain their upstream licence and
attribution. Bloom uses an original highlight extraction and Pillow Gaussian
blur, without adapting upstream shader code. Other mask patterns remain future work.

## Planned additions

After bloom, planned additions are chromatic aberration and RF-style colour
bleed and smearing, inspired by the appearance of NES output on an RF-connected
television. These are visual treatments rather than a promise of an accurate
signal-level RF simulation. Each belongs in the display pipeline, leaving the
underlying palette conversion and indexed image unchanged. These will extend the
ordered presentation chain; their exact positions and controls will be decided
during implementation.
