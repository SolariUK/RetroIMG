# retroimg

`retroimg` converts modern images into constrained retro-display styles.  The
project deliberately separates target geometry, palette, quantisation and
machine-specific constraints so that Teletext, Commodore 64, ZX Spectrum,
Amstrad CPC, BBC Micro, Amiga, Atari 2600 and future targets can share the same pipeline.

## Development install

From the directory containing `pyproject.toml`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

Then list the built-in targets:

```bash
retroimg profiles
retroimg palettes
```

## Teletext

The Teletext profile has two modes.

### Bitmap mode (default)

This intentionally preserves the colourful 80x75 low-resolution style from the
first version.  It uses the Teletext palette but does not impose mosaic-cell
restrictions.

```bash
retroimg convert photo.jpg output.png \
    --profile teletext \
    --teletext-mode bitmap \
    --dither floyd-steinberg \
    --scale 6
```

Because bitmap is the default, `--teletext-mode bitmap` may be omitted.

### Mosaic mode

This uses the same logical 80x75 raster, grouped into the authentic 40x25 grid
of 2x3 graphics cells.  Each cell is optimised to use at most two palette
colours, producing a visibly more Teletext-like result while retaining the
existing image conversion workflow. Colour pairs are fitted directly to the resized
RGB source, before palette quantisation, using an exhaustive minimum-error
search. Floyd–Steinberg dithering then uses the chosen pair within each cell;
error diffusion resets at cell boundaries. Without dithering, each cell is the
minimum weighted RGB error fit. Ties follow palette order for reproducibility.

```bash
retroimg convert photo.jpg output-mosaic.png \
    --profile teletext \
    --teletext-mode mosaic \
    --dither floyd-steinberg \
    --scale 6
```

This is currently a *visual* mosaic constraint.  Historical Teletext row
control codes, held/separated graphics and background-control behaviour are a
future layer rather than being baked into the image converter.

## ZX Spectrum

