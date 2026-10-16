# Module boundaries

The converter keeps palettes, display geometry, colour constraints, logical
representations and preview rendering independently usable. Machine-specific
implementations are grouped under `targets`; reusable fitting algorithms are
grouped under `constraints`.

```text
retroimg/
    targets/
        teletext.py          # Cells/pages, mosaic optimisation, rasterisation
        spectrum.py          # Ink/paper/BRIGHT cells and attribute optimisation
        c64.py               # Multicolour cells and shared-background optimisation
        cpc.py               # Global screen inks and pen-indexed images
        bbc.py               # Steady physical colours and logical pixel mappings
        amiga/
            __init__.py      # Public Amiga API (existing import paths retained)
            indexed.py       # Standard adaptive RGB12 register palettes
            ehb.py           # Linked full/half-bright palette fitting and codes
            ham.py           # Stateful greedy HAM6 encoding and decoding
            common.py        # Fixed register-table and code-grid validation
    constraints/
        cells.py             # Generic two-colour cell fitting, optional legal pairs
        shared_background.py # Generic local sets with an image-wide shared colour
        global_palette.py    # Generic whole-image selection from a fixed palette
        adaptive_palette.py  # Grid-snapped adaptive palette clustering
        histogram.py         # Shared deterministic frequency-weighted RGB sampling
        __init__.py          # Package description
    palettes/                # Named RGB colour definitions
    profiles/                # Geometry, default palette, constraint-model identifiers
    model.py                 # Shared Palette, Geometry, TargetProfile, IndexedImage
    colour_spaces.py         # Generic Cartesian RGB grids and exact nearest lookup
    quantize.py              # Palette quantisation and Floyd–Steinberg diffusion
    geometry.py              # Fitting and resizing
    adjustments.py           # Source saturation, hue rotation and RGB gains
    render.py                # Generic indexed preview rendering, scaling and aspect
    conversion_modes.py      # Mode metadata, validation and adapter registry
    convert.py               # Shared file conversion pipeline
    cli.py                   # Command-line argument handling
```

Machine modules live only under `targets`, and fitting implementations live
only under `constraints`. The package root contains the shared conversion,
image preparation, rendering, registry and CLI modules.

## Dependencies and conversion flow

Shared models, quantisation, fitting algorithms and generic preview rendering
do not import machine implementations at runtime. A target may use these shared
building blocks, but it owns its hardware rules and logical representation.

`convert_file` performs the same sequence for each profile:

1. Resolve a palette and geometry, including optional custom dimensions.
2. Ask the mode registry to validate target options and choose an adapter.
3. Resize the source and apply saturation, hue shift and RGB gains.
4. Call the adapter to obtain an `IndexedImage`.
5. Render and save the preview with the profile's preview aspect policy.

Unrestricted bitmap mode calls the generic quantiser directly. Constrained
adapters optimise a target-specific representation and then rasterise it.
`rasterize_*` functions expand logical data into palette indices; they do not
scale images, save files or add display effects. `render_indexed` handles the
generic display step and has no knowledge of ink limits or cell patterns.

For example, Spectrum supplies shared-brightness candidate pairs to the generic
cell fitter; C64 uses the shared-background fitter; CPC and BBC use whole-image
palette selection. The hardware rules do not live inside those reusable algorithms.

Simpler targets remain single modules. Amiga is a subpackage because indexed,
EHB and HAM have distinct representations and fitting rules. Its public API
remains `retroimg.targets.amiga`, so existing Python callers keep their imports. There is no plugin framework or mandatory
base class: the registry's adapter contract is an RGB image, palette and dither
setting returning an `IndexedImage`.

## Canonical Python imports

```python
from retroimg.targets.teletext import optimise_teletext_mosaic, rasterize_teletext
from retroimg.targets.spectrum import optimise_spectrum_attributes, rasterize_spectrum
from retroimg.targets.c64 import optimise_c64_multicolour, rasterize_c64_multicolour
from retroimg.targets.cpc import optimise_cpc, rasterize_cpc
from retroimg.targets.bbc import optimise_bbc, rasterize_bbc
from retroimg.targets.amiga import optimise_amiga, rasterize_amiga
from retroimg.targets.amiga import optimise_ehb, rasterize_ehb, optimise_ham, rasterize_ham

from retroimg.constraints.cells import quantize_cells
from retroimg.constraints.shared_background import fit_shared_background
from retroimg.constraints.global_palette import select_palette_indices
from retroimg.constraints.adaptive_palette import fit_rgb_palette
from retroimg.colour_spaces import RGBGrid
from retroimg.render import render_indexed
```

