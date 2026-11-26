#!/usr/bin/env python3
"""Generates DeckRemote's Steam library artwork (needs Pillow).

  python tools/make_art.py [output_dir]      (default: deck/art)

Visual identity: the Steam Deck projects a holographic gamepad (cyan/magenta light) above a
perspective grid floor. Files (installed by deck/set_artwork.py with Steam's artwork names):
  capsule.png  600x900    library grid (portrait)   -> <appid>p.png
  header.png   920x430    wide capsule / "recent"    -> <appid>.png
  hero.png     1920x620   game page background       -> <appid>_hero.png
  logo.png     1280x420   transparent logo over hero -> <appid>_logo.png
  icon.png     256x256    shortcut icon

Everything is drawn at SS x resolution and downsampled for clean anti-aliasing.
"""
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SS = 3  # supersampling factor

CYAN = (49, 232, 255)
MAGENTA = (255, 79, 216)
VIOLET = (124, 77, 255)
WHITE = (246, 248, 252)
TEXT_DIM = (176, 168, 214)

FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/TTF", "/usr/share/fonts/noto",
             "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts"]
BLACK_FONT = ["seguibl.ttf", "NotoSans-Black.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"]
SEMI_FONT = ["seguisb.ttf", "NotoSans-SemiBold.ttf", "segoeui.ttf", "DejaVuSans.ttf"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, int(size))
    return ImageFont.load_default(int(size))


# ------------------------------------------------------------------ helpers
def lerp(a, b, k):
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def gradient(w, h, stops, horizontal=False):
    """Multi-stop gradient image (RGBA). stops = [(pos 0..1, rgb), ...]."""
    n = 512
    strip = Image.new("RGBA", (n, 1) if horizontal else (1, n))
    for i in range(n):
        k = i / (n - 1)
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= k <= p1:
                col = lerp(c0, c1, (k - p0) / max(1e-6, p1 - p0))
                break
        else:
            col = stops[-1][1]
        strip.putpixel((i, 0) if horizontal else (0, i), col + (255,))
    return strip.resize((max(1, int(w)), max(1, int(h))), Image.BILINEAR)


def placed(size, img, xy):
    full = Image.new("RGBA", size, (0, 0, 0, 0))
    full.paste(img, (int(xy[0]), int(xy[1])))
    return full


def shape_mask(size, draw_fn):
    m = Image.new("L", (int(size[0]), int(size[1])), 0)
    draw_fn(ImageDraw.Draw(m))
    return m


