#!/usr/bin/env python3
"""Pre-renders DeckRemote's in-app UI assets (needs Pillow) into deck/ui/.

The Deck has no Pillow and Tk draws shapes without anti-aliasing, so every visual piece is
rendered here at 3x and downsampled; the app only places these PNGs and draws text on top.
Layout positions the app needs are written to deck/ui/layout.json.

  python tools/make_ui.py
"""
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_art as A  # noqa: E402

S = A.SS
W, H = 1280, 800
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "deck", "ui")
CYAN, MAGENTA, VIOLET, GREEN, RED = A.CYAN, A.MAGENTA, A.VIOLET, (74, 222, 128), (248, 113, 113)
CARD = (23, 19, 43)

# scene layout (screen pixels)
DECK = dict(cx=905, cy=640, h=120)
HOLO = dict(cx=905, cy=330, s=205)
CARD_BOX = (52, 140, 552, 540)
PILL_WIDTHS = (180, 220, 260, 300, 340, 380, 440)
CHIP_WIDTHS = (200, 240, 280, 320)


def save(img, name):
    img.save(os.path.join(OUT, name), optimize=True)


def down(c, box=None):
    """Downsample an SS canvas (optionally cropped, box in screen px) to 1x."""
    if box:
        c = c.crop(tuple(int(v * S) for v in box))
    return c.resize((c.width // S, c.height // S), Image.LANCZOS)


def transparent():
    return Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))


def holo_box():
    lw, lh = HOLO["s"] * 2.3, HOLO["s"] * 1.7
    x0, y0 = int(HOLO["cx"] - lw / 2), int(HOLO["cy"] - lh / 2)
    return (x0, y0, x0 + int(lw) + 1, y0 + int(lh) + 1)


def backgrounds():
    c = A.background(W * S, H * S, horizon=0.8, vx=0.7)
    disp = A.deck(c, DECK["cx"] * S, DECK["cy"] * S, DECK["h"] * S)
    A.beam(c, disp, (HOLO["cy"] + HOLO["s"] * 0.25) * S, HOLO["s"] * 0.95 * S, DECK["cx"] * S)
    save(down(c).convert("RGB"), "bg_main.png")
    c = A.background(W * S, H * S, horizon=0.86, vx=0.5)
    save(down(c).convert("RGB"), "bg_plain.png")


