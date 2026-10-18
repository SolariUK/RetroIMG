# Generic pixelation

Pixelate an image in its own RGB colours, independently of a retro system:

```bash
retroimg pixelate photo.jpg pixelated.png --block-size 8
```

`--block-size` is a positive whole-number width and height in **source pixels**.
The default is 8. A value of 1 leaves the RGB pixels unchanged; larger values
produce larger, chunkier blocks. The image keeps its original dimensions.
Blocks start at the top-left corner; partial blocks at the right and bottom
edges are clipped rather than stretching the grid.

Each block is filled with the average of its source RGB colours. Averaging can
create intermediate shades, but there is no imposed palette, colour-count
limit, dithering or hardware resolution. Output is RGB. Use PNG for lossless
examples and inspect at 100% to judge the block sizes.

In `retroimg guided`, choose **Pixelate original image colours** at the starting
point, then set **Pixel block size**. The guide shows the equivalent command and
lets you revise the size, write the image or keep the command only.

Python callers can use `pixelate_image(image, block_size)` or
`pixelate_file(input_path, output_path, block_size=8)` from `retroimg.pixelate`.
Both return an RGB Pillow image. The input image is left unchanged.

[Macaws examples](../samples/pixelation/README.md) compare 4×4, 8×8 and 16×16
blocks at the original image dimensions, with unscaled crops:

```bash
python examples/generate_pixelation.py --replace
```