def fill_mask(canvas, mask, fill, opacity=255):
    src = fill if isinstance(fill, Image.Image) else Image.new("RGBA", canvas.size, fill + (255,))
    if opacity != 255:
        mask = mask.point(lambda v: v * opacity // 255)
    canvas.alpha_composite(Image.composite(src, Image.new("RGBA", canvas.size, (0, 0, 0, 0)), mask))


def soft(canvas, mask, color, blur, opacity, offset=(0, 0)):
    """Blurred coloured copy of mask (glow when colour is bright, shadow when black)."""
    g = mask.point(lambda v: v * opacity // 255).filter(ImageFilter.GaussianBlur(blur))
    if offset != (0, 0):
        g = ImageChops.offset(g, int(offset[0]), int(offset[1]))
    layer = Image.new("RGBA", canvas.size, color + (0,))
    layer.putalpha(g)
    canvas.alpha_composite(layer)


# ------------------------------------------------------------------ background
def background(w, h, horizon=0.68, vx=0.5, seed=7):
    hy = h * horizon
    c = gradient(w, h, [(0, (7, 6, 20)), (horizon * 0.85, (27, 14, 62)), (horizon, (40, 18, 78)),
                        (min(1, horizon + 0.02), (10, 7, 26)), (1, (4, 3, 10))])
    # horizon glow
    for col, rx, ry, op in ((MAGENTA, 0.55, 0.10, 110), (CYAN, 0.35, 0.05, 90), (VIOLET, 0.8, 0.25, 70)):
        m = shape_mask((w, h), lambda d: d.ellipse([w * vx - w * rx, hy - h * ry, w * vx + w * rx, hy + h * ry], fill=255))
        soft(c, m, col, min(w, h) * 0.12, op)
    # stars
    rnd = random.Random(seed)
    stars = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stars)
    for _ in range(int(w * h / (9000 * SS * SS))):
        x, y = rnd.uniform(0, w), rnd.uniform(0, hy * 0.95)
        r = rnd.choice((0.6, 0.8, 1.0, 1.4)) * SS
        a = rnd.randint(40, 170)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(220, 225, 255, a))
    c.alpha_composite(stars)
    # perspective grid floor
    grid = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(grid)
    lw = max(1, int(1.2 * SS))
    rows = 14
    for i in range(1, rows + 1):
        k = (i / rows) ** 2.1
        y = hy + (h - hy) * k
        gd.line([(0, y), (w, y)], fill=255, width=lw)
    cols = 34
    vxp = w * vx
    for j in range(-cols, cols + 1):
        xb = vxp + j * (w / cols) * 1.9
        gd.line([(vxp + (xb - vxp) * 0.02, hy), (xb, h)], fill=255, width=lw)
    fade = gradient(1, h, [(0, (0, 0, 0)), (horizon, (30, 30, 30)), (min(1, horizon + 0.05), (130, 130, 130)), (1, (255, 255, 255))])
    fade = fade.convert("L").resize((w, h))
    grid = ImageChops.multiply(grid, fade)
    soft(c, grid, MAGENTA, 4 * SS, 255)
    fill_mask(c, grid, gradient(w, h, [(0, MAGENTA), (0.5, VIOLET), (1, CYAN)], horizontal=True), 235)
    # horizon line
    hl = shape_mask((w, h), lambda d: d.line([(0, hy), (w, hy)], fill=255, width=max(1, int(1.5 * SS))))
    soft(c, hl, MAGENTA, 6 * SS, 255)
    fill_mask(c, hl, (255, 170, 240), 200)
    # vignette
    v = shape_mask((w, h), lambda d: d.rectangle([0, 0, w, h], fill=255))
    inner = shape_mask((w, h), lambda d: d.rounded_rectangle([w * 0.05, h * 0.05, w * 0.95, h * 0.95],
                                                               radius=min(w, h) * 0.3, fill=255))
    v = ImageChops.subtract(v, inner).filter(ImageFilter.GaussianBlur(min(w, h) * 0.1))
    vig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    vig.putalpha(v.point(lambda p: p * 170 // 255))
    c.alpha_composite(vig)
    return c


# ------------------------------------------------------------------ the Deck
DECK_RATIO = 2.78  # width / height of the real handheld (front view)


def deck_body_mask(size, cx, cy, s):
    W, H = s * DECK_RATIO, s
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    top_rounded = shape_mask(size, lambda d: d.rounded_rectangle([x0, y0, x1, y1], radius=H * 0.24, fill=255))
    bottom_rounded = shape_mask(size, lambda d: d.rounded_rectangle([x0, y0 - H * 3, x1, y1], radius=H * 0.38, fill=255))
    return ImageChops.darker(top_rounded, bottom_rounded)


def deck(c, cx, cy, s):
    """Steam-Deck-style handheld (front view) centred on cx,cy; s = body height.

    Proportions follow the real device: a 16:10 screen that fills almost the whole height,
    and on each side D-pad/ABXY (outer, top), thumbstick (inner, top), square trackpad,
    STEAM / ⋯ button and speaker grille. Returns the display box.
    """
    W, H = s * DECK_RATIO, s
    x0, y0, x1, y1 = cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2
    X = lambda f: x0 + W * f
    Y = lambda f: y0 + H * f
    size = c.size
    body = deck_body_mask(size, cx, cy, s)
    soft(c, body, (0, 0, 0), H * 0.12, 210, (0, H * 0.12))
    fill_mask(c, body, placed(size, gradient(W, H, [(0, (60, 62, 78)), (0.45, (33, 34, 45)), (1, (17, 17, 25))]), (x0, y0)))
    rim = ImageChops.subtract(body, ImageChops.offset(body, 0, int(H * 0.018)))
    fill_mask(c, rim, (160, 160, 200), 190)
    under = ImageChops.subtract(body, ImageChops.offset(body, 0, -int(H * 0.018)))
    fill_mask(c, under, MAGENTA, 130)  # magenta rim light from the floor
    d = ImageDraw.Draw(c)
    line = (56, 58, 74, 255)
    lw = max(1, int(H * 0.008))
    # grip seams
    for side in (0, 1):
        fx = (lambda f: f) if side == 0 else (lambda f: 1 - f)
        d.line([(X(fx(0.012)), Y(0.55)), (X(fx(0.06)), Y(0.78)), (X(fx(0.165)), Y(0.995))], fill=line, width=lw, joint="curve")
    # screen glass and display (16:10)
    gx0, gx1, gy0, gy1 = X(0.19), X(0.81), Y(0.035), Y(0.935)
    d.rounded_rectangle([gx0, gy0, gx1, gy1], radius=H * 0.035, fill=(6, 6, 10, 255))
    bez = H * 0.05
    disp = (gx0 + bez, gy0 + bez, gx1 - bez, gy1 - bez)
    dw, dh = disp[2] - disp[0], disp[3] - disp[1]
    dm = shape_mask(size, lambda dd: dd.rectangle(disp, fill=255))
    soft(c, dm, CYAN, H * 0.1, 120)
    fill_mask(c, dm, placed(size, gradient(dw, dh, [(0, (46, 205, 255)), (0.55, (22, 74, 156)), (1, (14, 18, 50))]),
                            disp[:2]))
    glare = shape_mask(size, lambda dd: dd.polygon([(disp[0], disp[1]), (disp[0] + dw * 0.42, disp[1]),
                                                    (disp[0] + dw * 0.18, disp[3]), (disp[0], disp[3])], fill=255))
    fill_mask(c, ImageChops.multiply(glare, dm), (255, 255, 255), 18)
    d = ImageDraw.Draw(c)
    dark = (11, 11, 16, 255)
    grey = (96, 98, 120, 255)
    for side in (0, 1):
        fx = (lambda f: f) if side == 0 else (lambda f: 1 - f)
        # thumbstick
        sx, sy, r = X(fx(0.15)), Y(0.19), W * 0.04
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=dark)
        cr = r * 0.74
        cap = shape_mask(size, lambda dd: dd.ellipse([sx - cr, sy - cr, sx + cr, sy + cr], fill=255))
        fill_mask(c, cap, placed(size, gradient(2 * cr, 2 * cr, [(0, (96, 98, 118)), (1, (38, 39, 50))]), (sx - cr, sy - cr)))
        d = ImageDraw.Draw(c)
        # trackpad
        tx, ty, tw, th = X(fx(0.128)), Y(0.45), W * 0.115, H * 0.27
        d.rounded_rectangle([tx - tw / 2, ty - th / 2, tx + tw / 2, ty + th / 2], radius=W * 0.012,
                            fill=(27, 27, 37, 255), outline=(64, 64, 84, 255), width=lw)
        # STEAM / ⋯ button and speaker grille
        bx, by = X(fx(0.142)), Y(0.665)
        d.rounded_rectangle([bx - W * 0.03, by - H * 0.03, bx + W * 0.03, by + H * 0.03], radius=H * 0.03, fill=(24, 24, 32, 255),
                            outline=(70, 70, 90, 255), width=lw)
        for row in range(3):
            for col in range(5 - row % 2):
                gx = bx + (col - (4 - row % 2) / 2) * W * 0.008
                gy = Y(0.77) + row * H * 0.03
                rr = W * 0.0022
                d.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], fill=(10, 10, 14, 255))
        # View / Menu buttons on the top edge
        mx = X(fx(0.115))
        d.rounded_rectangle([mx - W * 0.012, Y(0.035), mx + W * 0.012, Y(0.075)], radius=H * 0.02, fill=grey)
    # D-pad (left, outer)
    lx, ly, k = X(0.066), Y(0.17), W * 0.0125
    for box in ([lx - k * 2.9, ly - k, lx + k * 2.9, ly + k], [lx - k, ly - k * 2.9, lx + k, ly + k * 2.9]):
        d.rounded_rectangle(box, radius=k * 0.35, fill=grey)
    # ABXY (right, outer)
    rx, ry, k = X(0.934), Y(0.15), W * 0.0125
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        r = k * 1.15
        d.ellipse([rx + dx * k * 2.4 - r, ry + dy * k * 2.4 - r, rx + dx * k * 2.4 + r, ry + dy * k * 2.4 + r], fill=grey)
    return disp


