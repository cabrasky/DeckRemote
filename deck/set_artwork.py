#!/usr/bin/env python3
"""Copies DeckRemote's artwork into Steam's custom-artwork folder for the "DeckRemote" shortcut.

  python3 set_artwork.py <art_dir> [shortcut_name]

Finds the shortcut's app id in every ~/.local/share/Steam/userdata/<user>/config/shortcuts.vdf
and writes <id>p.png, <id>.png, <id>_hero.png, <id>_logo.png (+ logo position) into .../config/grid/.
Steam shows them after it restarts (e.g. when you go back to Game Mode).
"""
import glob
import json
import os
import shutil
import struct
import sys

STEAM = os.path.expanduser("~/.local/share/Steam/userdata")


def parse_vdf(buf, i=0):
    """Minimal binary-VDF reader -> (dict, next_index)."""
    out = {}
    while i < len(buf):
        t = buf[i]
        i += 1
        if t == 0x08:
            return out, i
        end = buf.index(b"\x00", i)
        key = buf[i:end].decode("utf-8", "replace")
        i = end + 1
        if t == 0x00:
            out[key], i = parse_vdf(buf, i)
        elif t == 0x01:
            end = buf.index(b"\x00", i)
            out[key] = buf[i:end].decode("utf-8", "replace")
            i = end + 1
        elif t == 0x02:
            out[key] = struct.unpack_from("<I", buf, i)[0]
            i += 4
        elif t == 0x07:
            out[key] = struct.unpack_from("<Q", buf, i)[0]
            i += 8
        else:
            raise ValueError(f"unknown VDF type {t:#x} at {i}")
    return out, i


def find_appids(name):
    found = []
    for vdf in glob.glob(os.path.join(STEAM, "*", "config", "shortcuts.vdf")):
        try:
            data, _ = parse_vdf(open(vdf, "rb").read())
        except (OSError, ValueError):
            continue
        for entry in data.get("shortcuts", {}).values():
            entry_name = entry.get("AppName") or entry.get("appname") or ""
            if entry_name == name and "appid" in entry:
                found.append((os.path.dirname(vdf), entry["appid"]))
    return found


def main():
    art = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else "DeckRemote"
    targets = find_appids(name)
    if not targets:
        print(f"No Steam shortcut named '{name}' found yet.")
        return 1
    for config_dir, appid in targets:
        grid = os.path.join(config_dir, "grid")
        os.makedirs(grid, exist_ok=True)
        for src, dst in (("capsule.png", f"{appid}p.png"), ("header.png", f"{appid}.png"),
                         ("hero.png", f"{appid}_hero.png"), ("logo.png", f"{appid}_logo.png")):
            shutil.copyfile(os.path.join(art, src), os.path.join(grid, dst))
        with open(os.path.join(grid, f"{appid}.json"), "w") as f:
            json.dump({"nVersion": 1, "logoPosition": {"pinnedPosition": "BottomLeft",
                                                       "nWidthPct": 38, "nHeightPct": 60}}, f)
        print(f"artwork installed for app id {appid} in {grid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
