"""Pixelation in RGB, independent of machine palettes and target geometry."""
from pathlib import Path

from PIL import Image


def validate_block_size(block_size: int) -> None:
    if type(block_size) is not int or block_size < 1:
        raise ValueError('pixel block size must be a positive whole number')


def pixelate_image(image: Image.Image, block_size: int) -> Image.Image:
    """Fill fixed-size blocks with their average colour, retaining image dimensions.

    Blocks start at the top-left corner. Right and bottom edge blocks are
    clipped to the image, so an uneven image size never stretches the grid.
    """
    validate_block_size(block_size)
    source = image.convert('RGB')
    if block_size == 1:
        return source
    step_x, step_y = min(block_size, source.width), min(block_size, source.height)
    reduced = source.reduce((step_x, step_y))
    # Enlarge to whole blocks before clipping. Resizing directly to source.size
    # would stretch the edge blocks when dimensions are not divisible by the step.
    enlarged = reduced.resize((reduced.width * step_x, reduced.height * step_y), Image.Resampling.NEAREST)
    return enlarged.crop((0, 0, source.width, source.height))


def pixelate_file(input_path: Path, output_path: Path, *, block_size: int = 8) -> Image.Image:
    """Pixelate original RGB colours, preserving dimensions without a retro palette."""
    validate_block_size(block_size)
    with Image.open(input_path) as source:
        result = pixelate_image(source, block_size)
    result.save(output_path)
    return result
