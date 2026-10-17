# Nintendo Entertainment System / NES

The `nes` profile uses a 256×240 logical picture with nominal 4:3 preview
aspect. At scale 2 it renders 640×480. The `nes` palette retains all 64 PPU
colour-code slots, including duplicate RGBs. Its common NTSC RGB approximation
is a preview choice: composite output has no single definitive digital palette.
The [colour-data reference](https://pkg.go.dev/github.com/andrewthecodertx/go-nes-emulator/pkg/ppu#HardwarePalette)
documents this commonly used table. Emphasis bits and PAL palette variants
remain deferred.

`--nes-mode bitmap` is the default unrestricted conversion. It allows palette
swaps and does not limit local or image-wide colour counts.

`--nes-mode attributes` fits one static background plane. Four shared palettes
each contain three independently selected colours plus a common backdrop,
for at most thirteen distinct RGBs. One palette applies to each 16×16 region,
covering four 8×8 hardware tiles. The original [attribute-table documentation](https://www.nesdev.org/wiki/PPU_attribute_tables)
describes this distinction. Custom constrained dimensions must be multiples of
16; bitmap dimensions are unrestricted. The built-in NES palette is required.

```bash
retroimg convert photo.jpg nes.png --profile nes --nes-mode attributes --scale 2
retroimg convert photo.jpg nes-bayer.png --profile nes --nes-mode attributes \
    --dither bayer --bayer-size 4 --saturation 1.1 --scale 2
```

All colour controls apply before fitting. The shared palette-bank fitter selects
from fixed NES colour candidates, excluding the problematic below-black `$0D`
code. It chooses the backdrop from the most frequent nearest source colour,
seeds palettes from high-error regions, then alternates assignment and palette
refitting for up to four rounds. Each fixed-palette fit uses up to 512 weighted
samples and two improving swaps. It is a deterministic heuristic, and attribute
clash can remain. Dithering follows fitting: Floyd–Steinberg resets within each
16×16 region; Bayer uses original logical coordinates.

`optimise_nes` retains `NESImage.registers` (four four-entry PPU colour-code
palettes) and `.attributes` (`BankedImage`, with region selectors and local
two-bit pixel codes). `rasterize_nes` separately expands these into an opaque
preview. This is not a packed nametable/CHR file; tile-memory limits, sprites,
scrolling, mapper-specific attributes, raster effects and native export are deferred.

[View the NES comparisons](../../samples/comparisons/README.md).
