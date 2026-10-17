# Visual comparison gallery

`generate_gallery.py` runs real source images through Teletext, Spectrum, C64,
CPC, BBC Micro, Amiga indexed/EHB/HAM6 and Atari 2600 conversion. It produces individual PNGs, labelled JPEG comparison
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

`--family` accepts `teletext`, `spectrum`, `c64`, `cpc`, `bbc`, `amiga`, `atari2600`, `megadrive`, `snes` or `all`. The generated
commands use placeholder source paths; replace `/path/to/filename` and run the
commands from the gallery directory, or adjust the output paths.

## Dithering comparisons

The optional `--dither-comparison` matrix compares no dithering, Floyd–Steinberg,
and Bayer 2x2/4x4/8x8 with otherwise identical conversion settings. It selects
Teletext mosaic, Spectrum attributes, C64 multicolour, CPC mode 1, BBC mode 0,
Amiga lores 32-colour/EHB/HAM6, Atari NTSC independent playfields, Mega Drive
320-wide tiles, and SNES tiles/indexed backgrounds. Each
comparison sheet has five columns, one per dithering setting. These runs use
neutral source adjustments so the dithering difference is easy to compare.

```bash
python examples/generate_gallery.py --public-only --dither-comparison \
    --output-dir /path/to/new-dither-gallery

# Source IDs come from sources.json; --source may be repeated
python examples/generate_gallery.py --public-only --dither-comparison \
    --family cpc --source lush-landscape --source portrait-colour \
    --output-dir /path/to/new-cpc-dither-gallery
```

The complete public dithering run generates 420 PNGs and 63 comparison sheets
from the seven bundled sources. The normal gallery matrix below remains
unchanged. `--source` also works for normal gallery runs. Unknown IDs and IDs
excluded by `--public-only` are rejected. Bayer matrix sizes and exact CLI
commands are retained in the output manifest and reproduction commands.

## Comparison matrix

Each source gets the same 128 neutral conversions:

| Target family | Variants |
| --- | --- |
| Teletext | Bitmap/mosaic, each with no dither and Floyd–Steinberg; mosaic C64/Spectrum palette swaps; larger mosaic grid; saturation 1.5 example |
| Spectrum | Unrestricted bitmap/attribute constraints, each with no dither and Floyd–Steinberg |
| C64 | Unrestricted bitmap/multicolour constraints, each with no dither and Floyd–Steinberg; unrestricted Teletext/Spectrum palette swaps |
| CPC | Modes 0/1/2, unrestricted/constrained, each with no dither and Floyd–Steinberg |
| BBC Micro | Modes 0/1/2/4/5, unrestricted/constrained, each with no dither and Floyd–Steinberg; unrestricted CPC/Spectrum palette swaps in mode 1 |
| Amiga | PAL lores 2/4/8/16/32 colours and hires 2/4/8/16, each with no dither and Floyd–Steinberg; unrestricted lores/hires with both dither settings; C64/CPC palette swaps; constrained NTSC lores/hires with dithering; PAL/NTSC EHB and HAM6, each with no dither and Floyd–Steinberg |
| Atari 2600 | NTSC/PAL unrestricted bitmap, independent/repeated/mirrored playfields, all with no dither and Floyd–Steinberg; eight-line chunky playfields with dithering; unrestricted C64 palette swaps |
| Mega Drive | 256/320-wide, 224/240-line profiles; bitmap and tiles, each with no dither and Floyd–Steinberg |
| SNES | Bitmap, 4bpp tiles and 8bpp indexed background, each with no dither and Floyd–Steinberg |

Each source marked `adjusted` in the catalogue also gets 76 constrained examples
with hue +20 degrees and green gain 1.15. These are labelled separately from
neutral baselines. Both the local-only mountain landscape and the bundled lush
landscape have these adjustments. With the current nine-source catalogue, the
full local run produces 1304 converted PNGs and 81 comparison sheets; the
public-only run produces 972 converted PNGs and 63 sheets.

