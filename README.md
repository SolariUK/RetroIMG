# retroimg

`retroimg` converts modern images into constrained retro-display styles.  The
project deliberately separates target geometry, palette, quantisation and
machine-specific constraints so that Teletext, Commodore 64, ZX Spectrum and
other targets can share the same conversion pipeline.

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
Teletext bitmap/mosaic, Spectrum bitmap/attributes, C64 bitmap/multicolour, and
all three CPC modes. It includes unrestricted palette experiments, dithering,
and labelled colour-adjustment examples.

```bash
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-gallery \
    --public-only
```

Use a new output directory and the project's Python environment. Source
filenames and credits are described in [examples/README.md](examples/README.md).
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
from retroimg.constraints import optimise_teletext_mosaic
from retroimg.palettes import get_palette
from retroimg.render import rasterize_teletext, render_indexed

source = Image.new("RGB", (80, 75), "red")  # Already resized logical source
page = optimise_teletext_mosaic(source, get_palette("teletext"))
cell = page.cells[0][0]
print(cell.foreground, cell.background, cell.pattern)
render_indexed(rasterize_teletext(page), scale=6).save("preview.png")
```

Palette definitions, profile geometry, colour coexistence constraints, logical
representations and renderers remain separate. The generic cell optimiser has
no Teletext transmission rules. It accepts an optional set of allowed palette
index pairs: Teletext uses all pairs, while Spectrum supplies only pairs that
share a brightness bank. The conversion-mode registry connects profile
constraint models to raster adapters, keeping target rules out of the shared
file preparation/rendering pipeline.

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

Future strict Teletext support should introduce a separate page encoding layer
and CLI mode. It will need to account for row state, control-code cell positions,
foreground/background changes, contiguous/separated graphics and held graphics.
Visual mosaic pages do not guarantee broadcast encodability. A future versioned
cell-data export can preserve this model without pretending to be a transmitted
page; no export schema is committed yet.

Future CRT effects belong after logical rasterisation, in an optional preview
post-processing pipeline. Scanlines, bloom, phosphor scaling and bezels must not
modify cells or the raw raster. No such effects are currently implemented.
