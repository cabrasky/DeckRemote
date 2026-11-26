#!/bin/bash
# DeckRemote installer for the Steam Deck (SteamOS 3.x).
# Run it from Konsole in Desktop Mode, as the "deck" user (no sudo):   bash deck/install.sh
# It asks for your sudo password once. Nothing is started at boot.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
APP="/home/deck/DeckRemote"
say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*"; exit 1; }

[ "$(id -un)" = "deck" ] || die "run this as the 'deck' user, without sudo."
command -v usbipd >/dev/null && modinfo usbip-vudc >/dev/null 2>&1 \
  || die "this SteamOS has no usbipd / usbip-vudc kernel module."
if passwd -S deck 2>/dev/null | grep -q " NP "; then
  die "the 'deck' user has no password yet. Set one with:  passwd   — then run this again."
fi

say "Copying DeckRemote to $APP"
mkdir -p "$APP/art"
install -m 755 "$SRC/deckremote.py" "$APP/deckremote.py"
install -m 644 "$SRC/set_artwork.py" "$APP/set_artwork.py"
install -m 644 "$SRC/xinput.py" "$APP/xinput.py"
cp "$SRC"/art/*.png "$APP/art/"
python3 "$SRC/make_descriptor.py" "$APP" >/dev/null
printf '#!/bin/bash\nexec /usr/bin/python3 %s/deckremote.py "$@"\n' "$APP" > "$APP/deckremote.sh"
chmod 755 "$APP/deckremote.sh"
cat > "$APP/DeckRemote.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=DeckRemote
Comment=Use your Steam Deck as a controller for your PC
Exec=$APP/deckremote.sh
Icon=$APP/art/icon.png
Terminal=false
Categories=Game;Utility;
EOF
chmod 755 "$APP/DeckRemote.desktop"

say "Installing the system helper (asks for your sudo password)"
sudo bash -s "$SRC/gadget.sh" <<'ROOT'
set -e
mkdir -p /etc/deckremote
install -m 755 -o root -g root "$1" /etc/deckremote/gadget.sh
tmp=$(mktemp)
echo 'deck ALL=(root) NOPASSWD: /etc/deckremote/gadget.sh up, /etc/deckremote/gadget.sh up-xbox, /etc/deckremote/gadget.sh bind, /etc/deckremote/gadget.sh down, /etc/deckremote/gadget.sh status' > "$tmp"
visudo -cf "$tmp" >/dev/null
# "zz-" so it is read after SteamOS's own "wheel" rule (sudo applies the last matching rule)
install -m 440 -o root -g root "$tmp" /etc/sudoers.d/zz-deckremote
rm -f "$tmp"
visudo -c >/dev/null
# clean up the old "Mando PC" prototype if present
if [ -x /etc/mandopc/gadget.sh ]; then /etc/mandopc/gadget.sh down >/dev/null 2>&1 || true; fi
rm -rf /etc/mandopc /etc/sudoers.d/zz-mandopc
ROOT
rm -rf /home/deck/MandoPC

say "Adding DeckRemote to Steam"
if python3 "$APP/set_artwork.py" "$APP/art" >/dev/null 2>&1; then
  echo "    DeckRemote is already in your Steam library."
elif pgrep -x steam >/dev/null; then
  steamos-add-to-steam "$APP/DeckRemote.desktop" >/dev/null 2>&1 || true
  echo "    Confirm in Steam if it asks you to."
else
  echo "    Steam is not running. Add $APP/DeckRemote.desktop to Steam by hand (see README)."
fi

say "Installing library artwork"
for i in $(seq 1 30); do
  if python3 "$APP/set_artwork.py" "$APP/art"; then break; fi
  sleep 1
done

echo
say "Done! Go back to Game Mode and open DeckRemote from your library (Non-Steam)."
echo "    If you had the old 'Mando PC' shortcut, remove it from your library."
