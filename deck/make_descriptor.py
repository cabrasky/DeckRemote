#!/usr/bin/env python3
"""Writes the HID report descriptor of the virtual gamepad (report_desc.bin + report_len).

Report layout (13 bytes, no report ID):
  uint16  buttons   1=A 2=B 3=X 4=Y 5=LB 6=RB 7=View 8=Menu 9=LS 10=RS (11-16 unused)
  uint8   hat       low nibble 0-7 (N, NE, E, ... NW), 8 = centered; high nibble padding
  int16   X, Y      left stick   (-32767..32767)
  int16   Rx, Ry    right stick  (-32767..32767)
  uint8   Z, Rz     left / right trigger (0..255)
"""
import os
import sys

DESCRIPTOR = bytes.fromhex(
    "05 01 09 05 a1 01"                                                # Generic Desktop, Game Pad
    " 05 09 19 01 29 10 15 00 25 01 75 01 95 10 81 02"                  # 16 buttons
    " 05 01 09 39 15 00 25 07 35 00 46 3b 01 65 14 75 04 95 01 81 42"   # hat switch
    " 65 00 35 00 45 00 75 04 95 01 81 03"                              # 4-bit padding
    " 09 30 09 31 09 33 09 34 16 01 80 26 ff 7f 75 10 95 04 81 02"      # X Y Rx Ry
    " 09 32 09 35 15 00 26 ff 00 75 08 95 02 81 02"                     # Z Rz (triggers)
    " c0".replace(" ", ""))
REPORT_LEN = 13

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out, "report_desc.bin"), "wb") as f:
        f.write(DESCRIPTOR)
    with open(os.path.join(out, "report_len"), "w") as f:
        f.write(f"{REPORT_LEN}\n")
    print(f"descriptor: {len(DESCRIPTOR)} bytes, report: {REPORT_LEN} bytes -> {out}")
