"""Small-cell partition fitting must match the exhaustive palette-pair optimum."""
from itertools import combinations_with_replacement
import random

from PIL import Image
import pytest

from retroimg.colour_spaces import RGBGrid, colour_distance
from retroimg.constraints.cells import _fit_small_grid_cell, quantize_cells


@pytest.mark.parametrize('levels', [(0, 255), (0, 17, 255), (0, 51, 153, 255)])
def test_grid_partitions_match_exhaustive_pairs_including_ties(levels):
    values = RGBGrid(levels).palette('oracle').rgb_values()
    generator = random.Random(2026)
    cases = [((0, 0, 0),) * 6, ((255, 255, 255),) * 6,
             ((9, 9, 9),) * 6,
             ((0, 0, 0), (255, 255, 255)) * 3,
             ((0, 17, 0), (17, 0, 0), (17, 17, 0), (0, 0, 0), (0, 0, 17), (17, 17, 17))]
    cases += [tuple(tuple(generator.randrange(256) for _ in range(3)) for _ in range(count))
              for count in range(1, 9) for _ in range(8)]
    for samples in cases:
        expected = min(combinations_with_replacement(range(len(values)), 2),
                       key=lambda pair: sum(min(colour_distance(rgb, values[pair[0]]),
                                                colour_distance(rgb, values[pair[1]]))
                                            for rgb in samples))
        assert _fit_small_grid_cell(samples, levels) == expected, samples


@pytest.mark.parametrize('dither,bayer_size', [('none', 4), ('floyd-steinberg', 4),
                                             ('bayer', 2), ('bayer', 4), ('bayer', 8)])
def test_partition_raster_matches_exhaustive_cells_for_all_dithers(dither, bayer_size):
    palette = RGBGrid((0, 51, 153, 255)).palette('grid')
    source = Image.new('RGB', (8, 9))
    source.putdata([((i * 43) % 256, (i * 97) % 256, (i * 19) % 256) for i in range(72)])
    options = dict(cell_width=2, cell_height=3, dither=dither, bayer_size=bayer_size)
    exhaustive = quantize_cells(source, palette, **options,
                                allowed_pairs=tuple(combinations_with_replacement(range(64), 2)))
    assert quantize_cells(source, palette, **options) == exhaustive


def test_explicit_allowed_pairs_keep_their_own_order_and_constraints():
    palette = RGBGrid((0, 85, 170, 255)).palette('grid')
    source = Image.new('RGB', (2, 3))
    source.putdata([(0, 0, 0), (255, 255, 255)] * 3)
    actual = quantize_cells(source, palette, cell_width=2, cell_height=3,
                            allowed_pairs=((63, 63), (0, 0)))
    assert actual.pixels == ((63, 63),) * 3
