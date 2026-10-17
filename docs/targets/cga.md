# IBM CGA

Two graphics profiles use nominal 4:3 picture aspect:

| Profile | Logical raster | Suggested scale | Preview |
| --- | --- | --- | --- |
| `cga-320` | 320×200 | 2 | 640×480 |
| `cga-640` | 640×200 | 1 | 640×480 |

Custom dimensions preserve the profile's relative pixel aspect. There are no
tile-alignment requirements. The RGBI colours use ideal 0/85/170/255 levels,
including brown `(170,85,0)` in slot 6. This follows the standard RGBI display
interpretation described in the emulator author's [palette reference](https://book.martypc.net/appendices/video/palettes),
rather than simulating the analogue response of a particular monitor.

`--cga-mode constrained` requires a palette matching the resolution family:

| Palette | Colour slots, with black in slot zero |
| --- | --- |
| `cga-pal0-low` | Black, green, red, brown |
| `cga-pal0-high` | Black, bright green, bright red, yellow |
| `cga-pal1-low` | Black, cyan, magenta, light grey |
| `cga-pal1-high` | Black, bright cyan, bright magenta, white |
| `cga-mono` | Black and white; 640-family only |

`cga-320` defaults to `cga-pal1-high`; `cga-640` defaults to `cga-mono`.
The separate `cga` palette contains all sixteen RGBI colours for unrestricted
experiments. `--cga-mode bitmap` remains the default and permits any palette,
including sixteen-colour CGA-style pictures that a standard CGA graphics mode
would not display.

```bash
retroimg convert photo.jpg cga.png --profile cga-320 --cga-mode constrained \
    --palette cga-pal1-high --dither bayer --bayer-size 4 --scale 2
retroimg convert photo.jpg cga-brown.png --profile cga-320 --cga-mode constrained \
    --palette cga-pal0-low --dither floyd-steinberg --scale 2
retroimg convert photo.jpg cga-mono.png --profile cga-640 --cga-mode constrained --scale 1
```

Colour adjustments apply before quantisation. All dithering methods, guided
choices and presets are supported; the fixed palette is never refitted into
arbitrary colours. `CGAImage` retains local pixel codes and the Colour Select
register value: 0x00/0x10/0x20/0x30 for the four black-background palettes,
or 0x0F for the white monochrome foreground. A separate rasteriser creates
the opaque PNG. Hardware permits other background/foreground colours, but the
initial presets fix black backgrounds and white monochrome foregrounds.

Composite artefact colours, the alternate cyan/red/white mode, text/tweaked
modes, raster changes, screen-memory packing and native exports are deferred.
[View all CGA comparisons](../../samples/comparisons/README.md).