`--profile spectrum` uses a 256x192 logical raster and the Spectrum palette.
The default `--spectrum-mode bitmap` preserves unrestricted palette conversion.
The new `attributes` mode fits ink and paper colours to each 8x8 pixel block,
with a single normal/bright setting shared by both colours. Black is available
at either brightness. The standard screen contains 32x24 attribute cells.
These rules follow the [original Spectrum manual, Chapter 16](https://worldofspectrum.org/ZXBasicManual/zxmanchap16.html).

```bash
# Unrestricted Spectrum palette conversion (the existing default)
retroimg convert /path/to/image.jpg output-spectrum-bitmap.png \
    --profile spectrum --spectrum-mode bitmap --scale 2

# Apply 8x8 ink/paper and shared-brightness constraints
retroimg convert /path/to/image.jpg output-spectrum-attributes.png \
    --profile spectrum --spectrum-mode attributes --scale 2

# Dither within each selected ink/paper pair
retroimg convert /path/to/image.jpg output-spectrum-attributes-dither.png \
    --profile spectrum --spectrum-mode attributes \
    --dither floyd-steinberg --scale 2

# Combine attribute conversion with source colour adjustments
retroimg convert /path/to/image.jpg output-spectrum-adjusted.png \
    --profile spectrum --spectrum-mode attributes \
    --hue-shift 20 --green-gain 1.15 --scale 2
```

These previews are 512x384. Attribute mode searches every legal unordered
colour pair, including solid-colour pairs, directly against the prepared RGB
source. Without dithering it minimises weighted RGB error for each cell.
Normal-brightness candidates come first to break equal-error ties. With
Floyd–Steinberg, it selects the same pair first, then dithers using that pair
with diffusion reset at each cell boundary. Visible colour clash at block
edges is a consequence of the hardware constraints.

Attribute mode requires the built-in Spectrum palette; incompatible palette
overrides are rejected. Bitmap mode continues to allow any palette. Custom
attribute dimensions must both be divisible by 8, for example
`--width 128 --height 96`. Such grids are visual experiments rather than
standard Spectrum screens. `--spectrum-mode attributes` is only valid with
`--profile spectrum`; `--teletext-mode mosaic` remains Teletext-only.

This version renders static PNG previews with no FLASH animation, border,
hardware screen-file export or CRT effects. Palette RGB values remain the
existing display approximation.

## Commodore 64 multicolour

The new `c64-multicolour` profile selects a 160x200 logical raster with 2:1
wide pixels. Geometry and colour restrictions are independent: the default
`--c64-mode bitmap` uses unrestricted palette conversion, while
`--c64-mode multicolour` enables the hardware colour constraints. The existing
`c64-hires` profile and its unrestricted output remain unchanged.

```bash
# Wide-pixel C64 style with unrestricted colours (the default)
retroimg convert /path/to/image.jpg output-c64-bitmap.png \
    --profile c64-multicolour --c64-mode bitmap --scale 2

# Same geometry with multicolour bitmap constraints
retroimg convert /path/to/image.jpg output-c64-multicolour.png \
    --profile c64-multicolour --c64-mode multicolour --scale 2

# Diffuse errors within each cell's selected colours
retroimg convert /path/to/image.jpg output-c64-multicolour-dither.png \
    --profile c64-multicolour --c64-mode multicolour \
    --dither floyd-steinberg --scale 2

# Mix a different palette with unrestricted wide-pixel geometry
retroimg convert /path/to/image.jpg output-c64-teletext-palette.png \
    --profile c64-multicolour --c64-mode bitmap --palette teletext --scale 2

# Source-colour controls also work with C64 constraints
retroimg convert /path/to/image.jpg output-c64-adjusted.png \
    --profile c64-multicolour --c64-mode multicolour \
    --hue-shift 20 --green-gain 1.15 --scale 2
```

At scale 2 these outputs are 640x400: each logical pixel occupies 4x2 preview
pixels. Fitting the source accounts for the same wide-pixel geometry, so it
does not squash the image. This is a simple 2:1 pixel model rather than a
simulation of PAL/NTSC display differences. Only the new profile opts into
aspect-correct previews; older profiles keep their existing preview dimensions.

Constrained multicolour mode divides the raster into 40x25 cells of 4x8 logical
pixels. Each cell can select one image-wide background colour plus three
local colours, all from the C64 palette. A cell does not have to use its
background slot. This follows the [C64 Programmer's Reference Guide](https://www.devili.iki.fi/Computers/Commodore/C64/Programmers_Reference/Chapter_3/page_128.html).

The optimiser searches all background colours and local colour sets against
the prepared RGB source, minimising summed weighted RGB error over the whole
image. Equal total errors choose the lowest background palette index. Search
shortcuts stop when an unrestricted per-pixel minimum is already achievable;
they do not approximate the objective. No-dither output achieves that minimum.
With Floyd–Steinberg, the same background and cell sets are chosen first,
then diffusion is confined to each 4x8 cell. Background selection is automatic
and may vary with cropping, colour adjustments or input images.

`--c64-mode multicolour` requires `--profile c64-multicolour` and the built-in
C64 palette. Unrestricted bitmap mode allows any palette and does not impose
cell alignment. Custom constrained dimensions require width divisible by 4
and height by 8, for example `--width 80 --height 104`. Custom grids are visual
experiments rather than standard C64 screens. No hardware file export,
raster-interrupt effects or CRT effects are implemented.

## Amstrad CPC modes 0, 1 and 2

The `cpc` palette contains all 27 firmware colours in colour-number order.
It uses idealised RGB channel levels **0, 128 and 255**, corresponding to the
CPC's three levels per channel. These are digital approximations rather than
measurements of a particular analogue monitor. Colour numbering and RGB mixing
are documented in the [CPC Gate Array reference](https://cpctech.cpcwiki.de/docs/garray.html);
mode dimensions and ink limits appear in the [CPC464 manual](https://www.manualslib.com/manual/862146/Amstrad-Cpc464.html?page=107).

| Profile | Logical raster | Relative pixel aspect | Constrained ink limit | Scale for a 640x400 preview |
| --- | --- | --- | --- | --- |
| `cpc-mode0` | 160x200 | 2:1 | 16 from 27 | 2 |
| `cpc-mode1` | 320x200 | 1:1 | 4 from 27 | 2 |
| `cpc-mode2` | 640x200 | 1:2 | 2 from 27 | 1 |

Geometry is independent of colour constraints. Each profile defaults to
`--cpc-mode bitmap`, allowing unrestricted use of all palette colours and
palette swaps. Add `--cpc-mode constrained` to enforce the image-wide ink limit.
Unlike Teletext, Spectrum and C64 multicolour, CPC has no per-cell colour limit
in these modes. Mode 2 can use any selected pair of CPC colours, not just black
and white. Border colours, flashing inks and raster palette changes are excluded.

```bash
# Unrestricted CPC palette conversion in mode 0 geometry (the default)
retroimg convert /path/to/image.jpg output-cpc0-free.png \
    --profile cpc-mode0 --cpc-mode bitmap --scale 2

# Limit the whole image to 16 CPC inks
retroimg convert /path/to/image.jpg output-cpc0.png \
    --profile cpc-mode0 --cpc-mode constrained --scale 2

# Mode 1: choose four inks and dither using that global palette
retroimg convert /path/to/image.jpg output-cpc1.png \
    --profile cpc-mode1 --cpc-mode constrained \
    --dither floyd-steinberg --scale 2

# Mode 2: choose two inks, preserving every narrow logical pixel
retroimg convert /path/to/image.jpg output-cpc2.png \
    --profile cpc-mode2 --cpc-mode constrained \
    --dither floyd-steinberg --scale 1

# Hue and colour balance apply before selecting screen inks
retroimg convert /path/to/image.jpg output-cpc0-adjusted.png \
    --profile cpc-mode0 --cpc-mode constrained \
    --hue-shift 20 --green-gain 1.15 --scale 2

# Mix mode 1 geometry with the C64 palette, without CPC ink restrictions
retroimg convert /path/to/image.jpg output-cpc1-c64.png \
    --profile cpc-mode1 --cpc-mode bitmap --palette c64 --scale 2
```

Constrained mode requires the built-in `cpc` palette. Custom width and height
are supported without cell-alignment restrictions; they are visual experiments
rather than standard CPC screens. Existing profiles and defaults are unchanged.
All CPC previews account for relative pixel aspect during fitting and rendering.
Mode 2 stretches preview pixels vertically instead of discarding logical columns
at scale 1. The aspect model preserves relative mode geometry; it does not
simulate a particular monitor.

### Screen palette selection

Screen inks are selected against weighted RGB error from the prepared source.
One/two-colour selection searches every candidate; four/sixteen-colour selection
uses greedy additions followed by up to eight improving one-colour swaps.
The larger searches are deterministic heuristics, not guaranteed global optima.

Selection uses the complete RGB histogram when it contains at most 4096 unique
colours. Larger histograms use a deterministic, frequency-weighted sample of up
to 4096 RGB colours, so rare colours may be omitted during fitting. The Python
helper `select_palette_indices(..., max_samples=None)` can fit the complete
histogram. Palette selection always precedes dithering; **every output pixel is
quantised from the full prepared source**. Floyd–Steinberg diffusion runs across
the whole image using only the chosen screen inks. Hue, saturation and RGB gain
adjustments can therefore change which inks are selected.

### CPC firmware palette RGB values

These numbers identify firmware colours, not pen slots or Gate Array hardware
register values. The historical colour name `white` is the middle RGB level;
`bright-white` is full white.

| Firmware colour | Name | RGB |
| --- | --- | --- |
| 0 | black | 0, 0, 0 |
| 1 | blue | 0, 0, 128 |
| 2 | bright-blue | 0, 0, 255 |
| 3 | red | 128, 0, 0 |
| 4 | magenta | 128, 0, 128 |
| 5 | mauve | 128, 0, 255 |
| 6 | bright-red | 255, 0, 0 |
| 7 | purple | 255, 0, 128 |
| 8 | bright-magenta | 255, 0, 255 |
| 9 | green | 0, 128, 0 |
| 10 | cyan | 0, 128, 128 |
| 11 | sky-blue | 0, 128, 255 |
| 12 | yellow | 128, 128, 0 |
| 13 | white | 128, 128, 128 |
| 14 | pastel-blue | 128, 128, 255 |
| 15 | orange | 255, 128, 0 |
| 16 | pink | 255, 128, 128 |
| 17 | pastel-magenta | 255, 128, 255 |
| 18 | bright-green | 0, 255, 0 |
| 19 | sea-green | 0, 255, 128 |
| 20 | bright-cyan | 0, 255, 255 |
| 21 | lime | 128, 255, 0 |
| 22 | pastel-green | 128, 255, 128 |
| 23 | pastel-cyan | 128, 255, 255 |
| 24 | bright-yellow | 255, 255, 0 |
| 25 | pastel-yellow | 255, 255, 128 |
| 26 | bright-white | 255, 255, 255 |

## BBC Micro modes 0, 1, 2, 4 and 5

The `bbc` palette provides eight steady physical colours in BBC colour-number
order: black, red, green, yellow, blue, magenta, cyan and white. Each RGB channel
is idealised to 0 or 255. Mode dimensions, colour numbering and logical-colour
remapping follow the [BBC Microcomputer User Guide](https://www.bbcmicrobot.com/docs/BBC_User_Guide.pdf)
(printed pages 164–165, 224 and 301).

| Profile | Logical raster | Relative pixel aspect | Constrained steady colours | Scale for a 640x512 preview |
| --- | --- | --- | --- | --- |
| `bbc-mode0` | 640x256 | 1:2 | 2 from 8 | 1 |
| `bbc-mode1` | 320x256 | 1:1 | 4 from 8 | 2 |
| `bbc-mode2` | 160x256 | 2:1 | All 8 | 2 |
| `bbc-mode4` | 320x256 | 1:1 | 2 from 8 | 2 |
| `bbc-mode5` | 160x256 | 2:1 | 4 from 8 | 2 |

Every profile defaults to `--bbc-mode bitmap`: unrestricted palette use, with
palette swaps allowed. Add `--bbc-mode constrained` to select a screen-wide
palette within the mode's limit. Two-colour modes may choose any pair, not just
black and white; four-colour modes may choose any four steady colours. There
are no per-cell colour restrictions. Selection reuses the generic whole-image
selector described above: exhaustive pair fitting, deterministic greedy/swap
fitting for four colours, with up to 4096 weighted RGB samples. Dithering uses
the full prepared image and only the selected colours.

Mode 2 has **16 logical hardware slots**, but its default upper eight are
flashing colour pairs, not eight extra steady RGB colours. This static converter
uses its eight steady physical colours. Consequently Mode 2 bitmap and
constrained output match when using the built-in BBC palette and identical
settings. Unrestricted palette swaps can still produce different aesthetics.
Modes 3 and 6 are text modes and are omitted. BBC Mode 7 control-code emulation
is separate future work; the existing visual Teletext profile remains available.

```bash
# Mode 0: choose two colours and retain fine horizontal detail
retroimg convert /path/to/image.jpg output-bbc0.png \
    --profile bbc-mode0 --bbc-mode constrained \
    --dither floyd-steinberg --scale 1

# Mode 1: four automatically selected screen colours
retroimg convert /path/to/image.jpg output-bbc1.png \
    --profile bbc-mode1 --bbc-mode constrained --scale 2

# Mode 2: wide pixels and all eight steady colours
retroimg convert /path/to/image.jpg output-bbc2.png \
    --profile bbc-mode2 --bbc-mode constrained \
    --dither floyd-steinberg --scale 2

# Mode 4: two colours at 320x256
retroimg convert /path/to/image.jpg output-bbc4.png \
    --profile bbc-mode4 --bbc-mode constrained --scale 2

# Mode 5: four colours, with hue and green gain adjustments
retroimg convert /path/to/image.jpg output-bbc5-adjusted.png \
    --profile bbc-mode5 --bbc-mode constrained \
    --hue-shift 20 --green-gain 1.15 --scale 2

# Keep BBC geometry while using all 27 CPC colours
retroimg convert /path/to/image.jpg output-bbc1-cpc.png \
    --profile bbc-mode1 --bbc-mode bitmap --palette cpc --scale 2
```

Constrained conversion requires the built-in `bbc` palette. Custom dimensions
remain available without cell alignment requirements, as visual experiments.
Previews account for relative pixel aspect when fitting and scaling; Mode 0
stretches rows rather than discarding logical columns. This gives consistent
relative geometry between modes, not a simulation of a particular PAL monitor.
Flashing colours, raster palette changes, hardware screen-file export and CRT
effects are not implemented.

## Amiga OCS/ECS

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

## Atari 2600

`atari2600-ntsc` uses a nominal 160x192 active picture and `atari2600-pal`
uses 160x228. Both preview at 4:3; at scale 2 this gives 512x384 and 608x456
PNGs respectively. These active picture sizes follow Atari's
[Stella Programmer's Guide](https://www.atariage.com/2600/programming/2600_101/docs/stella.html).
The console has programmable vertical timing; these are useful presets, not
its only possible picture heights.

The two named palettes preserve 128 even TIA colour-register slots in register
order: palette index `i` corresponds to register value `i * 2`. NTSC has 128
distinct RGB values; PAL has 104 because hue banks 0, 1, 14 and 15 share the
same eight grays. Our palettes are **idealised approximations**, generated
independently with nominal hue phases, a luminance ramp and a YIQ-to-RGB
transform. PAL uses its own interleaved hue order. They are not measured console
output or copied emulator palette tables. Analogue colours depend on the TIA,
console adjustment and television; hue, saturation and gain controls remain
useful. The [Stella emulator documentation](https://stella-emu.github.io/docs/index.html)
also describes separate NTSC/PAL palettes and adjustable colour reproduction.
There are no TV/CRT effects in these previews.

`--atari-mode bitmap` is the default unrestricted palette conversion at the
profile's full logical resolution. It also allows other named palettes and
custom dimensions, as with existing profiles.

The playfield modes require a logical width of 160 and either Atari palette.
They divide each row into 40 blocks, each four colour clocks wide:

| Mode | Pattern constraint |
| --- | --- |
| `playfield` | 40 independent blocks across the image |
| `repeat` | 20 blocks repeated in the right half |
| `mirror` | 20 blocks reflected into the right half |

Each band has one foreground/background colour pair. `--atari-row-height`
selects how many scanlines share the pattern and pair (default 2); use 1 for
finer detail or 4/8 for chunkier output. A final partial band is supported.
Custom heights are allowed; custom playfield widths are rejected.

The fitter evaluates every distinct palette pair against the prepared RGB
source. Samples sharing a pattern bit are fitted together, including both
halves in repeated/mirrored modes. Without dithering this minimises the same
weighted RGB squared error used elsewhere in retroimg. Ties follow palette
order. Floyd–Steinberg uses the selected pair and diffuses horizontally along
the independent pattern bits, resetting at each band. Group means are rounded
to 8-bit RGB for the dithering step; no dithering occurs inside a shared block.

```bash
# Unrestricted full-resolution Atari palette conversion
retroimg convert /path/to/image.jpg atari-bitmap.png \
    --profile atari2600-ntsc --dither floyd-steinberg --scale 2

# Independent playfield blocks, with the landscape adjustments
retroimg convert /path/to/image.jpg atari-playfield.png \
    --profile atari2600-ntsc --atari-mode playfield \
    --hue-shift 20 --green-gain 1.15 --dither floyd-steinberg --scale 2

# PAL mirrored playfield with chunkier vertical blocks
retroimg convert /path/to/image.jpg atari-mirror.png \
    --profile atari2600-pal --atari-mode mirror --atari-row-height 8 --scale 2

# Repeated halves; use --atari-mode mirror to compare symmetry
retroimg convert /path/to/image.jpg atari-repeat.png \
    --profile atari2600-ntsc --atari-mode repeat --scale 2

# Keep unrestricted palette/profile mixing
retroimg convert /path/to/image.jpg atari-c64-palette.png \
    --profile atari2600-ntsc --palette c64 --scale 2
```

These are visual playfield constraints. Independent halves correspond to
mid-line playfield updates; this converter does not model CPU scheduling,
sprites, score mode or timed colour changes within a line. Output is PNG;
Atari native export and executable ROM generation are outside the current scope.

## Palette/profile independence

Palettes can be mixed with geometries for experimentation:

```bash
retroimg convert photo.jpg hybrid.png --profile teletext --palette c64
```

Custom dimensions are also available:

```bash
retroimg convert photo.jpg custom.png --profile teletext --width 160 --height 150
```

For `--teletext-mode mosaic`, width must be divisible by 2 and height by 3.

## Compare modes with the same source

After activating the virtual environment, run these commands from the project
directory. Replace `/path/to/image.jpg` with your source image path. Outputs
are saved in the current directory; change their paths as needed.

```bash
# Bitmap, with and without dithering
retroimg convert /path/to/image.jpg output-bitmap.png \
    --teletext-mode bitmap --dither none --scale 6
retroimg convert /path/to/image.jpg output-bitmap-dither.png \
    --teletext-mode bitmap --dither floyd-steinberg --scale 6

# Mosaic, with and without dithering
retroimg convert /path/to/image.jpg output-mosaic.png \
    --teletext-mode mosaic --dither none --scale 6
retroimg convert /path/to/image.jpg output-mosaic-dither.png \
    --teletext-mode mosaic --dither floyd-steinberg --scale 6

# Alternate palettes, retaining Teletext's 2x3 cell constraints
retroimg convert /path/to/image.jpg output-mosaic-c64.png \
    --teletext-mode mosaic --palette c64 --scale 6
retroimg convert /path/to/image.jpg output-mosaic-spectrum.png \
    --teletext-mode mosaic --palette spectrum --scale 6

# Larger logical grid, with the same preview dimensions
retroimg convert /path/to/image.jpg output-mosaic-large.png \
    --teletext-mode mosaic --width 160 --height 150 --scale 3

# More saturated source colours before optimisation
retroimg convert /path/to/image.jpg output-mosaic-saturated.png \
    --teletext-mode mosaic --saturation 1.5 --scale 6
```

All eight outputs are 480x450 previews. `--scale` enlarges logical pixels using
nearest-neighbour scaling; it does not add image detail. The larger mosaic uses
an 80x50 cell grid rather than the default 40x25. Palette swaps do not enable C64
or Spectrum hardware constraints.

The default `--fit cover` crops to fill the logical raster. Use `--fit contain`
to keep the whole source with padding, or `--fit stretch` to fill without
preserving its aspect ratio. Dithering defaults to `none` in these examples
unless explicitly enabled.

## Dithering

`--dither` accepts `none` (the default), `floyd-steinberg` and `bayer`.
Floyd–Steinberg spreads quantisation error to neighbouring pixels. Bayer uses a
repeating threshold matrix for a regular patterned texture, with no error
diffusion. Both work with the existing source colour adjustments.

Choose a **2x2, 4x4 or 8x8** matrix with `--bayer-size`; the default is 4x4.
Larger matrices provide finer coverage increments over a larger repeating tile.
They do not change the image resolution or preview scale. The option is rejected
unless `--dither bayer` is selected.

```bash
# Bayer with the default 4x4 matrix
retroimg convert /path/to/image.jpg cpc-bayer.png \
    --profile cpc-mode0 --cpc-mode constrained --dither bayer --scale 2

# Compare a larger matrix with the existing landscape adjustments
retroimg convert /path/to/image.jpg c64-bayer8.png \
    --profile c64-multicolour --c64-mode multicolour \
    --dither bayer --bayer-size 8 --hue-shift 20 --green-gain 1.15 --scale 2

# Smaller pattern, retaining Teletext cell constraints
retroimg convert /path/to/image.jpg teletext-bayer2.png \
    --profile teletext --teletext-mode mosaic --dither bayer --bayer-size 2 --scale 6

# HAM6 uses legal, state-dependent colour choices
retroimg convert /path/to/image.jpg amiga-ham-bayer.png \
    --profile amiga-lores --amiga-mode ham --dither bayer --scale 2
```

For an arbitrary palette, ordered conversion finds the nearest colour, then
chooses its best mixing partner by projecting the source RGB onto the segments
joining it to other available colours. The matrix chooses between that pair
according to the mixing proportion. This uses retroimg's weighted RGB error;
it is a nearest-anchor heuristic, not an exhaustive search of every colour pair.
Equally accurate mixtures prefer closer colours. Complete regular RGB grids,
such as unrestricted Amiga RGB12, instead use ordered rounding between adjacent
levels independently for each channel.

Target palette fitting stays the same: Bayer assigns pixels using the selected
cell/screen colours. A cell fitted to a single colour remains solid. Teletext,
Spectrum and C64 retain global logical matrix coordinates across cell boundaries.
Atari applies the matrix to its independent block bits and band number, then
expands shared scanlines and repeated/mirrored halves. HAM evaluates the 64 legal
codes at each pixel using the held colour, then makes its ordered choice; it
remains greedy and may show colour fringes. All outputs retain their mode's
colour and pattern constraints. Existing `none` and Floyd–Steinberg conversion
remain unchanged.

## Source colour adjustments

Optional adjustments apply after resizing and before palette/cell optimisation
for every profile. Processing order is saturation, hue shift, then RGB gains.
Neutral defaults preserve existing conversion output.

```bash
# Boost green by 15%
retroimg convert /path/to/image.jpg output-green.png \
    --teletext-mode mosaic --green-gain 1.15 --scale 6

# Rotate hue and adjust channel balance
retroimg convert /path/to/image.jpg output-balanced.png \
    --teletext-mode mosaic --hue-shift 10 \
    --red-gain 0.9 --green-gain 1.15 --blue-gain 1.0 --scale 6
```

`--hue-shift` rotates HSV hue in degrees (default `0`); positive 120 degrees
maps red to green, and negative values rotate the other way. Rotation wraps at
360 degrees. Greys remain neutral under hue rotation.

`--red-gain`, `--green-gain` and `--blue-gain` multiply the respective RGB
channels (default `1.0`). Values below 1 reduce a channel, values above 1 boost
it, and zero removes it. Results clip to 0–255. Gains must be finite and
non-negative; hue must be finite. These adjustments affect the whole image,
including sky, skin and neutral colours. A green boost can still leave grass
mapped to yellow when red remains high; a small red reduction may help, but
also changes other areas. All outputs still use the selected palette.

## Reproducible visual examples

The [example gallery runner](examples/README.md) compares the same sources across
Teletext bitmap/mosaic, Spectrum bitmap/attributes, C64 bitmap/multicolour,
all three CPC modes, BBC Micro modes 0/1/2/4/5, and Amiga lores/hires
colour counts plus EHB/HAM6, and Atari 2600 NTSC/PAL bitmap/playfield modes. It includes unrestricted palette experiments,
dithering, and labelled colour-adjustment examples.

```bash
python examples/generate_gallery.py \
    --output-dir /path/to/new-gallery \
    --public-only
```

For a focused dithering comparison (none, Floyd–Steinberg, Bayer 2/4/8):

```bash
python examples/generate_gallery.py --public-only --dither-comparison \
    --output-dir /path/to/new-dither-gallery

# Limit the run to one source and target family
python examples/generate_gallery.py --public-only --dither-comparison \
    --family cpc --source lush-landscape --output-dir /path/to/new-cpc-dither-gallery
```

Use a new output directory and the project's Python environment. Public
reference images are included in [samples/sources](samples/README.md), which is
the default source directory. Override it with `--sources-dir /path/to/source-images`
for local experiments. Source credits and rights are recorded in
[samples/README.md](samples/README.md); generation options are described in
[examples/README.md](examples/README.md).
The public-only run uses the documented public-domain/CC0 photographs and a
locally generated diagnostic chart. Local-only user-supplied images are excluded.

The runner writes an offline HTML gallery, Markdown index, individual PNGs,
labelled comparison sheets, reproduction commands and a settings/checksum
manifest. It checks colour constraints and preview properties as it runs. This
is a visual integration run; the fast unit/regression tests remain separate:

```bash
python -m pytest -q
```

## Internal representation and development direction

Bitmap conversion continues to return an `IndexedImage` directly. Mosaic
conversion now follows this sequence:

1. Resize and prepare RGB source pixels.
2. Fit cell colours using the generic `quantize_cells` constraint function.
3. Produce a `TeletextPage` through `optimise_teletext_mosaic`.
4. Expand cells with `rasterize_teletext`, then render the PNG preview.

`TeletextPage` holds a palette and a rectangular grid of `TeletextCell` values.
The default page is 40 columns by 25 rows; custom logical dimensions produce
correspondingly sized cell grids. Each cell stores foreground/background palette
indices and a six-bit pattern. Bits 0–5 run left to right, top to bottom across
the 2x3 subpixels; set bits select foreground. These logical bits are **not**
Teletext character bytes. When creating a page from an indexed raster, the lower
used colour index becomes background; solid cells use identical colours and
pattern zero. Pages reject invalid grids, indices and patterns.

Python callers can retain cell data independently of PNG rendering:

```python
from PIL import Image
from retroimg.targets.teletext import optimise_teletext_mosaic, rasterize_teletext
from retroimg.palettes import get_palette
from retroimg.render import render_indexed

source = Image.new("RGB", (80, 75), "red")  # Already resized logical source
page = optimise_teletext_mosaic(source, get_palette("teletext"))
cell = page.cells[0][0]
print(cell.foreground, cell.background, cell.pattern)
render_indexed(rasterize_teletext(page), scale=6).save("preview.png")
```

Machine-specific code lives in `retroimg.targets`, and reusable fitting
algorithms live in `retroimg.constraints`. The [architecture notes](docs/architecture.md)
describe the module boundaries and how to add another target. Import machine
models, optimisers and rasterisers from `retroimg.targets.<machine>`, generic
fitters from the appropriate `retroimg.constraints` module, and preview
rendering from `retroimg.render`.

Palette definitions, profile geometry, colour coexistence constraints, logical
representations and renderers remain separate. The generic cell optimiser has
no Teletext transmission rules. It accepts an optional set of allowed palette
index pairs: Teletext uses all pairs, while Spectrum supplies only pairs that
share a brightness bank. The conversion-mode registry validates mode options
and connects profile constraint models to target-owned raster adapters, keeping
target rules out of the shared file preparation/rendering pipeline.

`optimise_spectrum_attributes` returns a `SpectrumImage` containing validated
`SpectrumCell` values: hardware ink/paper codes (0–7), a shared boolean `bright`
and a 64-bit logical pattern. Bits run left to right, top to bottom, with bit 0
at the top left; set bits select ink. `rasterize_spectrum` expands this model
to an `IndexedImage`. These patterns do not use Spectrum video-memory byte
order.

`fit_shared_background` is a separate generic optimiser for colour sets that
share an image-wide palette index. C64 uses it with a four-colour limit and
4x8 cells. `optimise_c64_multicolour` produces a `C64MulticolourImage` containing
one background index and a grid of `C64MulticolourCell` values. Each cell holds
three local palette indices and a 64-bit logical pattern with two bits per
pixel: selector 0 uses the shared background and selectors 1–3 use the local
colours. The lowest two bits are the top-left pixel, followed by row-major
pixels. `rasterize_c64_multicolour` expands the selectors into an `IndexedImage`
without display scaling. This representation is not a hardware screen-file
layout. C64 high-resolution hardware constraints remain future work.

`select_palette_indices` provides reusable whole-image palette selection for
targets with global colour limits. `optimise_cpc` uses it to produce a validated
`CPCImage` with a mode number, a tuple of firmware colour numbers (`inks`) and a
pen-indexed pixel grid. `inks[pen]` maps a pixel's pen slot to a firmware colour;
`rasterize_cpc` expands those slots into the full CPC palette's indexed raster.
The representation is independent of CPC video-memory byte layout. Hardware
screen-file export remains deferred.

`optimise_bbc` reuses the same global selector to produce a `BBCImage` holding
its mode, selected steady physical `colours`, and logical-colour-indexed pixels.
`colours[logical]` maps each pixel's logical slot to a physical colour number;
`rasterize_bbc` expands that mapping into the full BBC palette. Optimisation,
logical mapping and preview rendering remain separate.

`optimise_amiga` produces an `AmigaImage` with a resolution family, bitplane
count, a tuple of 12-bit colour-register values and register-indexed pixels.
`rasterize_amiga` returns an indexed image with that selected screen palette;
it does not expand it into a 4096-entry palette. The model is independent of
Amiga bitplane byte layout and native export. Special EHB and HAM representations
retain their actual six-bit code grids; their separate rasterisers apply linked
brightness or scanline colour state. Full regular-grid palettes declare
validated `rgb_levels` metadata, which allows the generic quantiser to use an
exact per-channel lookup without target-specific branches.

Future strict Teletext support should introduce a separate page encoding layer
and CLI mode. It will need to account for row state, control-code cell positions,
foreground/background changes, contiguous/separated graphics and held graphics.
Visual mosaic pages do not guarantee broadcast encodability. A future versioned
cell-data export can preserve this model without pretending to be a transmitted
page; no export schema is committed yet.

Future CRT effects belong after logical rasterisation, in an optional preview
post-processing pipeline. Scanlines, bloom, phosphor scaling and bezels must not
modify cells or the raw raster. No such effects are currently implemented.
