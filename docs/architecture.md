# Module boundaries

The converter keeps palettes, display geometry, colour constraints, logical
representations and preview rendering independently usable. Machine-specific
implementations are grouped under `targets`; reusable fitting algorithms are
grouped under `constraints`.

```text
retroimg/
    targets/
        megadrive.py         # Four-bank single-plane tiles and CRAM words
        snes.py              # Eight-bank 4bpp tiles, 8bpp BG and CGRAM words
        nes.py               # Four palettes and 16x16 background attributes
        mastersystem.py      # Two independent RGB6 background tile palettes
        gameboy.py           # DMG luminance codes and BGP mapping
        cga.py               # Fixed graphics palettes and Colour Select register
        ega.py               # RGBI/RGB6 screen palettes and EGA register bits
        teletext.py          # Cells/pages, mosaic optimisation, rasterisation
        spectrum.py          # Ink/paper/BRIGHT cells and attribute optimisation
        c64.py               # Multicolour cells and shared-background optimisation
        cpc.py               # Global screen inks and pen-indexed images
        atari2600.py          # Per-band TIA colour codes and playfield patterns
        bbc.py               # Steady physical colours and logical pixel mappings
        amiga/
            __init__.py      # Public Amiga API (existing import paths retained)
            indexed.py       # Standard adaptive RGB12 register palettes
            ehb.py           # Linked full/half-bright palette fitting and codes
            ham.py           # Stateful greedy HAM6 encoding and decoding
            common.py        # Fixed register-table and code-grid validation
    constraints/
        palette_banks.py     # Shared tile-to-bank fitting and local pixel codes
        binary_groups.py     # Exact binary fitting for groups sharing one selector
        cells.py             # Generic two-colour cell fitting, optional legal pairs
        shared_background.py # Generic local sets with an image-wide shared colour
        global_palette.py    # Generic whole-image selection from a fixed palette
        adaptive_palette.py  # Grid-snapped adaptive palette clustering
        histogram.py         # Shared deterministic frequency-weighted RGB sampling
        __init__.py          # Package description
    palettes/
        __init__.py          # Public PALETTES / get_palette API
        builtin.py           # Ordered registry and legacy constant exports
        _shared.py           # Palette constructor and standard RGB primaries
        teletext.py          # One palette module per machine family
        c64.py
        spectrum.py
        cpc.py
        bbc.py
        amiga.py
        atari.py
        megadrive.py
        snes.py
        nes.py
        mastersystem.py
        gameboy.py
        cga.py
        ega.py
        consoles.py          # Compatibility imports only; no definitions
    profiles/                # Geometry, default palette, constraint-model identifiers
    model.py                 # Shared Palette, Geometry, TargetProfile, IndexedImage
    colour_spaces.py         # Cartesian RGB grids and shared weighted RGB metric
    ordered.py               # Bayer matrices and palette-aware ordered selection
    quantize.py              # Palette quantisation and Floyd–Steinberg diffusion
    geometry.py              # Fitting and resizing
    adjustments.py           # Source brightness, contrast, saturation, hue and RGB gains
    render.py                # Generic indexed preview rendering, scaling and aspect
    conversion_modes.py      # Mode metadata, validation and adapter registry
    convert.py               # Shared file conversion pipeline
    cli.py                   # Command-line argument handling
    guided.py                # Optional interactive builder for ordinary convert arguments
    path_input.py            # Optional cross-platform terminal completion backend
    settings.py              # Portable option validation and shared UI constraint hints
    presets.py               # Versioned JSON presets, built-ins and user storage
```

Machine modules live only under `targets`, and fitting implementations live
only under `constraints`. The package root contains the shared conversion,
image preparation, rendering, registry and CLI modules.

