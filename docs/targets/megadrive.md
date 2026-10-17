# Sega Mega Drive / Genesis

The `megadrive` colour space contains 512 normal colours: three bits per RGB
channel. Previews use idealised evenly spaced levels, rounded from `i * 255 / 7`.
These are digital approximations, not a simulation of an analogue TV or the
VDP's nonlinear DAC response. Shadow/highlight and raster palette changes are deferred.
Hardware organisation follows the [Sega software manual](https://nemesis.hacking-cult.org/MegaDrive/Documentation/GenesisSoftwareManual.pdf).

| Profile | Logical raster |
| --- | --- |
| `megadrive-320` | 320×224 |
| `megadrive-256` | 256×224 |
| `megadrive-320-pal` | 320×240 |
| `megadrive-256-pal` | 256×240 |

Profiles use a nominal 4:3 picture aspect, rather than modelling individual TV
timings. At scale 2, the 320-wide profiles render 640×480, the 256×224 profile
597×448, and the 256×240 profile 640×480. Rendering only enlarges axes, so no
logical pixels are discarded. Custom dimensions remain available.

`--megadrive-mode bitmap` is the default unrestricted mode: use the complete
colour space, or swap palettes freely. It does not enforce tile constraints.

`--megadrive-mode tiles` fits a single background plane. Four shared palette
banks each hold sixteen entries. Every 8×8 tile selects exactly one bank.
Local code zero resolves to the same backdrop throughout the image, leaving
fifteen independently selected colours per bank: at most 61 distinct RGBs
across the opaque output. The backdrop is chosen automatically from the most
frequent grid-snapped prepared source colour. No input-alpha feature is added.
Tiles mode requires the built-in `megadrive` palette and dimensions divisible
by eight; `--colours` remains an Amiga-specific option.

```bash
retroimg convert /path/to/image.jpg megadrive.png \
    --profile megadrive-320 --megadrive-mode tiles --scale 2

retroimg convert /path/to/image.jpg megadrive-bayer.png \
    --profile megadrive-320 --megadrive-mode tiles \
    --dither bayer --bayer-size 4 --saturation 1.1 --scale 2

retroimg guided /path/to/image.jpg megadrive.png
```

Brightness, contrast, saturation, hue and channel gains apply before fitting.
All dithering choices are available. Floyd–Steinberg resets within each tile;
Bayer retains the logical matrix origin. Neither dithering method changes the
selected banks. Presets retain all settings and explicit CLI values override them.

The shared bank fitter seeds palettes from tiles with the largest residual
colour error, alternates tile assignment and adaptive palette fitting for up
to four rounds, and retains the lowest-error result. Each bank fit uses up to
512 frequency-weighted source samples and six refinement iterations. This is
a deterministic heuristic; tile boundaries or palette compromises can remain.

Python callers can use `optimise_megadrive` to retain a `MegaDriveImage` with
four CRAM register banks, local pixel codes and tile bank selectors. Register
words use `0x0BGR` with even channel nibbles, e.g. red is `0x00e`.
`rasterize_megadrive` separately expands it for PNG rendering. This milestone
does not pack VRAM, budget tile memory, compose sprites/layers or export a ROM.
The [comparison panel](../../samples/comparisons/macaws-megadrive.png) shows
bitmap and tile-constrained output with each dither.
