# Logical representations and future work

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
algorithms live in `retroimg.constraints`. The [architecture notes](architecture.md)
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

`optimise_megadrive` and `optimise_snes_tiles` retain a generic validated
`BankedImage` as their `.tiles` member, plus hardware CRAM/CGRAM `.registers`.
The tile model contains RGB palette banks, `.tile_palettes` (one bank selector
per 8x8 tile), and `.pixels` (local 0..15 codes). Every bank's slot zero is the
shared backdrop. Mega Drive uses four banks and SNES 4bpp backgrounds eight.
Register tables must decode exactly to the tile palettes. Separate rasterisers
expand them into a flat indexed image, retaining duplicate backdrop slots so
bank/local identities remain recoverable. SNES 8bpp uses `SNESIndexedImage`
with a selected CGRAM table and ordinary palette indices. These representations
do not claim packed native tile memory or complete multi-layer console screens.

`NESImage` retains four background palettes of PPU colour codes and an
`.attributes` banked model with 16x16 selectors and two-bit local pixel codes.
`MasterSystemImage` retains two CRAM palettes and `.tiles` with 8x8 selectors
and four-bit local codes. These banks have no shared-backdrop requirement:
all sixteen entries in each bank are available to background tiles.
`GameBoyImage` retains two-bit pixel codes, a BGP byte and a selected green or
grey display palette. Rasterisation applies the BGP mapping to codes before
looking up display shades. No sprite, window, memory packing or native export
is implied by these models.

`CGAImage` stores the chosen fixed palette, resolution family, Colour Select
byte and local pixel codes. `EGAImage` stores the scanline family, up to sixteen
six-bit palette-register values and local indices. Separate rasterisers
interpret these values for preview rendering. EGA's register-bit order is
independent of the full RGB grid's internal palette order.

[Display effects](display-effects.md) run after logical rasterisation and preview
scaling. Optional Game Boy LCD cells and shadows, row-aligned scanlines, or a CRT
aperture grille with scanlines modify
the RGB preview without changing cells, palettes or the raw indexed raster.
Independent chromatic aberration runs before the surface treatment; highlight
bloom runs after it and before final display brightness. Future RF-style smearing and bezels
belong to the same separate presentation layer.