# ------------------------------------------------------------------ hologram
def catmull_rom_closed(pts, samples=24):
    """Smooth closed curve through pts (Catmull-Rom)."""
    out, n = [], len(pts)
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
                             for a, b, c, d in zip(p0, p1, p2, p3)))
    return out


# Right half of a generic gamepad outline, clockwise from the top centre to the bottom centre.
# Units: fraction of the pad width (x 0..1, y from the top). Measured from front-view
# references (classic dual-stick layout) with tools/shape_compare.py.
PAD_HALF = [(0.50, 0.110), (0.60, 0.107), (0.655, 0.090), (0.705, 0.066), (0.775, 0.056),
            (0.845, 0.076), (0.895, 0.118), (0.930, 0.185), (0.960, 0.275), (0.985, 0.365),
            (0.999, 0.450), (0.994, 0.515), (0.977, 0.565), (0.950, 0.602), (0.915, 0.626),
            (0.870, 0.636), (0.820, 0.626), (0.770, 0.600), (0.715, 0.572), (0.655, 0.556),
            (0.590, 0.545), (0.500, 0.537)]
PAD_TOP, PAD_BOTTOM = 0.056, 0.636


def pad_geometry(cx, cy, s):
    """Width W and origin of the pad so that its body is centred on cx,cy. s ~ 0.57 x width."""
    W = s * 1.75
    x0 = cx - W / 2
    y0 = cy - W * (PAD_TOP + PAD_BOTTOM) / 2
    return W, x0, y0


