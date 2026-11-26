#!/usr/bin/env python3
"""DeckRemote: use your Steam Deck as a standard USB gamepad for your PC, over the network.

Reads the controller Steam gives this app (SDL2, "Steam Virtual Gamepad") and writes HID
reports to the virtual USB gadget /dev/hidg0, which /etc/deckremote/gadget.sh creates and
exports with USB/IP (usbipd --device). The PC attaches it with any USB/IP client.
"""
import ctypes, ctypes.util, errno, json, os, signal, socket, struct, subprocess, sys, threading, time

HELPER = "/etc/deckremote/gadget.sh"
HIDG = "/dev/hidg0"
SETTINGS = os.path.expanduser("~/.config/deckremote/settings.json")
HEADLESS = "--headless" in sys.argv
DEMO = "--demo" in sys.argv  # UI only, fake states (for screenshots / development)

# ---------------------------------------------------------------- translations
STRINGS = {
    "en": {
        "lang_name": "English",
        "choose_lang": "Choose your language",
        "connected": "● Connected to PC",
        "client": "PC: {ip}",
        "client_generic": "PC connected",
        "waiting": "● Waiting for PC…",
        "waiting_help": "On your PC, open USBip and attach\n{ip}  →  usbip-vudc.0  (DeckRemote)",
        "off": "● Not sharing",
        "off_help": "Couldn't start the virtual controller ({err}).",
        "pad": "Controller: {name}",
        "pad_none": "not detected — launch DeckRemote from Steam",
        "deck_buttons": "The Steam and ⋯ buttons stay on your Deck.",
        "quit": "Disconnect & exit",
    },
    "es": {
        "lang_name": "Español",
        "choose_lang": "Elige tu idioma",
        "connected": "● Conectado al PC",
        "client": "PC: {ip}",
        "client_generic": "PC conectado",
        "waiting": "● Esperando al PC…",
        "waiting_help": "En el PC, abre USBip y conecta\n{ip}  →  usbip-vudc.0  (DeckRemote)",
        "off": "● Sin compartir",
        "off_help": "No se pudo activar el mando virtual ({err}).",
        "pad": "Mando: {name}",
        "pad_none": "no detectado — abre DeckRemote desde Steam",
        "deck_buttons": "Los botones Steam y ⋯ siguen siendo de tu Deck.",
        "quit": "Desconectar y salir",
    },
}


def load_settings():
    try:
        with open(SETTINGS) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
        with open(SETTINGS, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


# ---------------------------------------------------------------- SDL2 (ctypes)
sdl = None
SDL_INIT_JOYSTICK, SDL_INIT_GAMECONTROLLER = 0x200, 0x2000


def load_sdl():
    global sdl
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    # Never open the Deck's physical controller directly (it belongs to Steam): no HIDAPI,
    # only the "Steam Virtual Gamepad" that Steam Input gives to games.
    os.environ["SDL_JOYSTICK_HIDAPI"] = "0"
    sdl = ctypes.CDLL(ctypes.util.find_library("SDL2-2.0") or "libSDL2-2.0.so.0")
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    sdl.SDL_GameControllerGetButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerGetButton.restype = ctypes.c_uint8
    sdl.SDL_GameControllerGetAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
    sdl.SDL_GameControllerGetAxis.restype = ctypes.c_int16
    sdl.SDL_GameControllerGetAttached.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
    sdl.SDL_GameControllerNameForIndex.restype = ctypes.c_char_p

# SDL button index -> HID button bit (1=A 2=B 3=X 4=Y 5=LB 6=RB 7=View 8=Menu 9=LS 10=RS)
BUTTON_MAP = {0: 0, 1: 1, 2: 2, 3: 3, 9: 4, 10: 5, 4: 6, 6: 7, 7: 8, 8: 9}
DPAD = (11, 12, 13, 14)  # up, down, left, right
HAT = {(1, 0, 0, 0): 0, (1, 0, 0, 1): 1, (0, 0, 0, 1): 2, (0, 1, 0, 1): 3,
       (0, 1, 0, 0): 4, (0, 1, 1, 0): 5, (0, 0, 1, 0): 6, (1, 0, 1, 0): 7}
NEUTRAL = struct.pack("<HBhhhhBB", 0, 8, 0, 0, 0, 0, 0, 0)


def helper(verb):
    r = subprocess.run(["sudo", "-n", HELPER, verb], capture_output=True, text=True)
    return r.stdout.strip() or r.stderr.strip()


def own_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))  # no packet is sent; only picks the LAN interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "?"


