# IBM EGA

EGA's standard display palette differs between 200- and 350-line operation.
Ordinary 200-line modes use the sixteen RGBI colours familiar from CGA. The
350-line mode can select sixteen of 64 RGB6 colours. The monitor compatibility
reason is explained in the [colour-generation reference](https://keyj.emphy.de/cga-ega-vga/).
Unusual monitors and display tricks are outside this initial scope.

| Profile | Logical raster | Constrained colours | Suggested scale / preview |
| --- | --- | --- | --- |
| `ega-320` | 320×200 | Standard sixteen RGBI colours | 2 / 640×480 |
| `ega-640-200` | 640×200 | Standard sixteen RGBI colours | 1 / 640×480 |
| `ega-640` | 640×350 | Up to sixteen selected RGB6 colours | 1 / 640×480 |

Previews use nominal 4:3 aspect correction, retaining every logical pixel.
Custom dimensions are available without alignment restrictions; the profile
still selects its original 200- or 350-line colour rules.

The `ega-default` palette is the classic sixteen-colour PC palette, including
brown. It is required by 200-line constrained modes and can also be chosen for
350-line conversion. The `ega` palette contains all 64 RGB6 colours, using
0/85/170/255 channel levels. With 350-line `--ega-mode constrained`, an adaptive
fitter selects up to sixteen colours against the prepared source, using up to
1024 frequency-weighted samples and six refinement rounds. Selection is a
deterministic heuristic, performed before dithering.

```bash
retroimg convert photo.jpg ega-classic.png --profile ega-320 --ega-mode constrained \
    --dither floyd-steinberg --scale 2
retroimg convert photo.jpg ega-selected.png --profile ega-640 --ega-mode constrained \
    --dither bayer --bayer-size 4 --scale 1
retroimg convert photo.jpg ega-fixed.png --profile ega-640 --ega-mode constrained \
    --palette ega-default --scale 1
```

`--ega-mode bitmap` remains the default, with arbitrary palette swaps and no
sixteen-colour limit. In particular, `--palette ega` in bitmap mode can use all
64 colours and is an aesthetic option rather than a standard EGA screen.
All source adjustments, dithers, guided choices and presets are supported.
`--colours` remains reserved for selectable Amiga screen palettes.

`EGAImage` retains selected six-bit palette registers and local pixel indices.
Register bits are `r g b R G B`, where uppercase is the primary 170-level bit
and lowercase the secondary 85-level bit. Standard brown uses register 0x14;
0x06 would produce dark yellow. The rasteriser decodes the register values
separately from fitting and preview scaling. Native planar memory packing,
VGA DAC modes, raster changes and hardware export remain deferred.

[View the EGA comparisons](../../samples/comparisons/README.md).