Palette definitions and any RGB grid belong to their machine-family module.
Target implementations import that module directly. `palettes.builtin` collects
the definitions in a stable ordered registry and retains its earlier constant
imports for compatibility. `palettes.consoles` only re-exports the Mega Drive
and SNES constants for earlier callers; new code uses their individual modules.
BBC and Teletext reuse the standard primary-colour tuple from `_shared`, while
retaining separate named palettes. No palette module imports a target adapter.

## Dependencies and conversion flow

Shared models, quantisation, fitting algorithms and generic preview rendering
do not import machine implementations at runtime. A target may use these shared
building blocks, but it owns its hardware rules and logical representation.

`convert_file` performs the same sequence for each profile:

1. Resolve a palette and geometry, including optional custom dimensions.
2. Ask the mode registry to validate target options and choose an adapter.
3. Resize the source and apply brightness, contrast, saturation, hue shift and
   RGB gains, in that order. Neutral stages bypass enhancement/colour transforms.
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

## Atari visual playfields

`AtariPlayfield` holds height, band height, mode, palette and validated rows.
Each `AtariPlayfieldRow` holds even foreground/background TIA colour codes and
20 or 40 logical pattern bits. Bit zero is leftmost; repeated/mirrored halves
are expanded by the target rasteriser, followed by four-clock horizontal blocks
and vertical band repetition. Logical patterns do not use PF register byte order.

`fit_binary_groups` is target independent. Each group contains the original RGB
samples that must share one output selector. It evaluates every distinct RGB
pair using weighted sums and squared sums, preserving the full squared-error
objective even for groups of different sizes. It returns the pair and unrounded
group means. Atari defines groups from four-clock blocks, shared scanlines and,
where applicable, matching positions in both halves. Dithering operates on a
single strip of the independent bits with the selected pair; the target resets
it per band so repeated/mirrored structure is retained. This intentionally
restricts Floyd–Steinberg to horizontal propagation along that strip.

`palettes/atari.py` owns independently generated idealised RGB approximations;
the palette index maps to an even TIA register value. PAL duplicate grayscale
banks remain present to preserve register ordering. Profiles own nominal
NTSC/PAL dimensions and preview aspect. Unrestricted bitmap conversion still
uses the generic quantiser, with palette mixing and custom sizes available.
`--atari-row-height` is an optional adapter parameter validated by the mode
registry and rejected outside Atari playfield modes. The shared file pipeline
only forwards it. No timing kernel, native file or executable exporter is planned.

## Original-colour pixelation

Generic original-colour pixelation uses `pixelate.py` independently of indexed
conversion. Pillow integer reduction averages each source block; nearest-neighbour
enlargement to whole block dimensions followed by clipping preserves grid spacing
at partial edges. The `pixelate` command and guided starting point use this RGB
path without target profiles, palette fitting or dithering.

## Ordered dithering

`ordered.py` owns Bayer ranks, centered thresholds, and palette-aware ordered
selection. A nearest-colour anchor is paired with the available colour whose
weighted-RGB segment projection best reconstructs the source. Candidate coverage
is rounded to multiples of `1 / bayer_size**2` before scoring its mean-colour
error. A contrast term adds `0.25 * t * (1-t) * max(0, L-S)`, where `L` is the
weighted squared distance between the mixing colours, and `S` is the anchor's
nearest distinct palette-colour distance. This penalises high-contrast speckles
while leaving mixtures between nearest neighbours, binary palettes and exact
palette matches unpenalised. Duplicate entries do not reduce `S` to zero.
Equal scores
prefer smaller colour separation, then palette order. Index ordering fixes
threshold orientation when the nearest anchor changes. Complete RGB grids use
per-channel rounding between adjacent legal levels. Both quantisation paths
share the weighted metric constants from `colour_spaces.py`; the existing
`quantize.colour_distance` and `quantize.RGB_WEIGHTS` imports remain valid.