def pad_outline(cx, cy, s):
    W, x0, y0 = pad_geometry(cx, cy, s)
    left = [(1 - x, y) for x, y in reversed(PAD_HALF[1:-1])]
    return [(x0 + W * x, y0 + W * y) for x, y in catmull_rom_closed(PAD_HALF + left)]


def pad_body_mask(size, cx, cy, s, bumpers=True):
    W, x0, y0 = pad_geometry(cx, cy, s)
    m = shape_mask(size, lambda d: d.polygon(pad_outline(cx, cy, s), fill=255))
    if bumpers:
        for f0, f1 in ((0.17, 0.33), (0.67, 0.83)):
            m = ImageChops.lighter(m, shape_mask(size, lambda d: d.rounded_rectangle(
                [x0 + W * f0, y0 + W * 0.03, x0 + W * f1, y0 + W * 0.1], radius=W * 0.03, fill=255)))
    return m


def pad_details(d, cx, cy, s, width):
    W, x0, y0 = pad_geometry(cx, cy, s)
    X = lambda f: x0 + W * f
    Y = lambda f: y0 + W * f
    ring = lambda fx, fy, r, **kw: d.ellipse([X(fx) - W * r, Y(fy) - W * r, X(fx) + W * r, Y(fy) + W * r], **kw)
    # left stick (upper left) and right stick (lower right): well + cap
    for fx, fy in ((0.19, 0.325), (0.645, 0.448)):
        ring(fx, fy, 0.088, outline=255, width=width)
        ring(fx, fy, 0.056, outline=255, width=width)
    # D-pad (lower left) in its well
    ring(0.355, 0.448, 0.088, outline=255, width=width)
    k, dx, dy = W * 0.022, X(0.355), Y(0.448)
    d.polygon([(dx - k, dy - 2.9 * k), (dx + k, dy - 2.9 * k), (dx + k, dy - k), (dx + 2.9 * k, dy - k),
               (dx + 2.9 * k, dy + k), (dx + k, dy + k), (dx + k, dy + 2.9 * k), (dx - k, dy + 2.9 * k),
               (dx - k, dy + k), (dx - 2.9 * k, dy + k), (dx - 2.9 * k, dy - k), (dx - k, dy - k)],
              outline=255, width=width)
    # face buttons (upper right)
    for ddx, ddy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        ring(0.805 + ddx * 0.078, 0.31 + ddy * 0.068, 0.034, outline=255, width=width)
    # guide button and the two small centre buttons
    ring(0.5, 0.3, 0.055, outline=255, width=width)
    ring(0.5, 0.3, 0.022, fill=255)
    for fx in (0.39, 0.61):
        ring(fx, 0.315, 0.022, outline=255, width=width)


