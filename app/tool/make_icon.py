#!/usr/bin/env python3
"""Draws the launcher icon of the app: the mountain of the background on fir green.

    backend/.venv/bin/python app/tool/make_icon.py     (needs Pillow)

Writes the adaptive icon (foreground on a coloured background) and the plain icon
for older Android versions into android/app/src/main/res.
"""

from pathlib import Path

from PIL import Image, ImageDraw

RES = Path(__file__).resolve().parent.parent / "android/app/src/main/res"
GREEN = (31, 95, 69)
# The peak and its shaded east face, as in lib/core/widgets/mountain_background.dart,
# cut out around the summit (x 300..970, y 60..600 of the 1200 x 600 drawing).
PEAK = [(300, 600), (450, 395), (505, 350), (550, 240), (590, 185), (620, 105), (644, 83),
        (670, 117), (692, 195), (736, 287), (788, 347), (866, 469), (970, 600)]
SHADE = [(644, 83), (670, 117), (692, 195), (736, 287), (788, 347), (866, 469), (970, 600),
         (690, 600), (660, 410), (638, 290)]
SNOW = [
    [(644, 83), (620, 105), (602, 153), (624, 139), (638, 159), (654, 135), (670, 153)],
    [(550, 240), (532, 284), (558, 272), (578, 298), (592, 262)],
    [(736, 287), (730, 321), (756, 313), (788, 347)],
]
DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def mountain(size: int, inset: float) -> Image.Image:
    """The mountain on a transparent square; `inset` is the free margin as a share."""
    scale = 4  # drawn larger and scaled down for smooth edges
    canvas = Image.new("RGBA", (size * scale, size * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    box = size * scale * (1 - 2 * inset)
    factor = box / 670  # width of the cut-out
    left = size * scale * inset
    top = size * scale * inset + (box - 540 * factor) / 2

    def place(points):
        return [(left + (x - 300) * factor, top + (y - 60) * factor) for x, y in points]

    draw.polygon(place(PEAK), fill=(247, 249, 248, 255))
    draw.polygon(place(SHADE), fill=(207, 214, 211, 255))
    for patch in SNOW:
        draw.polygon(place(patch), fill=(255, 255, 255, 255))
    return canvas.resize((size, size), Image.LANCZOS)


def main() -> None:
    for name, density in DENSITIES.items():
        folder = RES / f"mipmap-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        # Adaptive icon: 108 dp, of which the launcher shows the inner 66 to 72 dp.
        mountain(round(108 * density), 0.27).save(folder / "ic_launcher_foreground.png")
        # Plain icon for Android 7 and older: a rounded square.
        size = round(48 * density)
        plain = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size * 4, size * 4), radius=size * 4 * 0.22, fill=255
        )
        plain.paste(Image.new("RGBA", (size, size), (*GREEN, 255)), mask=mask.resize((size, size)))
        plain.alpha_composite(mountain(size, 0.14))
        plain.save(folder / "ic_launcher.png")
    adaptive = RES / "mipmap-anydpi-v26"
    adaptive.mkdir(exist_ok=True)
    (adaptive / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        "</adaptive-icon>\n"
    )
    (RES / "values/ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        '    <color name="ic_launcher_background">#1F5F45</color>\n'
        "</resources>\n"
    )


if __name__ == "__main__":
    main()
