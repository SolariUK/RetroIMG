# Original monochrome Game Boy

The `gameboy` profile uses the original 160×144 square-pixel display. At scale
4 its preview is 640×576. It offers two four-shade palettes, ordered light to dark:
`gameboy` is a classic green LCD approximation and `gameboy-grey` uses neutral
255/170/85/0 greys. The green values are an aesthetic approximation, not measured
LCD colourimetry. Game Boy Color is a separate future target.

`--gameboy-mode bitmap` retains unrestricted palette conversion and palette
swapping, like other targets. The default green palette is fitted directly
against RGB source colours in this mode.

`--gameboy-mode tiles` converts the adjusted source to luminance and quantises
it to four shade codes. The tint is applied only when rendering: green and grey
output have identical underlying codes with identical settings. All four
background codes are opaque, including code zero. Tile dimensions must be
divisible by eight, and this mode accepts only `gameboy` or `gameboy-grey`.
These rules follow [Pan Docs' palette registers](https://gbdev.io/pandocs/Palettes.html)
and [2bpp tile description](https://gbdev.io/pandocs/Tile_Data.html).

```bash
retroimg convert photo.jpg gameboy.png --profile gameboy --gameboy-mode tiles \
    --dither bayer --bayer-size 4 --scale 4
retroimg convert photo.jpg gameboy-grey.png --profile gameboy --gameboy-mode tiles \
    --palette gameboy-grey --dither floyd-steinberg --scale 4
```

All source controls apply before luminance conversion. None, Floyd–Steinberg,
and Bayer 2/4/8 are available. A single background palette serves the whole
image, so error diffusion can cross tile boundaries and Bayer is continuous.
There is no additional per-tile colour limit beyond the four global shades.

`optimise_gameboy` retains a `GameBoyImage` with two-bit pixel codes and BGP
register `0xE4` (identity shade mapping). `rasterize_gameboy` interprets that
register and applies the chosen display palette. Python callers may construct
other valid BGP mappings. This model does not pack native tile bytes or budget
unique tiles. Sprites, window composition, LCD ghosting, native exports and
Game Boy Color features are deferred. No input-alpha feature is introduced.

[View the green/grey comparisons](../../samples/comparisons/README.md).

Optional [LCD display effects](../display-effects.md) add inset pixel cells and
subtle shadows: append `--display-effect gameboy-lcd --scale 8`. They affect only
the rendered preview, preserve the selected green/grey tint, and are also
available for experiments with other platforms. See the separate
[full-size examples and crops](../../samples/display-effects/README.md).