def hologram(c, cx, cy, s):
    """Holographic gamepad: translucent body, scanlines, glowing chromatic edges."""
    lw, lh = int(s * 2.3), int(s * 1.7)
    ox, oy = cx - lw / 2, cy - lh / 2
    lc = (lw / 2, lh / 2)
    layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    body = pad_body_mask((lw, lh), lc[0], lc[1], s)
    stroke = max(3, int(s * 0.028)) | 1
    edge = ImageChops.subtract(body, body.filter(ImageFilter.MinFilter(stroke)))
    det = shape_mask((lw, lh), lambda d: pad_details(d, lc[0], lc[1], s, max(2, int(s * 0.016))))
    lines = ImageChops.lighter(edge, det)
    # translucent body + scanlines
    fill_mask(layer, body, gradient(lw, lh, [(0, CYAN), (1, VIOLET)]), 55)
    scan = Image.new("L", (lw, lh), 0)
    sd = ImageDraw.Draw(scan)
    step = max(3, int(s * 0.03))
    for y in range(0, lh, step):
        sd.line([(0, y), (lw, y)], fill=255, width=max(1, step // 3))
    fill_mask(layer, ImageChops.multiply(scan, body), CYAN, 70)
    # glow + chromatic aberration edges
    soft(layer, lines, CYAN, s * 0.07, 255)
    soft(layer, lines, MAGENTA, s * 0.16, 130)
    ab = max(2, int(s * 0.012))
    fill_mask(layer, ImageChops.offset(lines, -ab, 0), MAGENTA, 210)
    fill_mask(layer, ImageChops.offset(lines, ab, 0), CYAN, 210)
    fill_mask(layer, lines, (225, 252, 255), 255)
    c.alpha_composite(layer, (int(ox), int(oy)))
    return ox, oy, lw, lh


def beam(c, base, top_y, top_half, cx, seed=3):
    """Light cone from the Deck's display (base box) up to top_y."""
    size = c.size
    x0, y0, x1, _ = base
    poly = [(x0 + (x1 - x0) * 0.08, y0), (x1 - (x1 - x0) * 0.08, y0), (cx + top_half, top_y), (cx - top_half, top_y)]
    m = shape_mask(size, lambda d: d.polygon(poly, fill=255))
    fade = gradient(1, size[1], [(0, (0, 0, 0)), (top_y / size[1], (40, 40, 40)),
                                 (min(1, (top_y + (y0 - top_y) * 0.4) / size[1]), (130, 130, 130)),
                                 (y0 / size[1], (255, 255, 255)), (1, (255, 255, 255))]).convert("L").resize(size)
    m = ImageChops.multiply(m, fade).filter(ImageFilter.GaussianBlur((x1 - x0) * 0.03))
    soft(c, m, CYAN, (x1 - x0) * 0.12, 120)
    grad = placed(size, gradient(1, y0 - top_y, [(0, VIOLET), (0.6, CYAN), (1, (190, 250, 255))])
                  .resize((int(x1 - x0 + 2 * top_half), int(y0 - top_y))), (min(x0, cx - top_half), top_y))
    fill_mask(c, m, grad, 150)
    # bright core streaks
    core = shape_mask(size, lambda d: d.polygon([(cx - (x1 - x0) * 0.18, y0), (cx + (x1 - x0) * 0.18, y0),
                                                  (cx + top_half * 0.35, top_y), (cx - top_half * 0.35, top_y)], fill=255))
    core = ImageChops.multiply(core, fade).filter(ImageFilter.GaussianBlur((x1 - x0) * 0.05))
    fill_mask(c, core, (210, 250, 255), 70)
    rnd = random.Random(seed)
    p = Image.new("L", size, 0)
    pd = ImageDraw.Draw(p)
    for _ in range(26):
        t = rnd.random()
        y = y0 - (y0 - top_y) * t
        half = ((x1 - x0) / 2) * (1 - t) + top_half * t
        x = cx + rnd.uniform(-half * 0.85, half * 0.85)
        r = rnd.uniform(0.6, 1.6) * SS * (1 + (y0 - top_y) / 900)
        pd.ellipse([x - r, y - r, x + r, y + r], fill=rnd.randint(120, 255))
    soft(c, p, CYAN, 2 * SS, 255)
    fill_mask(c, p, (230, 252, 255))


# ------------------------------------------------------------------ text
def wordmark(c, cx, cy, size, align="center"):
    f = font(BLACK_FONT, size)
    d = ImageDraw.Draw(c)
    a, b = "Deck", "Remote"
    wa, wb = d.textlength(a, font=f), d.textlength(b, font=f)
    x = cx - (wa + wb) / 2 if align == "center" else cx
    full = shape_mask(c.size, lambda dd: dd.text((x, cy), a + b, font=f, fill=255, anchor="lm"))
    rem = shape_mask(c.size, lambda dd: dd.text((x + wa, cy), b, font=f, fill=255, anchor="lm"))
    deck_m = ImageChops.subtract(full, rem)
    soft(c, full, (0, 0, 0), size * 0.07, 220, (0, size * 0.05))
    soft(c, rem, MAGENTA, size * 0.16, 140)
    soft(c, rem, CYAN, size * 0.06, 150)
    ab = max(2, int(size * 0.02))
    fill_mask(c, ImageChops.offset(rem, -ab, 0), MAGENTA, 200)
    fill_mask(c, rem, placed(c.size, gradient(wb, size * 1.2, [(0, CYAN), (1, (150, 120, 255))], horizontal=True),
                             (x + wa, cy - size * 0.6)))
    fill_mask(c, deck_m, placed(c.size, gradient(wa, size * 1.2, [(0, (255, 255, 255)), (1, (205, 210, 235))]),
                                (x, cy - size * 0.6)))
    return wa + wb


def tagline(c, cx, cy, size, text):
    ImageDraw.Draw(c).text((cx, cy), text, font=font(SEMI_FONT, size), fill=TEXT_DIM + (255,), anchor="mm")


def finish(c, w, h, path, keep_alpha=False):
    img = c.resize((w, h), Image.LANCZOS)
    if not keep_alpha:
        img = img.convert("RGB")
    img.save(path, optimize=True)


# ------------------------------------------------------------------ assets
def scene(c, cx, deck_y, deck_h, holo_y, holo_s):
    disp = deck(c, cx, deck_y, deck_h)
    beam(c, disp, holo_y + holo_s * 0.25, holo_s * 0.95, cx)
    hologram(c, cx, holo_y, holo_s)


def capsule(out):
    w, h, S = 600, 900, SS
    c = background(w * S, h * S, horizon=0.72)
    scene(c, w / 2 * S, 700 * S, 150 * S, 410 * S, 215 * S)
    wordmark(c, w / 2 * S, 112 * S, 88 * S)
    tagline(c, w / 2 * S, 176 * S, 25 * S, "Steam Deck  →  PC controller")
    finish(c, w, h, os.path.join(out, "capsule.png"))


def header(out):
    w, h, S = 920, 430, SS
    c = background(w * S, h * S, horizon=0.74, vx=0.3)
    scene(c, 255 * S, 345 * S, 100 * S, 150 * S, 150 * S)
    wordmark(c, 655 * S, 195 * S, 78 * S)
    tagline(c, 655 * S, 255 * S, 22 * S, "Your Steam Deck, your PC controller")
    finish(c, w, h, os.path.join(out, "header.png"))


def hero(out):
    w, h, S = 1920, 620, SS
    # Steam shows roughly the top 70% of the hero and draws its status bar over the top,
    # so the scene sits in the band y = 100..430.
    c = background(w * S, h * S, horizon=0.64, vx=0.68)
    scene(c, 1330 * S, 395 * S, 105 * S, 240 * S, 150 * S)
    finish(c, w, h, os.path.join(out, "hero.png"))


def logo(out):
    w, h, S = 1280, 420, SS
    c = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    wordmark(c, w / 2 * S, 175 * S, 190 * S)
    tagline(c, w / 2 * S, 330 * S, 46 * S, "Your Steam Deck is now your PC controller")
    finish(c, w, h, os.path.join(out, "logo.png"), keep_alpha=True)


def icon(out):
    s, S = 256, SS
    size = (s * S, s * S)
    bg = background(*size, horizon=0.74)
    mask = shape_mask(size, lambda d: d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=58 * S, fill=255))
    c = Image.new("RGBA", size, (0, 0, 0, 0))
    c.paste(bg, (0, 0), mask)
    base = (88 * S, 200 * S, 168 * S, 206 * S)
    bar = shape_mask(size, lambda d: d.rounded_rectangle(base, radius=3 * S, fill=255))
    soft(c, bar, CYAN, 8 * S, 255)
    fill_mask(c, bar, (200, 250, 255))
    beam(c, base, 120 * S, 70 * S, s / 2 * S)
    hologram(c, s / 2 * S, 112 * S, 112 * S)
    c.putalpha(ImageChops.multiply(c.getchannel("A"), mask))
    finish(c, s, s, os.path.join(out, "icon.png"), keep_alpha=True)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "deck", "art")
    os.makedirs(out, exist_ok=True)
    for fn in (capsule, header, hero, logo, icon):
        fn(out)
    print("artwork written to", os.path.abspath(out))
