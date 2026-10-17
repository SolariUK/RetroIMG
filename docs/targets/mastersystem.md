# Sega Master System

The `mastersystem` palette contains the 64 Mode 4 RGB colours: two bits per
channel, expanded to idealised levels 0/85/170/255. Actual analogue output can
differ; this does not simulate the first VDP's nonlinear blue response.
[Palette registers](https://www.smspower.org/Development/Palette) use `%00BBGGRR`.

| Profile | Logical raster | Scale-2 preview |
| --- | --- | --- |
| `mastersystem` | 256×192 | 512×384 |
| `mastersystem-224` | 256×224 | 597×448 |
| `mastersystem-240` | 256×240 | 640×480 |

The [extended-height modes](https://www.smspower.org/Development/Modes) are for
compatible later VDPs. Previews use a nominal
4:3 picture aspect, with no discarded logical columns or rows.

`--mastersystem-mode bitmap` is the default unrestricted RGB6 conversion,
with palette swaps available. `--mastersystem-mode tiles` fits two shared
16-entry palettes and assigns one to each 8×8 background tile. Background
tiles can select either bank, including the bank used by sprites; all sixteen
entries are usable, including code zero. The image can therefore contain up
to 32 distinct RGBs. See the [Mode 4 tile description](https://www.smspower.org/Development/Tiles).
This differs from Mega Drive's shared-backdrop constraint.

```bash
retroimg convert photo.jpg sms.png --profile mastersystem \
    --mastersystem-mode tiles --dither floyd-steinberg --scale 2
retroimg convert photo.jpg sms-bayer.png --profile mastersystem \
    --mastersystem-mode tiles --dither bayer --bayer-size 4 --scale 2
```

Tiles mode requires the built-in palette and dimensions divisible by eight.
It reuses the generic RGB-grid bank fitter with two independent banks and no
reserved backdrop slots. Fitting is deterministic and heuristic, preceding
dithering; diffusion resets per tile and Bayer retains logical coordinates.
Brightness, contrast, saturation, hue and RGB gains, guided mode and presets
are available.

`MasterSystemImage` retains two CRAM register banks and a `BankedImage` of local
pixel codes and tile-bank selectors. Separate rasterisation produces an opaque
PNG. Sprites, legacy TMS9918 modes, scrolling, raster changes, native tile packing,
memory limits and executable export remain deferred.

[View the Master System comparisons](../../samples/comparisons/README.md).
