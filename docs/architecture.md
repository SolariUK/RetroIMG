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
    constraints/
        cells.py             # Generic two-colour cell fitting, optional legal pairs
        shared_background.py # Generic local sets with an image-wide shared colour
        global_palette.py    # Generic whole-image selection from a fixed palette
        __init__.py          # Shared entry point and lazy legacy Teletext forwarding
    palettes/                # Named RGB colour definitions
    profiles/                # Geometry, default palette, constraint-model identifiers
    model.py                 # Shared Palette, Geometry, TargetProfile, IndexedImage
    quantize.py              # Palette quantisation and Floyd–Steinberg diffusion
    geometry.py              # Fitting and resizing
    adjustments.py           # Source saturation, hue rotation and RGB gains
    render.py                # Generic indexed preview rendering, scaling and aspect
    conversion_modes.py      # Mode metadata, validation and adapter registry
    convert.py               # Shared file conversion pipeline
    cli.py                   # Command-line argument handling
```

Root-level `teletext.py`, `spectrum.py`, `c64.py`, `cpc.py`, `cellfit.py` and
`palettefit.py` are small compatibility modules. Implementations live in the
packages above; the old files do not contain separate copies of algorithms.

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
cell fitter; C64 uses the shared-background fitter; CPC uses whole-image palette
selection. The hardware rules do not live inside those reusable algorithms.

Each target currently fits comfortably in one module. A target can become a
subpackage if its modes grow substantially, without requiring that extra
structure for every simpler target. There is no plugin framework or mandatory
base class: the registry's adapter contract is an RGB image, palette and dither
setting returning an `IndexedImage`.

## Canonical Python imports

```python
from retroimg.targets.teletext import optimise_teletext_mosaic, rasterize_teletext
from retroimg.targets.spectrum import optimise_spectrum_attributes, rasterize_spectrum
from retroimg.targets.c64 import optimise_c64_multicolour, rasterize_c64_multicolour
from retroimg.targets.cpc import optimise_cpc, rasterize_cpc

from retroimg.constraints.cells import quantize_cells
from retroimg.constraints.shared_background import fit_shared_background
from retroimg.constraints.global_palette import select_palette_indices
from retroimg.render import render_indexed
```

Earlier public import paths remain supported. Compatibility target modules
re-export the same class/function objects. The earlier Teletext functions in
`retroimg.constraints` and rasterisers in `retroimg.render` forward lazily to
the target modules, preventing circular imports and keeping generic imports
independent of machines. Existing CLI flags, defaults and output behaviour are
preserved; unrestricted palette/profile combinations remain available.

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

The next planned target is BBC Micro bitmap modes. Hardware exporters and any
future optional CRT post-processing remain separate concerns; neither is
implemented by this restructuring.

## Refactor verification

The fast regression suite includes legacy import compatibility and a fresh
interpreter check that shared modules do not load target implementations.
For visual verification, regenerate the gallery into a new directory using
the same sources and compare source checksums, settings and output PNG hashes
in the two `manifest.json` files. Matching PNG hashes establish byte-for-byte
equality, including all palette, geometry, dithering and adjustment examples.