BBC previews are 640x512; comparison tiles expand to hold all rows without
cropping. Mode 2's bitmap/constrained results match with the BBC palette because
all eight steady colours fit. Its other eight hardware slots provide flashing
pairs, which are excluded from static output. Use `--family bbc` for a BBC-only
run (218 local PNGs or 164 public PNGs with the current catalogue).

`--family amiga --public-only` uses all seven bundled sources and generates
266 Amiga PNGs plus seven comparison sheets. PAL examples are 640x512 previews;
NTSC examples are 640x400. Only the lush landscape receives the additional
Amiga hue +20 / green gain 1.15 comparisons, including EHB/HAM6. Experimental output stays outside
the repository; no complete generated gallery is committed.

`--family atari2600 --public-only` generates 154 PNGs and seven comparison
sheets. NTSC previews are 512x384; PAL previews are 608x456. Playfield bands
normally share two scanlines; the chunky examples share eight. The lush
landscape includes hue +20 / green gain 1.15 variants. Palettes are independently
generated idealised analogue colour approximations, described in the main README.

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
- Atari playfield: at most two colours per band, identical pattern/colours on
  shared scanlines, four-clock-wide blocks and the requested half symmetry.
- Amiga indexed: at most the selected screen-colour count and legal four-bit RGB channels.
- EHB: all 64 palette slots have legal precision and the upper 32 are exactly the
  hardware-rounded half-bright counterparts of the lower 32.
- HAM6: the target validates its register/code model before independent decoding;
  the gallery checks the decoded RGB12 raster. PNG colour counts alone cannot
  establish whether an image is encodable in HAM. Unit tests verify known codes,
  scanline resets and greedy choices against an exhaustive 64-code oracle.

These checks establish structural validity, not visual quality or historical
hardware-file compatibility. The normal pytest suite additionally covers the
gallery matrix, constraint-failure detection and exclusion of private files and
metadata from public exports. A lightweight reference-asset check verifies the
bundled files against catalogue checksums and dimensions; full photographic
conversions run separately from pytest. Reference checksums describe the bundled
files; external source overrides are allowed and their actual checksums are
recorded in each gallery manifest.

## Curated repository samples

`generate_samples.py` reuses the converter, mode variants and constraint checks
to maintain ten PNG panels, each 800 pixels wide with two columns and up to
ten rows. The nine family panels show several modes and dithers: Teletext
bitmap/mosaic and palette swaps; C64 geometry, multicolour and greener colour
settings; CPC 0/1/2 bitmap/constrained; Spectrum bitmap/attributes; BBC 0/1/2/4/5;
Amiga RGB12, indexed 2/4/8/16/32, EHB/HAM6 and hires; Atari bitmap, playfield,
repeat/mirror and PAL/NTSC; Mega Drive palette-bank tiles; SNES tiles and indexed
backgrounds. An additional panel retains the CPC macaws blue-gain,
brightness and contrast recipe. This remains a bounded documentation set,
defaulting to `samples/comparisons`; individual conversions are temporary.

```bash
python examples/generate_samples.py --replace

# Alternatively, generate into a new directory
python examples/generate_samples.py --output-dir /path/to/new-samples
```

The committed selection is under [samples/comparisons](../samples/comparisons/README.md).
Only known sample files are refreshed, after successful generation. Unrelated
files cause a refusal; failed conversion leaves existing panels intact. Individual
PNG conversions are temporary and automatically removed. Converted thumbnails
use area averaging when reduced and nearest-neighbour when enlarged; source
thumbnails use smooth fitting. Exact colour
counts refer to underlying conversions rather than whole labelled panels.
Source-image rights remain separately
documented in [samples/README.md](../samples/README.md).

## Conversion timings

Each output entry in `manifest.json` includes `elapsed_seconds`, measured around
file conversion (preparation, fitting, logical conversion and PNG saving).
These wall-clock timings are informational and vary with machine and system
load; they are not deterministic output data or benchmark guarantees. Use the
same source, geometry, adjustments and dither when comparing modes. PAL lores
standard 32-colour, EHB and HAM6 examples provide that comparison directly.