Use these module paths for Python callers. Machine models, optimisers and
rasterisers belong to their target module; preview rendering belongs to
`retroimg.render`. Each implementation has a single module location. CLI flags,
defaults and output behaviour are preserved; unrestricted palette/profile
combinations remain available.

## Adding a target

1. Add its palette and geometry profiles without changing existing profiles.
2. Add a `targets/<name>.py` module with any required logical representation,
   validation, optimiser and rasteriser.
3. Reuse a generic fitter when its constraints match. Add a new generic
   algorithm only if it can be expressed without machine-specific rules.
4. Register the constrained adapter and mode metadata in `conversion_modes.py`.
   Expose any needed mode option through the CLI and `convert_file` API, while
   retaining unrestricted bitmap conversion.
5. Test legal/illegal representations, known patterns, colour limits,
   deterministic output and CLI integration. Extend the visual gallery matrix
   with neutral baselines and clearly labelled adjustments.

BBC bitmap modes use `BBCImage`, with a mode number, a tuple of steady physical
colour numbers (`colours`) and a logical-colour-indexed pixel grid.
`colours[logical]` maps a logical slot to physical colour 0..7; `rasterize_bbc`
expands the mapping without scaling. `optimise_bbc` reuses the same global
palette selector as CPC. The target owns its mode limits: 2/4/8/2/4 steady
colours for modes 0/1/2/4/5. Mode 2's flashing slots are deliberately excluded
from this static representation. There are no BBC-specific branches in the
shared fitting algorithms, file pipeline or renderer.

Amiga uses `fit_rgb_palette` to choose colours from an `RGBGrid`; weighted
median-cut seeds and snapped cluster means avoid enumerating combinations of
4096 candidates. The fitter contains no Amiga rules. `AmigaImage` validates
lores/hires bitplane capacity, 12-bit register values and register-indexed pixels.
Its rasteriser returns the selected palette and logical pixels. PAL/NTSC geometry
lives in profiles, independently of the screen representation. `--colours` is
passed through the registry's configurable-palette adapter map; the target
validates allowed counts. No target rules are added to `convert_file`.

A complete Cartesian `Palette` may declare `rgb_levels`. Validation requires
sorted unique 8-bit levels and the full red-major RGB product in precisely that
order. The shared quantiser then uses exact per-channel lookup, including lower
index tie-breaking, for both plain quantisation and error diffusion. Selected
screen palettes do not carry this metadata and use ordinary weighted-distance
lookup. The existing fixed-palette selector retains its original fitting
behaviour, with its histogram implementation moved to the shared module.

`AmigaEHBImage` retains 32 physical registers and six-bit codes. The EHB fitter
reuses adaptive RGB-grid palette seeds and frequency-weighted sampling, then
refines base registers jointly against full- and half-bright assignments. The
Amiga-specific four-bit truncation rule stays in the target. The 64-entry
raster palette preserves the exact register/half-bright slot relationship.

`AmigaHAMImage` retains 16 physical registers and six-bit HAM6 codes. Encoding is
greedy in scan order; it compares base entries and the nearest legal change for
each channel. Decoding is a separate function that begins each scanline from
register 0. The raw raster uses the complete RGB12 space, not the 64 HAM codes
as if they were colour indices. A model validator checks register/code ranges
before rasterisation. These representations support a future native exporter
without claiming that the existing PNG previews are native Amiga files.

The generic quantiser accepts an optional `pixel_lookup(x, y, rgb)` callback
returning a palette index. HAM supplies a stateful lookup that returns the
actual displayed RGB12 index and retains its selected code separately. Shared
Floyd–Steinberg diffusion therefore uses decoded colours, while the target owns
all scanline state. Existing callers keep the same default lookup and output.
No machine-specific logic is added to the shared diffusion algorithm.

AGA/HAM8 and interlaced/overscan modes remain deferred. More expensive HAM
whole-row searches can be explored later, without replacing the bounded greedy
mode or compromising its valid hardware representation.

Hardware exporters and future optional CRT post-processing remain separate
concerns; neither is implemented by these target adapters.

## Refactor verification

The fast regression suite includes a fresh-interpreter check that shared
modules do not load target implementations, along with mode registry checks.
For visual verification, regenerate the gallery into a new directory using
the same sources and compare source checksums, settings and output PNG hashes
in the two `manifest.json` files. Matching PNG hashes establish byte-for-byte
equality, including all palette, geometry, dithering and adjustment examples.
