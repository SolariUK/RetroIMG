# ZX Spectrum

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

[All targets](README.md) · [Project README](../../README.md)
