"""Draws the symbols of the map: summit, saddle, hut, shelter, viewpoint, parking,
cable car and the ladder of via ferratas. They are drawn here, not taken from anywhere.

The map library loads symbols as one image with a list of where each one lies
("sprite"), in single and double resolution. The files are part of the repository
(`maps/sprite/`); after a change to a symbol they are written anew:

    python -m app.modules.maps.sprites
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

FOLDER = Path(__file__).parent / "sprite"
# Edge of a symbol in pixels at single resolution.
SIZE = 22
_SCALE = 8  # drawn larger and scaled down, for smooth edges
WHITE = (255, 255, 255, 255)
BLACK = (17, 17, 17, 255)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    edge = SIZE * _SCALE
    image = Image.new("RGBA", (edge, edge), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image), edge


def _peak() -> Image.Image:
    image, draw, e = _canvas()
    # A black triangle with a white edge, readable on forest and on rock.
    draw.polygon([(e * 0.5, e * 0.12), (e * 0.94, e * 0.88), (e * 0.06, e * 0.88)], fill=WHITE)
    draw.polygon([(e * 0.5, e * 0.27), (e * 0.8, e * 0.8), (e * 0.2, e * 0.8)], fill=BLACK)
    return image


def _saddle() -> Image.Image:
    image, draw, e = _canvas()
    # Two arcs back to back: the ridge falls from both sides to the pass.
    for width, colour in ((e * 0.2, WHITE), (e * 0.1, BLACK)):
        draw.arc(
            (-e * 0.42, e * 0.12, e * 0.42, e * 0.88), -62, 62, fill=colour, width=round(width)
        )
        draw.arc(
            (e * 0.58, e * 0.12, e * 1.42, e * 0.88), 118, 242, fill=colour, width=round(width)
        )
    return image


def _badge(draw: ImageDraw.ImageDraw, e: int, colour: tuple, round_: bool = True) -> None:
    box = (e * 0.05, e * 0.05, e * 0.95, e * 0.95)
    inner = (e * 0.12, e * 0.12, e * 0.88, e * 0.88)
    if round_:
        draw.ellipse(box, fill=WHITE)
        draw.ellipse(inner, fill=colour)
    else:
        draw.rounded_rectangle(box, radius=e * 0.2, fill=WHITE)
        draw.rounded_rectangle(inner, radius=e * 0.14, fill=colour)


def _house(draw: ImageDraw.ImageDraw, e: int, colour: tuple, door: tuple | None) -> None:
    draw.polygon([(e * 0.5, e * 0.24), (e * 0.8, e * 0.5), (e * 0.2, e * 0.5)], fill=colour)
    draw.rectangle((e * 0.29, e * 0.48, e * 0.71, e * 0.74), fill=colour)
    if door is not None:
        draw.rectangle((e * 0.44, e * 0.56, e * 0.56, e * 0.74), fill=door)


def _hut() -> Image.Image:
    image, draw, e = _canvas()
    orange = (224, 112, 28, 255)
    _badge(draw, e, orange)
    _house(draw, e, WHITE, orange)
    return image


def _shelter() -> Image.Image:
    image, draw, e = _canvas()
    grey = (96, 96, 96, 255)
    _badge(draw, e, grey)
    # A roof on two posts: open, without walls.
    draw.polygon([(e * 0.5, e * 0.26), (e * 0.82, e * 0.52), (e * 0.18, e * 0.52)], fill=WHITE)
    draw.rectangle((e * 0.28, e * 0.5, e * 0.36, e * 0.76), fill=WHITE)
    draw.rectangle((e * 0.64, e * 0.5, e * 0.72, e * 0.76), fill=WHITE)
    return image


def _viewpoint() -> Image.Image:
    image, draw, e = _canvas()
    _badge(draw, e, (38, 110, 60, 255))
    # A fan of sight opening upwards from the place one stands on.
    draw.pieslice((e * 0.16, e * 0.22, e * 0.84, e * 0.9), 215, 325, fill=WHITE)
    draw.ellipse((e * 0.43, e * 0.6, e * 0.57, e * 0.74), fill=(38, 110, 60, 255))
    return image


def _parking() -> Image.Image:
    image, draw, e = _canvas()
    blue = (30, 90, 180, 255)
    _badge(draw, e, blue, round_=False)
    # The letter P from a stem and a bowl.
    draw.rectangle((e * 0.34, e * 0.25, e * 0.45, e * 0.77), fill=WHITE)
    draw.ellipse((e * 0.34, e * 0.25, e * 0.7, e * 0.57), fill=WHITE)
    draw.ellipse((e * 0.45, e * 0.34, e * 0.59, e * 0.48), fill=blue)
    return image


def _cable_car() -> Image.Image:
    image, draw, e = _canvas()
    _badge(draw, e, BLACK, round_=False)
    # A cabin hanging from the rope.
    draw.line((e * 0.18, e * 0.36, e * 0.82, e * 0.24), fill=WHITE, width=round(e * 0.05))
    draw.line((e * 0.5, e * 0.3, e * 0.5, e * 0.46), fill=WHITE, width=round(e * 0.05))
    draw.rounded_rectangle((e * 0.3, e * 0.44, e * 0.7, e * 0.76), radius=e * 0.06, fill=WHITE)
    draw.rectangle((e * 0.36, e * 0.5, e * 0.64, e * 0.6), fill=BLACK)
    return image


def _ladder() -> Image.Image:
    image, draw, e = _canvas()
    # Two rails and four rungs, black on a white edge.
    for width, colour in ((e * 0.2, WHITE), (e * 0.09, BLACK)):
        w = round(width)
        for x in (0.33, 0.67):
            draw.line((e * x, e * 0.08, e * x, e * 0.92), fill=colour, width=w)
        for y in (0.22, 0.41, 0.6, 0.79):
            draw.line((e * 0.33, e * y, e * 0.67, e * y), fill=colour, width=w)
    return image


SYMBOLS = {
    "peak": _peak,
    "saddle": _saddle,
    "hut": _hut,
    "shelter": _shelter,
    "viewpoint": _viewpoint,
    "parking": _parking,
    "cable-car": _cable_car,
    "ladder": _ladder,
}


def build(ratio: int) -> tuple[Image.Image, dict]:
    """The sheet with all symbols in a row and the list of their places."""
    edge = SIZE * ratio
    sheet = Image.new("RGBA", (edge * len(SYMBOLS), edge), (0, 0, 0, 0))
    index = {}
    for position, (name, draw) in enumerate(SYMBOLS.items()):
        sheet.paste(draw().resize((edge, edge), Image.LANCZOS), (position * edge, 0))
        index[name] = {
            "x": position * edge,
            "y": 0,
            "width": edge,
            "height": edge,
            "pixelRatio": ratio,
        }
    return sheet, index


def write(folder: Path = FOLDER) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for ratio, suffix in ((1, ""), (2, "@2x")):
        sheet, index = build(ratio)
        sheet.save(folder / f"sprite{suffix}.png", optimize=True)
        (folder / f"sprite{suffix}.json").write_text(json.dumps(index, indent=1) + "\n")


if __name__ == "__main__":
    write()
    print(f"{len(SYMBOLS)} symbols written to {FOLDER}")
