#!/usr/bin/env python3
"""Shape lab: compares a drawn silhouette against a reference picture.

  python tools/shape_compare.py pad  <reference.png> <out_dir>
  python tools/shape_compare.py deck <reference.png> <out_dir>

* Extracts the reference silhouette (flood-fills the background, outlines act as walls).
* Renders our silhouette from tools/make_art.py, scaled to the same bounding box.
* Prints IoU (1.0 = identical) and writes overlay.png:
    white = both, red = only reference, cyan = only ours.
References are not shipped with the repo; use any front-view photo or diagram.
"""
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_art  # noqa: E402

N = 800  # working resolution


def bbox_crop(mask):
    box = mask.getbbox()
    return mask.crop(box), box


def reference_silhouette(path, wall=170, mode="outline", top_cut=0.0):
    """Silhouette of the object in a reference picture (white on black, cropped to its bbox).

    mode "outline": light object drawn with dark outlines on a light background (diagrams).
    mode "dark":    dark object on a lighter background (photos).
    top_cut: fraction of the width removed from the top (e.g. to drop triggers).
    """
    img = Image.open(path).convert("L")
    # drop the dark letterbox bars of browser screenshots
    rows = [y for y in range(img.height) if sum(img.crop((0, y, img.width, y + 1)).getdata()) / img.width > 40]
    img = img.crop((0, rows[0], img.width, rows[-1] + 1))
    k = 7 if mode == "outline" else 3
    walls = img.point(lambda v: 0 if v < wall else 255).filter(ImageFilter.MinFilter(k))
    fill = walls.convert("L")
    for corner in ((1, 1), (fill.width - 2, 1), (1, fill.height - 2), (fill.width - 2, fill.height - 2)):
        if fill.getpixel(corner) == 255:
            ImageDraw.floodfill(fill, corner, 128)
    sil = fill.point(lambda v: 0 if v == 128 else 255).filter(ImageFilter.MaxFilter(k))
    sil = bbox_crop(sil)[0]
    if top_cut:
        sil = bbox_crop(sil.crop((0, int(sil.width * top_cut), sil.width, sil.height)))[0]
    return sil


def our_silhouette(kind):
    size = (N * 3, N * 3)
    if kind == "pad":
        m = make_art.pad_body_mask(size, size[0] / 2, size[1] / 2, N * 0.6, bumpers=False)
    else:
        cx, cy, s = size[0] / 2, size[1] / 2, N * 0.35
        m = make_art.deck_body_mask(size, cx, cy, s)
    return bbox_crop(m)[0]


def compare(ref, ours, out):
    w, h = N, int(N * ref.height / ref.width)
    a = ref.resize((w, h)).point(lambda v: 255 if v > 127 else 0)
    b = ours.resize((w, h)).point(lambda v: 255 if v > 127 else 0)
    inter = ImageChops.multiply(a, b)
    union = ImageChops.lighter(a, b)
    iou = sum(1 for v in inter.getdata() if v) / max(1, sum(1 for v in union.getdata() if v))
    ov = Image.new("RGB", (w, h), (20, 20, 26))
    only_ref = ImageChops.subtract(a, b)
    only_ours = ImageChops.subtract(b, a)
    ov.paste((235, 235, 235), (0, 0), inter)
    ov.paste((255, 70, 70), (0, 0), only_ref)
    ov.paste((40, 220, 255), (0, 0), only_ours)
    ov.save(os.path.join(out, "overlay.png"))
    a.save(os.path.join(out, "reference_mask.png"))
    print(f"IoU = {iou:.3f}   (aspect ref {ref.width / ref.height:.2f}, ours {ours.width / ours.height:.2f})")
    return iou


if __name__ == "__main__":
    kind, ref_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    if kind == "pad":
        # cut the trigger stubs that stick out above the body in the reference diagram
        ref = reference_silhouette(ref_path, mode="outline", wall=170, top_cut=0.056)
        ours = our_silhouette(kind)
        ours = bbox_crop(ours.crop((0, int(ours.width * 0.0), ours.width, ours.height)))[0]
    else:
        ref = reference_silhouette(ref_path, mode="dark", wall=60)
        ours = our_silhouette(kind)
    compare(ref, ours, out)
