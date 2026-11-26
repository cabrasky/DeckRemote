#!/bin/bash
# gadget.sh up|up-xbox|bind|down|status — DeckRemote's root helper.
#   up       generic USB HID gamepad, exported over USB/IP right away (usbip-vudc backend)
#   up-xbox  Xbox 360 mode: loads dummy_hcd + raw_gadget, reserves the dummy port for usbip-host
#            (so neither the Deck nor Steam ever sees the pad) and hands /dev/raw-gadget to "deck".
#            The app then acts as a wired Xbox 360 controller (045e:028e) and calls "bind".
#   bind     Xbox mode: exports the pad with usbip-host + usbipd (bus id shown by "status")
#   down     removes everything (safe to call any time, any number of times)
#   status   off | waiting | connected   (Xbox mode adds the bus id: "waiting 3-1")
G=/sys/kernel/config/usb_gadget/deckremote
DESC=/home/deck/DeckRemote/report_desc.bin
LENF=/home/deck/DeckRemote/report_len
VUDC=usbip-vudc.0
MATCH=/sys/bus/usb/drivers/usbip-host/match_busid

dummy_busid() {  # bus id of the single port of dummy_hcd's root hub, e.g. "5-1"
  local hub
  hub=$(ls -d /sys/devices/platform/dummy_hcd.0/usb* 2>/dev/null | head -1)
  [ -n "$hub" ] && echo "${hub##*/usb}-1"
}

down() {
  pkill -x usbipd 2>/dev/null || true
  if [ -d "$G" ]; then
    echo "" > "$G/UDC" 2>/dev/null || true
    rm -f "$G/configs/c.1/hid.usb0"
    rmdir "$G/functions/hid.usb0" 2>/dev/null || true
    rmdir "$G/configs/c.1/strings/0x409" "$G/configs/c.1" "$G/strings/0x409" "$G" 2>/dev/null || true
  fi
  local busid
  busid=$(dummy_busid)
  if [ -n "$busid" ]; then
    /usr/bin/usbip unbind -b "$busid" >/dev/null 2>&1 || true
    [ -w "$MATCH" ] && echo "del $busid" > "$MATCH" 2>/dev/null || true
  fi
  # raw_gadget / dummy_hcd stay loaded (idle, nothing listens): unloading them while a
  # gadget is half torn down has crashed the kernel in testing.
  if [ -z "$busid" ]; then timeout 5 modprobe -r usbip-vudc 2>/dev/null || true; fi
}

case "$1" in
  up)
    down
    len=$(tr -dc 0-9 < "$LENF"); size=$(stat -c %s "$DESC")
    [ -n "$len" ] && [ "$len" -ge 1 ] && [ "$len" -le 64 ] && [ "$size" -le 1024 ] || { echo "bad descriptor"; exit 1; }
    modprobe libcomposite; modprobe usbip-vudc num=1; modprobe usb_f_hid
    mkdir -p "$G"; cd "$G" || exit 1
    echo 0x1d6b > idVendor; echo 0x0104 > idProduct; echo 0x0100 > bcdDevice; echo 0x0200 > bcdUSB
    mkdir -p strings/0x409
    echo "Steam Deck" > strings/0x409/manufacturer; echo "DeckRemote" > strings/0x409/product
    echo "DECKREMOTE01" > strings/0x409/serialnumber
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
  up-xbox)
    down
    modprobe usbip-host
    modprobe dummy_hcd
    modprobe raw_gadget
    busid=$(dummy_busid)
    [ -n "$busid" ] || { echo "no dummy_hcd bus"; exit 1; }
    # claim the port for usbip-host before the pad appears, so xpad / Steam never bind it
    echo "add $busid" > "$MATCH"
    for i in $(seq 1 20); do [ -e /dev/raw-gadget ] && break; sleep 0.1; done
    chown deck:deck /dev/raw-gadget
    echo "up-xbox $busid" ;;
  bind)
    busid=$(dummy_busid)
    [ -n "$busid" ] || { echo "not in xbox mode"; exit 1; }
    for i in $(seq 1 30); do [ -e "/sys/bus/usb/devices/$busid" ] && break; sleep 0.1; done
    [ -e "/sys/bus/usb/devices/$busid/usbip_status" ] || /usr/bin/usbip bind -b "$busid" >/dev/null 2>&1
    pgrep -x usbipd >/dev/null || systemd-run --unit=deckremote-usbipd --collect /usr/bin/usbipd >/dev/null
    echo "bound $busid" ;;
  down)
    down; echo "down" ;;
  status)
    # usbipd only runs while DeckRemote shares a pad, so without it everything is off
    pgrep -x usbipd >/dev/null || { echo off; exit 0; }
    f=/sys/devices/platform/$VUDC/usbip_status
    busid=$(dummy_busid)
    [ -n "$busid" ] && f=/sys/bus/usb/devices/$busid/usbip_status
    if [ -f "$f" ]; then
      case "$(cat "$f")" in 1) s=waiting;; 2) s=connected;; *) s="error $(cat "$f")";; esac
    elif [ -n "$busid" ]; then s=waiting
    else s=off; fi
    echo "$s${busid:+ $busid}" ;;
  *) echo "usage: gadget.sh up|up-xbox|bind|down|status"; exit 2 ;;
esac
