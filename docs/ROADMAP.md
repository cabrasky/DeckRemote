# Roadmap: from "tech project" to "4 clicks"

[🇪🇸 Versión en español](es/HOJA_DE_RUTA.md)

The goal: someone thinks *"I want to use my Steam Deck as a controller"*, and a few clicks later it works. No Konsole, no IP addresses, no passwords.

## What stands in the way today

| Obstacle                                   | Why it hurts                                         |
| ------------------------------------------ | ---------------------------------------------------- |
| Desktop Mode + Konsole                     | Most Deck owners have never opened a terminal        |
| A `sudo` password                          | Many Deck owners never set one                       |
| Installing usbip-win2 on the PC            | A technical tool, in English, that installs a driver |
| Typing the IP and choosing `usbip-vudc.0`  | Nobody knows what that means                         |
| *Attach* every session                   | Friction every single time                           |
| Generic HID, not Xbox                      | Many PC games only accept XInput controllers         |

## Proposals, highest impact first

### 1. Xbox 360 controller emulation, so it works in every game

The Deck's kernel has **FunctionFS** (`CONFIG_USB_CONFIGFS_F_FS=y`). With it, the virtual device can present itself as an **Xbox 360 Controller** (`045e:028e`) with its vendor-specific descriptors. Windows recognises it with its built-in driver as **XInput**, exactly like a wired Xbox pad. That's the biggest compatibility win: every PC game, with no extra software. As a bonus, XInput sends **rumble** back, which could drive the Deck's haptics.

### 2. Windows companion app: no IPs, no `usbip-vudc.0`

One installer (`DeckRemote-Setup.exe`, or a **winget** / Microsoft Store package) that:

- installs usbip-win2 under the hood (or bundles its driver);
- opens a simple window that **finds the Deck on its own** and shows a big **Connect** button.

Auto-discovery: while the app is open, the Deck announces `_deckremote._tcp` over **mDNS/Bonjour** (Avahi ships with SteamOS). The PC app finds it and attaches automatically. It keeps the "nothing in the background" rule: the PC app only works while it's open.

### 3. Decky Loader plugin: no Konsole, no sudo

[Decky Loader](https://decky.xyz) is the most popular plugin store for the Deck, and its plugin backends **already run as root**. So:

- Install: Decky → Store → *DeckRemote* → Install. That's 2–3 clicks, right from Game Mode.
- No password and no sudo rule: the plugin does what `gadget.sh` does.
- A Quick Access (⋯) panel with a **"Use as PC controller"** toggle, the status and the PC's IP.
- The plugin creates the *DeckRemote* Steam shortcut (the part that reads the controller) and its artwork.

### 4. Pairing and security

USB/IP has no authentication. For a general audience:

- a 4-digit **pairing code** on the Deck that you confirm on the PC (the companion app checks it before attaching);
- or a firewall rule, only while the app is open, that lets just the paired PC reach port 3240.

### 5. Polish

- Ready-made **Steam Input template** (back grips mapped, gyro as right stick when a trigger is held).
- Mode picker: *Generic gamepad* / *Xbox controller*.
- Latency meter and a weak Wi‑Fi warning.
- More languages: the UI strings live in one table in `deckremote.py`.

### 6. Distribution

| Channel                                                                     | Audience                                                                                         | Effort |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ------ |
| **GitHub Releases**: a ZIP with a double-click `.desktop` installer | Tinkerers                                                                                        | Low    |
| **Decky Loader store**                                                | Most "power" Deck users                                                                          | Medium |
| **winget / Microsoft Store** (companion)                              | Any Windows user                                                                                 | Medium |
| **Flatpak on Discover**                                               | Not possible on its own: a Flatpak can't create virtual USB devices (it needs root and configfs) | —     |

## What it would feel like

1. **Deck:** Decky → Store → *DeckRemote* → Install.
2. **PC:** install *DeckRemote* from winget / the Microsoft Store.
3. **Play:** on the Deck, ⋯ → *DeckRemote* → toggle on. On the PC, open *DeckRemote* → "Steam Deck found" → **Connect**.

That's about 4 clicks per device the first time, and 2 clicks per session after that. No terminal, no IPs, no passwords.

## Suggested order

1. Xbox 360 emulation (compatibility is what users notice first).
2. mDNS discovery + Windows companion app.
3. Decky Loader plugin.
4. Pairing code.
5. Steam Input template, languages, store listings.