def client_ip():
    try:
        out = subprocess.run(["ss", "-Htn", "state", "established", "( sport = :3240 )"],
                             capture_output=True, text=True).stdout.strip()
        if not out:
            return None
        peer = out.splitlines()[0].split()[-1]
        return peer.rsplit(":", 1)[0].replace("::ffff:", "").strip("[]")
    except Exception:
        return None


class Pad:
    def __init__(self):
        self.state = {"link": "off", "client": None, "pad": None}
        self.running = True
        self.gc = None
        self.fd = None

    def pick_controller(self):
        for i in range(sdl.SDL_NumJoysticks()):
            if not sdl.SDL_IsGameController(i):
                continue
            name = (sdl.SDL_GameControllerNameForIndex(i) or b"").decode(errors="ignore")
            if "Steam Virtual" in name:
                return i
        return None

    def report(self):
        g = self.gc
        b = 0
        for sdl_btn, bit in BUTTON_MAP.items():
            if sdl.SDL_GameControllerGetButton(g, sdl_btn):
                b |= 1 << bit
        hat = HAT.get(tuple(sdl.SDL_GameControllerGetButton(g, x) for x in DPAD), 8)
        ax = [sdl.SDL_GameControllerGetAxis(g, a) for a in range(6)]
        lt, rt = max(0, ax[4]) * 255 // 32767, max(0, ax[5]) * 255 // 32767
        c = lambda v: max(-32767, v)
        return struct.pack("<HBhhhhBB", b, hat, c(ax[0]), c(ax[1]), c(ax[2]), c(ax[3]), lt, rt)

    def loop(self):
        load_sdl()
        sdl.SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER)
        last, last_status, last_send = None, 0.0, 0.0
        while self.running:
            now = time.monotonic()
            if now - last_status > 1:
                last_status = now
                st = helper("status")
                self.state["link"] = st
                self.state["client"] = client_ip() if st == "connected" else None
                if self.fd is None and os.path.exists(HIDG):
                    try:
                        self.fd = os.open(HIDG, os.O_WRONLY | os.O_NONBLOCK)
                    except OSError:
                        self.fd = None
            sdl.SDL_GameControllerUpdate()
            if self.gc and not sdl.SDL_GameControllerGetAttached(self.gc):
                sdl.SDL_GameControllerClose(self.gc)
                self.gc = None
            if not self.gc:
                idx = self.pick_controller()
                if idx is not None:
                    self.gc = sdl.SDL_GameControllerOpen(idx)
                    self.state["pad"] = (sdl.SDL_GameControllerNameForIndex(idx) or b"?").decode(errors="ignore")
                    last = None
                else:
                    self.state["pad"] = None
            if self.gc and self.fd is not None:
                rep = self.report()
                if rep != last or now - last_send > 0.1:
                    try:
                        os.write(self.fd, rep)
                        last, last_send = rep, now
                    except OSError as e:
                        if e.errno != errno.EAGAIN:
                            try:
                                os.close(self.fd)
                            except OSError:
                                pass
                            self.fd = None
            time.sleep(0.004)
        if self.fd is not None:
            try:
                os.write(self.fd, NEUTRAL)
            except OSError:
                pass
            os.close(self.fd)
        sdl.SDL_Quit()


class DemoPad:
    """Fake backend for --demo: cycles through the three states."""
    def __init__(self):
        self.state = {"link": "waiting", "client": None, "pad": "Steam Virtual Gamepad"}
        self.running = True

    def loop(self):
        seq = [("waiting", None), ("connected", "192.168.1.20"), ("off", None)]
        i = 0
        while self.running:
            self.state["link"], self.state["client"] = seq[i % len(seq)]
            i += 1
            time.sleep(float(os.environ.get("DECKREMOTE_DEMO_STEP", "4")))


