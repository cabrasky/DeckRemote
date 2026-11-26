#!/bin/bash
# gadget.sh up|down|status — DeckRemote: virtual USB HID gamepad exported over USB/IP (usbip-vudc backend)
G=/sys/kernel/config/usb_gadget/deckremote
DESC=/home/deck/DeckRemote/report_desc.bin
LENF=/home/deck/DeckRemote/report_len
VUDC=usbip-vudc.0
down() {
  pkill -x usbipd 2>/dev/null || true
  if [ -d "$G" ]; then
    echo "" > "$G/UDC" 2>/dev/null || true
    rm -f "$G/configs/c.1/hid.usb0"
    rmdir "$G/configs/c.1/strings/0x409" "$G/configs/c.1" "$G/functions/hid.usb0" "$G/strings/0x409" "$G" 2>/dev/null || true
  fi
  modprobe -r usbip-vudc 2>/dev/null || true
}
case "$1" in
  up)
    down
    len=$(tr -dc 0-9 < "$LENF"); size=$(stat -c %s "$DESC")
    [ -n "$len" ] && [ "$len" -ge 1 ] && [ "$len" -le 64 ] && [ "$size" -le 1024 ] || { echo "bad descriptor"; exit 1; }
    modprobe libcomposite; modprobe usb_f_hid; modprobe usbip-vudc num=1
    mkdir -p "$G"; cd "$G"
    echo 0x1d6b > idVendor; echo 0x0104 > idProduct; echo 0x0100 > bcdDevice; echo 0x0200 > bcdUSB
    mkdir -p strings/0x409
    echo "Steam Deck" > strings/0x409/manufacturer; echo "DeckRemote" > strings/0x409/product; echo "DECKREMOTE01" > strings/0x409/serialnumber
    mkdir -p functions/hid.usb0
    echo 0 > functions/hid.usb0/protocol; echo 0 > functions/hid.usb0/subclass
    echo "$len" > functions/hid.usb0/report_length
    cat "$DESC" > functions/hid.usb0/report_desc
    mkdir -p configs/c.1/strings/0x409
    echo "DeckRemote" > configs/c.1/strings/0x409/configuration; echo 100 > configs/c.1/MaxPower
    ln -sf "$G/functions/hid.usb0" configs/c.1/
    echo "$VUDC" > UDC
    systemd-run --unit=deckremote-usbipd --collect /usr/bin/usbipd --device >/dev/null
    for i in $(seq 1 20); do [ -e /dev/hidg0 ] && break; sleep 0.1; done
    chown deck:deck /dev/hidg0
    echo "up" ;;
  down)
    down; echo "down" ;;
  status)
    f=/sys/devices/platform/$VUDC/usbip_status
    if [ -f "$f" ]; then
      case "$(cat "$f")" in 1) echo waiting;; 2) echo connected;; *) echo "error $(cat "$f")";; esac
    else echo off; fi ;;
  *) echo "usage: gadget.sh up|down|status"; exit 2 ;;
esac