The distinction between mean-colour accuracy and distracting mixing contrast
follows the motivation discussed in [Yliluoma's ordered dithering article](https://bisqwit.iki.fi/story/howto/dither/jy/).
The spacing-relative variance score is an original implementation; it is still
a per-pixel heuristic and does not introduce neighbourhood analysis or diffusion.

`quantize_bayer` takes `bayer_size` and a logical `bayer_origin`. Cell adapters
supply crop origins, preserving matrix phase across boundaries without changing
palette selection. Atari uses the independent bit coordinate and band index,
then expands its model normally. No diffusion crosses cells or alters patterns.
Bayer sizes are limited to 2, 4 and 8, with 4 the default. CLI/API file conversion
rejects an explicit `bayer_size` for another dither before opening the input.
The registry binds this optional quantiser keyword without knowing the algorithm.

A custom `pixel_lookup` overrides generic ordered selection and receives the
original RGB and local position; it owns its Bayer choice. HAM supplies such a
lookup, enumerating all 64 legal codes from the current held colour and applying
the shared ordered selector, including the selected matrix size, to their decoded RGBs. It retains the chosen code
and updates held state, resetting at each scanline. Plain/FS HAM keeps its
previous nearest-channel fast path and output. Bayer uses no error buffer.

All dithering belongs to logical conversion. Preview scaling and display
post-processing remain independent. `display_effects.py` implements the optional
Game Boy LCD, scanline and CRT aperture-grille treatments of enlarged RGB previews
and imports no target adapters.
`render_indexed` supplies the logical grid and the palette's lightest colour;
`convert_file` still returns the unmodified indexed raster. Future CRT effects
belong in this presentation layer. See [display effects](display-effects.md).
Scanline weights are integrated over each output row in logical coordinates,
then applied with linear-light sRGB lookup tables. They preserve the logical
beam count through aspect correction, including fractional row heights.
The CRT aperture effect uses the same row weights with a repeating output-column
RGB stripe mask. The two attenuations are combined in a shared linear-light
lookup table before encoding to sRGB once. The existing strength setting controls
both. Grille phase is fixed to the full image's left edge and does not follow
source-pixel boundaries; detail crops preserve the rendered pattern.
`render_indexed` applies `display_brightness` as its final RGB step after the
display effect, immediately before `convert_file` saves the image. Its linear-
light lookup clamps to the display range and bypasses processing at gain 1,
preserving existing output exactly. It is independent of source `brightness`,
which runs before quantisation. Validation occurs before file conversion reads
the source, and presets and the guide expose the two stages separately.

## Console palette banks

`constraints.palette_banks` fits shared RGB banks and assigns one to each tile.
`BankedImage` validates tile dimensions, bank selectors, local codes, equal bank
capacities and, when requested, the shared slot-zero backdrop. It contains no hardware register
layout or target imports. Fitting seeds banks from farthest-error tiles, then
alternates histogram error assignment and grid-snapped bank fitting for up to
four rounds, retaining the best result. It is a deterministic bounded heuristic.
Tile diffusion and Bayer selection use the existing quantiser; diffusion resets
per tile and Bayer receives the original logical origin.

Mega Drive and SNES adapters supply their RGB grids and bank counts and retain
target-owned register words alongside the generic tile representation.
Rasterisers flatten bank/local codes into an indexed preview; slot zero in
every bank has the same opaque RGB. SNES indexed backgrounds separately reuse
adaptive screen-palette fitting, with a validated CGRAM table and pixel grid.
The file pipeline only forwards the declared mode options. Native packing,
VRAM limits, sprites, multiple layers and console display effects are deferred.

The same fitter accepts either a regular RGB grid or a fixed candidate palette.
NES supplies fixed PPU colours and four four-entry banks, with one bank selected
per 16x16 attribute region and a common backdrop. Fixed-palette fitting reuses
the generic global selector. Master System supplies RGB6 and two independent
sixteen-entry banks, with `shared_backdrop=False`; every entry is available to
background tiles. Existing RGB-grid/shared-backdrop defaults are unchanged.
Game Boy uses the shared luminance conversion and quantiser with four neutral
shades, retaining two-bit codes and a BGP register. Its renderer maps shades to
green or grey; the tint does not influence fitting. Game Boy Color is deferred.

CGA uses fixed palette variants and retains the Colour Select register; no
free palette fitting is applied in its constrained modes. EGA 200-line screens
use standard RGBI colours, while 350-line screens may reuse adaptive RGB-grid
fitting to select sixteen RGB6 colours. `EGAImage` validates the register table
and its display-family limits. Standard RGBI definitions live in palette
`_shared`, independently of either target. Presentation hints in settings
restrict palette choices by constraint model; target adapters perform final
validation. These additions do not change the shared file pipeline.

## Guided CLI boundary

`guided.py` is an optional command builder, loaded only for `retroimg guided`.
It reads profile/palette registries, mode metadata and supported adapter keys.
Small UI tables provide explanations, restricted palette choices and dimension
hints; target adapters retain the authoritative conversion validation. Amiga
screen-colour choices reuse the existing target limits. New target constraints
should update these presentation hints alongside their CLI exposure.

The builder uses ordinary parser defaults, collects applicable options and
returns a `convert` argument list. The CLI feeds that list through its existing
parser and conversion branch. It does not execute the printed shell command.
The guide has no palette fitting, quantisation, rendering or image-writing
implementation. Pillow is used only to check input images and output extensions.
Core conversion modules do not depend on the guide.

Input/output paths may be supplied or prompted. File paths are made absolute;
argument lists keep spaces and shell metacharacters literal. Equals syntax
preserves negative scientific-notation values through argparse. Displayed
commands use POSIX quoting or PowerShell single-quoted tokens on Windows.
Path prompts lazily load `path_input.py`, which uses `prompt_toolkit` for the
same Tab completion on Unix and Windows. Directory candidates include a path
separator; names remain literal, including spaces and shell metacharacters.
The completion library is an optional `guided` install extra. When it is absent,
the guide uses ordinary path input and omits completion hints. Other import
errors propagate rather than being mistaken for a missing optional dependency.
Piped input and injected test readers retain ordinary input. Menu prompts do
not use the completion backend or change global readline configuration.

The UI has injectable input/output for tests. Enter accepts defaults, q/EOF/
Ctrl-C cancels, and the final review offers conversion, revision or command-only
output. Revisions preserve compatible defaults and discard inapplicable flags.
Existing outputs require explicit replacement before returning conversion
arguments. None of these review/path checks alter the noninteractive converter.

## Preset boundary

`presets.py` handles built-in definitions, JSON loading, user-file discovery and
saving. The version-1 document has a name, optional description and conversion
settings. Input/output paths, nested preset references and unknown settings are
rejected. Built-ins are code data and need no packaging resources or writable
installation directory. Only an explicit guide save/update writes a preset.
New saves use exclusive creation; updates replace a complete temporary file.

`settings.py` shares the guide's existing palette/dimension hints and validates
preset settings against profile/palette registries, mode adapters and existing
Amiga limits. It checks types, finite values, dependent options and dimensions
without processing an image. Target implementations retain final authority.
Normalization pins implicit palette, Bayer size, screen-colour count and Atari
band height. Compact snapshots contain applicable flags and neutral colour
values, keeping presets portable and independent of image paths.

The CLI parses explicit overrides with sentinel defaults, so an explicitly
supplied neutral value still overrides a saved non-neutral value. This also
preserves argparse's supported flag abbreviations. Inherited options made
inapplicable by a profile/mode/dither change are cleared; invalid explicit
combinations still fail validation. The existing conversion branch receives the
merged settings. Image conversion, target optimisation and rendering are unchanged.

The guide may start from a catalogued or explicit preset, show its summary,
revise it, save a new copy, or explicitly update a loaded user file. Printed
commands expand settings and remain usable without the preset file. User storage
uses the platform config directory, with a `--presets-dir` override for local or
portable collections. Invalid catalog files are reported and skipped.
