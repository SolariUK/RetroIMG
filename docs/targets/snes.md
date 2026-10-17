# Super Nintendo / SNES

The `snes` palette describes the 32,768-colour space, with five bits per RGB
channel. Preview levels are rounded from `i * 255 / 31`. The initial `snes`
profile is 256×224, rendered with a nominal 4:3 picture aspect: at scale 2 the
PNG is 597×448. Custom dimensions are supported; constrained backgrounds
require multiples of eight. Palette and background organisation follow
[Nintendo's development manual, Book I](https://floating.muncher.se/bot/manual/book1_text.pdf),
particularly the Background and CG-RAM sections.

| Option | Behaviour |
| --- | --- |
| `--snes-mode bitmap` | Default: unrestricted colour space, with palette swaps available |
| `--snes-mode tiles` | Single 4bpp background layer: eight shared 16-entry banks, one bank per 8×8 tile |
| `--snes-mode indexed` | Single 8bpp background layer, as BG1 in Mode 3, using up to 256 selected colours |

Tiles mode models the colour rules used by a 4bpp background in modes such as
Mode 1. It does not reproduce an entire multi-layer Mode 1 screen. Each bank
has fifteen independently selected colours plus a shared backdrop, for up to
121 distinct RGBs in the opaque PNG. Code zero shows that backdrop. Indexed
mode also resolves code zero to its backdrop colour; a single opaque layer
can therefore use all 256 selected RGBs. Neither mode adds input-alpha handling.
Constrained modes require the built-in `snes` palette.

```bash
retroimg convert /path/to/image.jpg snes-tiles.png \
    --profile snes --snes-mode tiles --dither floyd-steinberg --scale 2

retroimg convert /path/to/image.jpg snes-256.png \
    --profile snes --snes-mode indexed --dither bayer --bayer-size 4 --scale 2
```

Tiles use the same deterministic bank fitter as [Mega Drive](megadrive.md),
with eight banks and the SNES RGB grid. Indexed palette fitting uses up to
2048 frequency-weighted samples and six refinement iterations. Colour
controls apply before fitting; all dithering methods are available, along
with guided choices and presets. Tile diffusion resets at tile boundaries;
indexed diffusion spans the full image. Bayer preserves logical coordinates.

`optimise_snes_tiles` returns a validated `SNESTileImage`, retaining CGRAM
banks plus local pixel codes and tile bank selectors. `optimise_snes_indexed`
returns `SNESIndexedImage` with selected CGRAM values and pixel indices.
Hardware words are `0bbbbbgggggrrrrr`, e.g. red is `0x001f`. Separate rasterisers
produce the displayed indexed image. These models do not pack native tile data.

Mode 7 transforms, direct colour, high resolution, colour math, sprites,
multiple layers, interlace, memory budgeting and native exports remain deferred.
The [comparison sheets](../../samples/comparisons/README.md)
show the three conversion modes with each dither.
