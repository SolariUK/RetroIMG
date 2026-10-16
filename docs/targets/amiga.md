# Amiga OCS/ECS

The `amiga` palette describes the complete **4,096-colour RGB space**: four bits
per channel, with ideal preview levels `0, 17, 34, …, 255`. Hardware colour words
are `0xRGB`; for example, `0xF80` becomes RGB `(255, 136, 0)`. Individual screens
select a small palette from this colour space. Channel precision and display
limits follow the [Amiga graphics documentation](https://wiki.amigaos.net/wiki/Classic_Graphics_Primitives).

| Profile | Standard | Logical raster | Relative pixel aspect | Constrained colour counts | Scale for matching previews |
| --- | --- | --- | --- | --- | --- |
| `amiga-lores` | PAL | 320x256 | 1:1 | 2, 4, 8, 16, 32 | 2 → 640x512 |
| `amiga-hires` | PAL | 640x256 | 1:2 | 2, 4, 8, 16 | 1 → 640x512 |
| `amiga-lores-ntsc` | NTSC | 320x200 | 1:1 | 2, 4, 8, 16, 32 | 2 → 640x400 |
| `amiga-hires-ntsc` | NTSC | 640x200 | 1:2 | 2, 4, 8, 16 | 1 → 640x400 |

As with the other targets, `--amiga-mode bitmap` is the default. It uses the
whole selected palette without a screen-colour limit. With the built-in Amiga
palette, every output channel has four-bit precision but an image can use more
than 32 colours. This is an aesthetic option, not an encodable standard screen.
Bitmap mode accepts palette swaps, including C64 and CPC colours.

Use `--amiga-mode constrained` to fit a screen palette. `--colours` chooses the
maximum count; it defaults to 32 for lores and 16 for hires. Counts must be powers
of two from the table; a solid image may use fewer colours. Currently `--colours`
is supported only by Amiga constrained conversion and is rejected in bitmap
mode or with another target. Constrained Amiga conversion requires the built-in
`amiga` palette. Custom width/height are allowed as visual experiments without
cell alignment requirements.

```bash
# Default: unrestricted 4096-colour conversion in PAL low-resolution geometry
retroimg convert /path/to/image.jpg amiga-free.png \
    --profile amiga-lores --scale 2

# Select up to 32 legal screen colours and dither within that palette
retroimg convert /path/to/image.jpg amiga-32.png \
    --profile amiga-lores --amiga-mode constrained --colours 32 \
    --dither floyd-steinberg --scale 2

# A four-colour low-resolution treatment, without dithering
retroimg convert /path/to/image.jpg amiga-4.png \
    --profile amiga-lores --amiga-mode constrained --colours 4 --scale 2

# PAL high resolution supports up to 16 screen colours
retroimg convert /path/to/image.jpg amiga-hires.png \
    --profile amiga-hires --amiga-mode constrained --colours 16 \
    --dither floyd-steinberg --scale 1

# NTSC geometry with the existing hue and channel-gain controls
retroimg convert /path/to/image.jpg amiga-ntsc.png \
    --profile amiga-lores-ntsc --amiga-mode constrained \
    --hue-shift 20 --green-gain 1.15 --dither floyd-steinberg --scale 2

# Mix Amiga geometry with an unrestricted CPC palette
retroimg convert /path/to/image.jpg amiga-cpc.png \
    --profile amiga-lores --palette cpc --scale 2
```

### Adaptive screen palettes

The reusable `fit_rgb_palette` fitter uses frequency-weighted RGB samples,
weighted median-cut seeds, then up to 12 iterations of colour-cluster refinement.
Cluster centres snap to the permitted channel levels. It fits the prepared RGB
source, rather than an already quantised image. The result is deterministic for
the same prepared input and settings; it is a heuristic, not a guaranteed global
minimum. Sampling follows the shared 4096-sample histogram policy described in
the CPC section. The Python fitter accepts `max_samples=None` for full-histogram
fitting. There is no exhaustive search over all possible screen palettes.

Palette selection precedes dithering. The full prepared source is quantised
using only those selected colours, with Floyd–Steinberg diffusion across the
whole image. Saturation, hue and gains apply before selection and can change the
screen palette. No-dither and dithered runs with otherwise identical settings
select the same register colours.

Unrestricted regular RGB-grid quantisation uses exact per-channel nearest-level
lookup rather than searching all 4096 entries per pixel. Ties select the lower
index, matching exhaustive weighted RGB distance. High-resolution previews keep
every logical column and stretch rows for relative aspect. As with CPC and BBC,
this aspect convention preserves relative mode geometry without simulating a
particular monitor.

### EHB and HAM6

Both special modes use `amiga-lores` (PAL) or `amiga-lores-ntsc`. They require the
built-in `amiga` colour space and reject `--colours`, since their register-table
sizes and code meanings are fixed. Standard constrained conversion and
unrestricted bitmap conversion remain available.

| Option | Base registers | Pixel interpretation |
| --- | --- | --- |
| `--amiga-mode ehb` | 32 RGB12 colours | Six-bit code selects a base colour or its linked half-bright counterpart; up to 64 distinct colours |
| `--amiga-mode ham` | 16 RGB12 colours | Six-bit code selects a base colour or changes one RGB channel of the previous displayed pixel; can reach the 4096-colour space |

```bash
# EHB: 32 chosen colours plus their hardware-linked half-bright copies
retroimg convert /path/to/image.jpg amiga-ehb.png \
    --profile amiga-lores --amiga-mode ehb --scale 2

# EHB with error diffusion
retroimg convert /path/to/image.jpg amiga-ehb-dither.png \
    --profile amiga-lores --amiga-mode ehb \
    --dither floyd-steinberg --scale 2

# HAM6: preserve legal hold-and-modify codes, then decode a PNG preview
retroimg convert /path/to/image.jpg amiga-ham.png \
    --profile amiga-lores --amiga-mode ham --scale 2

# NTSC HAM6, with dithering and source-colour adjustments
retroimg convert /path/to/image.jpg amiga-ham-ntsc.png \
    --profile amiga-lores-ntsc --amiga-mode ham \
    --dither floyd-steinberg --hue-shift 20 --green-gain 1.15 --scale 2
```

EHB halves each **four-bit component**, discarding its low bit. Full white
`0xFFF` therefore becomes `0x777`, RGB `(119, 119, 119)` in the preview, rather
than halving already expanded eight-bit RGB values. The fitter seeds 32 base
colours using the standard adaptive fitter, then performs up to eight linked
refinement iterations. Each register is fitted jointly against pixels assigned
to its full and half-bright colours, evaluating all 16 component levels. Updates
must strictly reduce error on the shared fitting histogram. This remains a
bounded heuristic rather than an exhaustive global palette search.

HAM6 uses an adaptive 16-colour base palette. Code bits 5–4 select palette/blue/
red/green; the low nibble supplies the register index or new channel level.
The held colour resets to register 0 at the start of **each scanline**. Other
than base-colour selection, a pixel changes only one channel, so adjacent pixels
are dependent. Colour fringes can remain at sharp transitions.

The HAM encoder chooses the lowest-error **current** pixel among the 16 base
entries and the best red, green and blue modifications. Those 19 candidates give
the same immediate minimum as testing all 64 codes. This is a deterministic
greedy encoder, not a whole-row or whole-image optimum. It deliberately avoids
a large state search to keep conversion practical in Python. No independent
4096-way colour choice is claimed for each pixel.

All source-colour controls remain available. Floyd–Steinberg diffusion uses the
actual displayed RGB colour after each HAM code is applied; it does not diffuse
errors against code numbers. Diffusion continues across the image, while HAM's
held-colour state resets at each row. EHB and HAM choose the same base register
tables with and without dithering when other inputs and settings match.

`AmigaEHBImage` retains 32 registers and six-bit pixel codes; `AmigaHAMImage`
retains 16 registers and six-bit pixel codes. Unused register slots are padded
with black, and duplicate register colours are legal. Independent rasterisers
decode these representations into previews. These data models preserve what a
future native exporter needs, but **PNG output is not an Amiga screen file**.
Bitplane packing and IFF/ILBM metadata still need a dedicated exporter.

The implementation covers non-interlaced, single-playfield indexed, EHB and
HAM6 images with PNG previews. AGA/HAM8, Copper palette changes, sprites,
interlace, overscan, native export and CRT effects remain deferred.

[All targets](README.md) · [Project README](../../README.md)
