"""Generate a lossless diagnostic source without third-party imagery."""
from pathlib import Path
import argparse
import colorsys

from PIL import Image, ImageDraw, ImageFont


def generate(output: Path) -> None:
    image = Image.new('RGB', (640, 400), '#202020')
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=14)
    except TypeError:  # Pillow 10.0 uses the older fixed-size bundled font.
        font = ImageFont.load_default()

    def label(x, y, text):
        draw.text((x, y), text, fill='white', font=font)

    label(8, 4, 'retroimg diagnostic source: gradients, colour boundaries and fine detail')
    label(8, 26, 'Neutral ramp: banding and brightness preservation')
    for x in range(640):
        value = round(x * 255 / 639)
        draw.line((x, 46, x, 87), fill=(value, value, value))
    label(8, 94, 'Hue ramp: colour boundaries and palette selection')
    for x in range(640):
        rgb = tuple(round(v * 255) for v in colorsys.hsv_to_rgb(x / 640, 0.85, 0.9))
        draw.line((x, 114, x, 155), fill=rgb)
    label(8, 162, 'Red / green / blue ramps: channel balance and shadow detail')
    for channel in range(3):
        left, right = channel * 640 // 3, (channel + 1) * 640 // 3
        for x in range(left, right):
            rgb = [0, 0, 0]
            rgb[channel] = round((x - left) * 255 / (right - left - 1))
            draw.line((x, 182, x, 223), fill=tuple(rgb))
    label(8, 230, 'Flat RGB colours: clean boundaries, swatches and palette limits')
    colours = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0),
               (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
    for i, colour in enumerate(colours):
        draw.rectangle((i * 80, 250, i * 80 + 79, 291), fill=colour)
    label(8, 298, '1 / 2 / 4 / 8 px checkerboards, stripes and diagonal edges')
    for panel in range(8):
        size = (1, 2, 4, 8)[panel % 4]
        for y in range(320, 368):
            for x in range(panel * 80, panel * 80 + 80):
                value = ((x // size + y // size) % 2 if panel < 4 else x // size % 2) * 255
                image.putpixel((x, y), (value, value, value))
    draw.line((320, 368, 639, 320), fill='red', width=2)
    label(8, 376, 'Small text 0123456789 ABCDEFG / crop and fit / aspect ratio')
    image.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
