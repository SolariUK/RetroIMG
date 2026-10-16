from PIL import Image

from retroimg.geometry import resize_to_geometry
from retroimg.model import Geometry
from retroimg.palettes import get_palette
from retroimg.quantize import quantize


def test_teletext_palette_has_eight_colours():
    assert len(get_palette("teletext").colours) == 8


def test_geometry_resize_exact_size():
    image = Image.new("RGB", (100, 50), "white")
    result = resize_to_geometry(image, Geometry(80, 75), fit="cover")
    assert result.size == (80, 75)


def test_quantize_indexes_are_valid():
    image = Image.new("RGB", (4, 4), (250, 10, 10))
    result = quantize(image, get_palette("teletext"), dither="none")
    result.validate()

from retroimg.targets.teletext import constrain_teletext_mosaic
from retroimg.model import IndexedImage


def test_teletext_mosaic_limits_each_cell_to_two_colours():
    palette = get_palette("teletext")
    # One 2x3 cell deliberately containing six different colours.
    image = IndexedImage(
        width=2,
        height=3,
        palette=palette,
        pixels=((0, 1), (2, 3), (4, 5)),
    )
    result = constrain_teletext_mosaic(image)
    assert len({value for row in result.pixels for value in row}) <= 2


def test_teletext_mosaic_rejects_incompatible_geometry():
    palette = get_palette("teletext")
    image = IndexedImage(
        width=3,
        height=3,
        palette=palette,
        pixels=((0, 0, 0), (0, 0, 0), (0, 0, 0)),
    )
    try:
        constrain_teletext_mosaic(image)
    except ValueError as exc:
        assert "divisible by 2" in str(exc)
    else:
        raise AssertionError("expected incompatible geometry to fail")