# ---------------------------------------------------------------- UI
def run_ui(pad, stop):
    import tkinter as tk
    settings = load_settings()
    lang = {"code": settings.get("lang")}
    if lang["code"] not in STRINGS and "--lang" in sys.argv:
        lang["code"] = sys.argv[sys.argv.index("--lang") + 1]

    BG, FG, DIM = "#0b0918", "#ffffff", "#b0a8d6"
    CYAN, MAGENTA, CARD = "#31e8ff", "#ff4fd8", "#17132b"
    here = os.path.dirname(os.path.abspath(__file__))
    root = tk.Tk()
    root.title("DeckRemote")
    root.configure(bg=BG)
    if "--windowed" in sys.argv:
        root.geometry("1280x800")
    else:
        root.attributes("-fullscreen", True)

    images = {}

    def image(name, sub=1):
        key = (name, sub)
        if key not in images:
            try:
                img = tk.PhotoImage(file=os.path.join(here, "art", name))
                images[key] = img.subsample(sub) if sub > 1 else img
            except tk.TclError:
                images[key] = None
        return images[key]

    def header(parent, pady=(36, 8)):
        logo = image("logo.png", 2)
        if logo:
            tk.Label(parent, image=logo, bg=BG, bd=0).pack(pady=pady)
        else:
            tk.Label(parent, text="DeckRemote", font=("Sans", 40, "bold"), fg=FG, bg=BG).pack(pady=pady)

    def pill_button(parent, text, command, color, font_size=24, width=None):
        frame = tk.Frame(parent, bg=color, padx=3, pady=3)
        b = tk.Button(frame, text=text, font=("Sans", font_size, "bold"), command=command, width=width,
                      fg=FG, bg=CARD, activebackground=color, activeforeground=BG,
                      relief="flat", bd=0, padx=36, pady=18, highlightthickness=0)
        b.pack()
        return frame

    def t(key, **kw):
        return STRINGS[lang["code"] or "en"][key].format(**kw)

    def quit_app():
        stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", quit_app)

    def clear():
        for w in root.winfo_children():
            w.destroy()

    # ---- first run: language picker
    def show_language_picker():
        clear()
        header(root, pady=(70, 10))
        tk.Label(root, text="Choose your language  ·  Elige tu idioma", font=("Sans", 21),
                 fg=DIM, bg=BG).pack(pady=(10, 56))
        row = tk.Frame(root, bg=BG)
        row.pack()
        for code, color in zip(STRINGS, (CYAN, MAGENTA)):
            pill_button(row, STRINGS[code]["lang_name"], lambda c=code: choose(c), color,
                        font_size=28, width=9).pack(side="left", padx=28)

    def choose(code):
        lang["code"] = code
        settings["lang"] = code
        save_settings(settings)
        show_main()

    # ---- main screen
    def show_main():
        clear()
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x")
        tk.Button(top, text="A/文  " + t("lang_name"), font=("Sans", 15), command=show_language_picker,
                  fg=DIM, bg=BG, activebackground=CARD, activeforeground=FG, bd=0,
                  relief="flat", padx=16, pady=8, highlightthickness=0).pack(side="right", padx=20, pady=14)
        header(root, pady=(0, 4))
        card = tk.Frame(root, bg=CARD, padx=40, pady=22)
        card.pack(pady=(6, 0))
        status = tk.Label(card, text="", font=("Sans", 30, "bold"), bg=CARD)
        status.pack(pady=(0, 10))
        detail = tk.Label(card, text="", font=("Sans", 18), fg=DIM, bg=CARD, justify="center")
        detail.pack()
        pill_button(root, t("quit"), quit_app, MAGENTA, font_size=22).pack(side="bottom", pady=40)

        def refresh():
            if not status.winfo_exists():
                return
            s = pad.state
            if s["link"] == "connected":
                status.config(text=t("connected"), fg="#4ade80")
                msg = t("client", ip=s["client"]) if s["client"] else t("client_generic")
            elif s["link"] == "waiting":
                status.config(text=t("waiting"), fg=CYAN)
                msg = t("waiting_help", ip=own_ip())
            else:
                status.config(text=t("off"), fg="#f87171")
                msg = t("off_help", err=s["link"])
            msg += "\n\n" + t("pad", name=s["pad"] or t("pad_none"))
            msg += "\n" + t("deck_buttons")
            detail.config(text=msg)
            root.after(500, refresh)

        refresh()

    if lang["code"] in STRINGS:
        show_main()
    else:
        show_language_picker()
    root.mainloop()


def main():
    pad = DemoPad() if DEMO else Pad()
    up = "demo" if DEMO else helper("up")
    stopped = threading.Event()

    def stop(*_):
        if stopped.is_set():
            return
        stopped.set()
        pad.running = False
        time.sleep(0.05)
        if not DEMO:
            helper("down")

    def on_signal(*_):
        stop()
        os._exit(0)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGHUP, on_signal)
    threading.Thread(target=pad.loop, daemon=True).start()

    if HEADLESS:
        try:
            while True:
                s = pad.state
                print(f"helper={up} link={s['link']} client={s['client']} pad={s['pad']}", flush=True)
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        stop()
        return

    run_ui(pad, stop)
    stop()


if __name__ == "__main__":
    main()
