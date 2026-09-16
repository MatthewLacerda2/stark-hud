#!/usr/bin/env python3
"""Pad an image to an aspect ratio, in its own background colour.

The board draws an image with `object-cover`, which crops whatever does not fit
the widget, and a cropped plot is a plot that lies. So a picture is padded to
the widget's shape before it goes up, rather than trimmed to it.

Its own file, and run with whichever python has Pillow — this machine's
`python3` does not, and `tools/agent.py` is standard-library-only on purpose.

    <some-venv>/bin/python tools/letterbox.py source.png target.png 1.93
"""

import sys

from PIL import Image


def pad(source: str, target: str, aspect: float) -> None:
    with Image.open(source) as image:
        image = image.convert("RGB")
        width, height = image.size
        box = (
            (width, round(width / aspect))
            if width / height >= aspect
            else (round(height * aspect), height)
        )
        canvas = Image.new("RGB", box, image.getpixel((0, 0)))
        canvas.paste(image, ((box[0] - width) // 2, (box[1] - height) // 2))
        canvas.save(target)


if __name__ == "__main__":
    pad(sys.argv[1], sys.argv[2], float(sys.argv[3]))
