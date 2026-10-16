# Visual comparison gallery

`generate_gallery.py` runs real source images through Teletext, Spectrum, C64,
CPC, BBC Micro and standard Amiga conversion. It produces individual PNGs, labelled JPEG comparison
sheets, reproduction commands, JSON settings/checksums, and offline HTML and
Markdown indexes. It is a visual integration run, separate from the fast pytest
suite. It uses the installed converter and Pillow, with no additional dependencies.

## Sources and rights

`sources.json` records filenames, captions, fitting choices, rights, reference
checksums and dimensions. The seven public reference images are bundled under
[`samples/sources/`](../samples/README.md), the default `--sources-dir`. No
downloads or scratchpad files are needed for `--public-only` runs. You can still
supply an external source directory for local experiments. Public runs include:

| Filename | Subject | Rights/source |
| --- | --- | --- |
| `macaws.jpg` | Blue-and-yellow macaws | Public-domain release by Adrian Pingstone; [source statement](https://commons.wikimedia.org/wiki/File:Macaw.blueyellow.arp.750pix.jpg) |
| `city-night.jpg` | Stockholm night architecture | CC0 dedication by Martin Eklund; [source statement](https://commons.wikimedia.org/wiki/File:City_silhouette_at_night.jpg) |
| `diagnostic-chart.png` | Mathematical gradients, swatches, fine patterns and text | Generated locally without third-party source imagery |
| `portrait-colour.jpg` | Colour portrait, skin tones, hair and hat texture | CC0, Petr Kratochvil; [source statement](https://www.publicdomainpictures.net/en/view-image.php?image=392516&picture=summer-girl-portrait) |
| `lush-landscape.jpg` | Grass, trees and green hills | CC0, Baap8969; [source statement](https://commons.wikimedia.org/wiki/File:Green_Landscape_with_Hills_and_Trees.jpg) |
| `green-hills.jpg` | Dense vegetation, rocks, sky and distant hills | Worldwide public-domain release, Jon Sullivan; [source statement](https://commons.wikimedia.org/wiki/File:Green_hills.jpg) |
| `portrait-man.jpg` | Near-monochrome portrait and deep shadows | CC0, George Hodan; [source statement](https://www.publicdomainpictures.net/en/free-download.php?id=82849&image=people) |

A run without `--public-only` also requires the two user-supplied files recorded in the
catalogue. Their redistribution rights have not been established, so they are
marked local-only and excluded from public exports. Generated examples retain
the source's credit and rights information; conversion does not establish new
rights to the source image.

Photograph rights are separate from the software licence. The portrait sources
report model releases and caution against offensive or derogatory portrayals;
use neutral conversion comparisons without implying endorsement. Detailed
provenance, rights notes and checksums are in [samples/README.md](../samples/README.md).

Keep experimental outputs in an external temporary directory. Only selected
comparison sheets should later be copied to `samples/comparisons/`; complete
galleries are not committed.

The generator never downloads source files or publishes anything remotely.
Original files are read without modification. Reports include source checksums
and resized source previews, rather than duplicating full-size originals.

Create the diagnostic source without downloading anything:

```bash
python examples/generate_diagnostic_chart.py \
    --output /path/to/source-images/diagnostic-chart.png
```

The output directory must already exist. The chart uses Pillow's bundled font;
font rendering may differ between Pillow versions. The source checksum recorded
by each gallery identifies the exact input used in that run.

## Reproduce the gallery

Install retroimg in the active environment, then run from the project root:

```bash
# Bundled public examples; no downloads or external sources needed
python examples/generate_gallery.py \
    --output-dir /path/to/new-public-gallery \
    --public-only

# All local sources, plus a separate filtered public gallery
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-local-gallery \
    --public-output /path/to/new-public-gallery

# Run just one target family
python examples/generate_gallery.py \
    --sources-dir /path/to/source-images \
    --output-dir /path/to/new-cpc-gallery \
    --family cpc --public-only
```

Use the virtualenv's Python when appropriate. Output directories must be new,
which prevents stale local-only files from surviving in a public export. Open
`index.html` or `README.md` in the chosen output directory. No server or network
access is needed to browse the gallery. JPEG sheets are convenient overviews;
use the linked PNGs to judge exact converted pixels.

`--family` accepts `teletext`, `spectrum`, `c64`, `cpc`, `bbc`, `amiga` or `all`. The generated
commands use placeholder source paths; replace `/path/to/filename` and run the
commands from the gallery directory, or adjust the output paths.

## Comparison matrix

Each source gets the same 78 neutral conversions:

| Target family | Variants |
| --- | --- |
| Teletext | Bitmap/mosaic, each with no dither and Floyd–Steinberg; mosaic C64/Spectrum palette swaps; larger mosaic grid; saturation 1.5 example |
| Spectrum | Unrestricted bitmap/attribute constraints, each with no dither and Floyd–Steinberg |
| C64 | Unrestricted bitmap/multicolour constraints, each with no dither and Floyd–Steinberg; unrestricted Teletext/Spectrum palette swaps |
| CPC | Modes 0/1/2, unrestricted/constrained, each with no dither and Floyd–Steinberg |
| BBC Micro | Modes 0/1/2/4/5, unrestricted/constrained, each with no dither and Floyd–Steinberg; unrestricted CPC/Spectrum palette swaps in mode 1 |
| Amiga | PAL lores 2/4/8/16/32 colours and hires 2/4/8/16, each with no dither and Floyd–Steinberg; unrestricted lores/hires with both dither settings; C64/CPC palette swaps; constrained NTSC lores/hires with dithering |

Each source marked `adjusted` in the catalogue also gets 42 constrained examples
with hue +20 degrees and green gain 1.15. These are labelled separately from
neutral baselines. Both the local-only mountain landscape and the bundled lush
landscape have these adjustments. With the current nine-source catalogue, the
full local run produces 786 converted PNGs and 54 comparison sheets; the
public-only run produces 588 converted PNGs and 42 sheets.

BBC previews are 640x512; comparison tiles expand to hold all rows without
cropping. Mode 2's bitmap/constrained results match with the BBC palette because
all eight steady colours fit. Its other eight hardware slots provide flashing
pairs, which are excluded from static output. Use `--family bbc` for a BBC-only
run (218 local PNGs or 164 public PNGs with the current catalogue).

`--family amiga --public-only` uses all seven bundled sources and generates
202 Amiga PNGs plus seven comparison sheets. PAL examples are 640x512 previews;
NTSC examples are 640x400. Only the lush landscape receives the additional
Amiga hue +20 / green gain 1.15 comparisons. Experimental output stays outside
the repository; no complete generated gallery is committed.

Photos use `cover` fitting; the diagnostic chart uses `contain` so the complete
chart remains visible. Different target geometries can therefore crop photos
differently. Assess colour-constraint changes within the same target geometry.

## Automated checks

Every conversion validates indexed pixels, expected preview dimensions, and
that PNG colours belong to its selected palette. Constrained examples also check:

- Teletext: at most two colours in every 2x3 cell.
- Spectrum: at most two colours per 8x8 cell, with compatible shared brightness.
- C64: at most four colours per 4x8 cell and a legal background shared across
  the whole image. Merely checking each cell independently is insufficient.
- CPC: at most 16, 4 or 2 colours across the entire image, according to mode.
- BBC: at most 2, 4, 8, 2 or 4 steady colours for modes 0, 1, 2, 4 or 5.
- Amiga: at most the selected screen-colour count and legal four-bit RGB channels.

These checks establish structural validity, not visual quality or historical
hardware-file compatibility. The normal pytest suite additionally covers the
gallery matrix, constraint-failure detection and exclusion of private files and
metadata from public exports. A lightweight reference-asset check verifies the
bundled files against catalogue checksums and dimensions; full photographic
conversions run separately from pytest. Reference checksums describe the bundled
files; external source overrides are allowed and their actual checksums are
recorded in each gallery manifest.
