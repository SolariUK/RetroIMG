# Display effects

Display effects are optional treatments of the enlarged RGB preview. They run
after conversion and aspect correction. Indexed pixels, hardware constraints,
palette entries and the `IndexedImage` returned by `convert_file` stay unchanged.
The resulting PNG can contain additional colours from the display simulation.
Without an effect, existing output is unchanged.

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
keeps plain output and also overrides an effect inherited from a preset.
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

For scanlines, [CRT EasyMode](https://github.com/libretro/glsl-shaders/blob/master/crt/shaders/crt-easymode.glsl)
is a useful reference for periodic beam profiles and brightness handling. Our
small implementation uses an original, analytically averaged cosine profile
and sRGB transfer functions; it does not port that shader's brightness-dependent
beam, interpolation or masks. More elaborate shader adaptations should retain
their upstream licence and attribution. Phosphor masks and bloom remain future work.