def hologram():
    box = holo_box()
    c = transparent()
    A.hologram(c, HOLO["cx"] * S, HOLO["cy"] * S, HOLO["s"] * S)
    on = down(c, box)
    save(on, "pad_on.png")
    dim = on.copy()
    dim.putalpha(on.getchannel("A").point(lambda v: v * 40 // 100))
    save(dim, "pad_dim.png")


def highlight_sprites():
    """One sprite per control, same size/position as pad_on.png, only that control lit."""
    box = holo_box()
    Wp, x0, y0 = A.pad_geometry(HOLO["cx"] * S, HOLO["cy"] * S, HOLO["s"] * S)
    X = lambda f: x0 + Wp * f
    Y = lambda f: y0 + Wp * f

    def circle(fx, fy, r):
        return lambda d: d.ellipse([X(fx) - Wp * r, Y(fy) - Wp * r, X(fx) + Wp * r, Y(fy) + Wp * r], fill=255)

    def ring(fx, fy, r, w):
        return lambda d: d.ellipse([X(fx) - Wp * r, Y(fy) - Wp * r, X(fx) + Wp * r, Y(fy) + Wp * r],
                                   outline=255, width=int(Wp * w))

    def rect(fx0, fy0, fx1, fy1):
        return lambda d: d.rounded_rectangle([X(fx0), Y(fy0), X(fx1), Y(fy1)], radius=Wp * 0.012, fill=255)

    k, dx, dy = 0.022, 0.355, 0.448
    shapes = {
        # SDL GameController button index -> shape
        0: circle(0.805, 0.31 + 0.068, 0.03), 1: circle(0.805 + 0.078, 0.31, 0.03),
        2: circle(0.805 - 0.078, 0.31, 0.03), 3: circle(0.805, 0.31 - 0.068, 0.03),
        4: circle(0.39, 0.315, 0.02), 6: circle(0.61, 0.315, 0.02),
        7: ring(0.19, 0.325, 0.088, 0.018), 8: ring(0.645, 0.448, 0.088, 0.018),
        9: rect(0.17, 0.03, 0.33, 0.1), 10: rect(0.67, 0.03, 0.83, 0.1),
        11: rect(dx - k, dy - 2.9 * k, dx + k, dy - k), 12: rect(dx - k, dy + k, dx + k, dy + 2.9 * k),
        13: rect(dx - 2.9 * k, dy - k, dx - k, dy + k), 14: rect(dx + k, dy - k, dx + 2.9 * k, dy + k),
    }
    for idx, shape in shapes.items():
        c = transparent()
        m = A.shape_mask(c.size, shape)
        A.soft(c, m, CYAN, 7 * S, 255)
        A.fill_mask(c, m, (205, 250, 255), 235)
        save(down(c, box), f"btn_{idx}.png")
    # movable stick dot (centred sprite)
    r = Wp / S * 0.042
    size = int(r * 2 + 30)
    c = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    m = A.shape_mask(c.size, lambda d: d.ellipse([(size / 2 - r) * S, (size / 2 - r) * S, (size / 2 + r) * S, (size / 2 + r) * S], fill=255))
    A.soft(c, m, CYAN, 6 * S, 255)
    A.fill_mask(c, m, (205, 250, 255), 235)
    save(down(c), "stick_dot.png")
    Wpx, x0p, y0p = Wp / S, x0 / S, y0 / S
    return {"left_stick": [x0p + Wpx * 0.19, y0p + Wpx * 0.325], "right_stick": [x0p + Wpx * 0.645, y0p + Wpx * 0.448],
            "stick_travel": Wpx * 0.04, "pad_origin": [box[0], box[1]]}


def card():
    m = 30
    box = (CARD_BOX[0] - m, CARD_BOX[1] - m, CARD_BOX[2] + m, CARD_BOX[3] + m)
    c = transparent()
    layer = Image.new("RGBA", c.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([v * S for v in CARD_BOX], radius=26 * S, fill=CARD + (215,))
    c.alpha_composite(layer)
    edge = A.shape_mask(c.size, lambda d: d.rounded_rectangle([v * S for v in CARD_BOX], radius=26 * S, outline=255, width=2 * S))
    A.soft(c, edge, CYAN, 10 * S, 90)
    A.fill_mask(c, edge, CYAN, 200)
    save(down(c, box), "card.png")
    return [box[0], box[1]]


def pills():
    def pill(w, h, color, filled, name):
        pad = 6
        c = Image.new("RGBA", ((w + 2 * pad) * S, (h + 2 * pad) * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        bx = [pad * S, pad * S, (pad + w) * S, (pad + h) * S]
        if filled:
            d.rounded_rectangle(bx, radius=h / 2 * S, fill=color + (255,))
        else:
            d.rounded_rectangle(bx, radius=h / 2 * S, fill=CARD + (235,), outline=color + (255,), width=2 * S)
        save(down(c), name)
    for w in PILL_WIDTHS:
        pill(w, 48, VIOLET, False, f"pill_v_{w}.png")
        pill(w, 56, MAGENTA, True, f"pill_m_{w}.png")
    for w in CHIP_WIDTHS:
        pill(w, 38, CYAN, True, f"chip_c_{w}.png")
        pill(w, 38, VIOLET, True, f"chip_v_{w}.png")
    for name, color in (("tile_c", CYAN), ("tile_m", MAGENTA), ("tile_v", VIOLET)):
        c = Image.new("RGBA", (242 * S, 92 * S), (0, 0, 0, 0))
        ImageDraw.Draw(c).rounded_rectangle([6 * S, 6 * S, 236 * S, 86 * S], radius=20 * S,
                                            fill=CARD + (235,), outline=color + (255,), width=2 * S)
        save(down(c), f"{name}.png")


def dots():
    for name, color in (("dot_green", GREEN), ("dot_cyan", CYAN), ("dot_red", RED)):
        c = Image.new("RGBA", (48 * S, 48 * S), (0, 0, 0, 0))
        m = A.shape_mask(c.size, lambda d: d.ellipse([13 * S, 13 * S, 35 * S, 35 * S], fill=255))
        A.soft(c, m, color, 5 * S, 200)
        A.fill_mask(c, m, color)
        save(down(c), f"{name}.png")


def wordmarks():
    for name, size in (("wordmark_small.png", 46), ("wordmark_big.png", 64)):
        c = Image.new("RGBA", (700 * S, 140 * S), (0, 0, 0, 0))
        A.wordmark(c, 20 * S, 70 * S, size * S, align="left")
        img = down(c)
        save(img.crop(img.getbbox()), name)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    backgrounds()
    hologram()
    layout = highlight_sprites()
    layout["card_origin"] = card()
    layout["card_box"] = list(CARD_BOX)
    layout["pill_widths"] = list(PILL_WIDTHS)
    layout["chip_widths"] = list(CHIP_WIDTHS)
    pills()
    dots()
    wordmarks()
    with open(os.path.join(OUT, "layout.json"), "w") as f:
        json.dump({k: ([round(x, 1) for x in v] if isinstance(v, list) else round(v, 1)) for k, v in layout.items()}, f, indent=1)
    print("UI assets written to", os.path.abspath(OUT))
