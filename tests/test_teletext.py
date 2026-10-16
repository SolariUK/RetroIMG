import pytest
from PIL import Image

from retroimg.targets.teletext import optimise_teletext_mosaic
from retroimg.constraints.cells import quantize_cells
from retroimg.model import IndexedImage
from retroimg.palettes import get_palette
from retroimg.targets.teletext import rasterize_teletext
from retroimg.targets.teletext import TeletextCell, TeletextPage, page_from_indexed


@pytest.mark.parametrize("pattern", range(64))
def test_all_patterns_round_trip(pattern):
    palette = get_palette("teletext")
    page = TeletextPage(palette, ((TeletextCell(7, 0, pattern),),), 1, 1)
    raster = rasterize_teletext(page)
    assert raster.pixels == tuple(
        tuple(7 if pattern & (1 << (dy * 2 + dx)) else 0 for dx in range(2))
        for dy in range(3)
    )
    assert rasterize_teletext(page_from_indexed(raster)) == raster


def test_known_cell_and_solid_canonicalisation():
    palette = get_palette("teletext")
    image = IndexedImage(2, 3, palette, ((7, 0), (0, 7), (7, 0)))
    assert page_from_indexed(image).cells == ((TeletextCell(7, 0, 25),),)
    solid = IndexedImage(2, 3, palette, ((3, 3),) * 3)
    assert page_from_indexed(solid).cells == ((TeletextCell(3, 3, 0),),)


@pytest.mark.parametrize("palette_name", ["teletext", "c64", "spectrum"])
@pytest.mark.parametrize("dither", ["none", "floyd-steinberg"])
def test_page_preserves_existing_optimiser_output(palette_name, dither):
    palette = get_palette(palette_name)
    source = Image.new("RGB", (8, 9))
    source.putdata([((i * 43) % 256, (i * 97) % 256, (i * 19) % 256) for i in range(72)])
    expected = quantize_cells(source, palette, cell_width=2, cell_height=3, dither=dither)
    page = optimise_teletext_mosaic(source, palette, dither)
    assert (page.columns, page.rows) == (4, 3)
    assert rasterize_teletext(page) == expected


def test_default_page_dimensions():
    page = optimise_teletext_mosaic(Image.new("RGB", (80, 75)), get_palette("teletext"))
    assert (page.columns, page.rows) == (40, 25)


@pytest.mark.parametrize("args", [(0, 0, -1), (0, 0, 64), (-1, 0, 0), (0, -1, 0), (0, 0, 1.5)])
def test_invalid_cell(args):
    with pytest.raises(ValueError):
        TeletextCell(*args)


def test_invalid_page_and_raster():
    palette = get_palette("teletext")
    with pytest.raises(ValueError, match="grid"):
        TeletextPage(palette, (), 1, 1)
    with pytest.raises(ValueError, match="palette"):
        TeletextPage(palette, ((TeletextCell(8, 0, 0),),), 1, 1)
    with pytest.raises(ValueError, match="positive"):
        TeletextPage(palette, (), 0, 0)
    with pytest.raises(ValueError, match="more than two"):
        page_from_indexed(IndexedImage(2, 3, palette, ((0, 1), (2, 0), (0, 0))))
