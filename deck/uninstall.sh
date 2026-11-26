#!/bin/bash
# DeckRemote uninstaller for the Steam Deck. Run from Konsole:   bash deck/uninstall.sh
# Remove the "DeckRemote" shortcut from your Steam library by hand afterwards.
sudo bash -c '
  [ -x /etc/deckremote/gadget.sh ] && /etc/deckremote/gadget.sh down >/dev/null 2>&1
  rm -rf /etc/deckremote /etc/sudoers.d/zz-deckremote
'
rm -rf /home/deck/DeckRemote /home/deck/.config/deckremote
echo "DeckRemote removed. Now remove the 'DeckRemote' shortcut from your Steam library."
