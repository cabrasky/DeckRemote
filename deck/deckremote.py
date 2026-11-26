#!/usr/bin/env python3
"""DeckRemote: use your Steam Deck as a PC controller over the network.

Reads the controller Steam gives this app (SDL2, "Steam Virtual Gamepad") and feeds a virtual
USB gamepad exported with USB/IP: an Xbox 360 controller (xinput.py, XInput + rumble) or a
generic HID gamepad (/dev/hidg0). The PC attaches it with any USB/IP client.
"""
import ctypes, ctypes.util, errno, json, os, signal, socket, struct, subprocess, sys, threading, time

HELPER = "/etc/deckremote/gadget.sh"
HIDG = "/dev/hidg0"
SETTINGS = os.path.expanduser("~/.config/deckremote/settings.json")
HEADLESS = "--headless" in sys.argv
DEMO = "--demo" in sys.argv  # UI only, fake states (for screenshots / development)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import i18n  # noqa: E402  (UI strings, 12 languages)


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
    """Reads Steam's virtual gamepad and feeds the virtual USB gamepad.

    mode "xbox":    Xbox 360 controller (XInput, rumble) via xinput.py on dummy_hcd + usbip-host.
    mode "generic": plain HID gamepad on usbip-vudc (/dev/hidg0).
    """
    def __init__(self, mode="xbox"):
        self.mode = mode
        self.state = {"link": "off", "client": None, "pad": None, "busid": None, "mode": mode,
                      "buttons": set(), "axes": (0, 0, 0, 0, 0, 0), "rumble": (0, 0)}
        self.running = True
        self.gc = None
        self.fd = None
        self.xdev = None
        self.rumble = (0, 0)          # requested by the PC (0..255 strong, weak)
        self.rumble_sent = (0, 0, 0.0)

    def set_rumble(self, strong, weak):
        self.rumble = (strong, weak)
        self.state["rumble"] = (strong, weak)

    def start(self):
        if self.mode == "xbox":
            out = helper("up-xbox")
            if out.startswith("up-xbox"):
                import xinput
                self.state["busid"] = out.split()[1] if len(out.split()) > 1 else None
                self.xdev = xinput.XInputDevice(bind=lambda: helper("bind"), on_rumble=self.set_rumble)
                try:
                    self.xdev.start()
                    return
                except OSError:
                    self.xdev = None
                    helper("down")
            self.mode = self.state["mode"] = "generic"  # helper too old or raw-gadget missing
        helper("up")
        self.state["busid"] = "usbip-vudc.0"

    def stop(self):
        if self.xdev:
            self.xdev.stop()

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

    def xinput_report(self):
        import xinput
        g = self.gc
        buttons = {i: sdl.SDL_GameControllerGetButton(g, i) for i in xinput.SDL_TO_XINPUT}
        axes = tuple(sdl.SDL_GameControllerGetAxis(g, a) for a in range(6))
        return xinput.report(buttons, axes)

    def apply_rumble(self, now):
        """Mirror the PC's rumble on the Deck. XInput holds a level until changed; SDL rumble
        expires, so it is re-armed while non-zero."""
        strong, weak = self.rumble
        if not self.gc:
            return
        last_s, last_w, last_t = self.rumble_sent
        if (strong, weak) != (last_s, last_w) or ((strong or weak) and now - last_t > 0.5):
            sdl.SDL_GameControllerRumble(self.gc, strong * 257, weak * 257, 1000 if (strong or weak) else 0)
            self.rumble_sent = (strong, weak, now)

    def loop(self):
        load_sdl()
        sdl.SDL_GameControllerRumble.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32]
        sdl.SDL_Init(SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER)
        self.start()
        last, last_status, last_send = None, 0.0, 0.0
        while self.running:
            now = time.monotonic()
            if now - last_status > 1:
                last_status = now
                parts = helper("status").split()
                st = parts[0] if parts else "off"
                self.state["link"] = st
                self.state["client"] = client_ip() if st == "connected" else None
                if st != "connected":
                    self.set_rumble(0, 0)
                if self.mode == "generic" and self.fd is None and os.path.exists(HIDG):
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
            if self.gc:
                self.state["buttons"] = {i for i in range(15) if sdl.SDL_GameControllerGetButton(self.gc, i)}
                self.state["axes"] = tuple(sdl.SDL_GameControllerGetAxis(self.gc, a) for a in range(6))
            if self.gc and self.xdev:
                self.xdev.update(self.xinput_report())
                self.apply_rumble(now)
            elif self.gc and self.fd is not None:
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
        if self.gc:
            sdl.SDL_GameControllerRumble(self.gc, 0, 0, 0)
        if self.fd is not None:
            try:
                os.write(self.fd, NEUTRAL)
            except OSError:
                pass
            os.close(self.fd)
        sdl.SDL_Quit()


class DemoPad:
    """Fake backend for --demo: cycles the link states and animates input and rumble."""
    def __init__(self):
        self.state = {"link": "waiting", "client": None, "pad": "Steam Virtual Gamepad", "busid": "5-1",
                      "mode": load_settings().get("mode", "xbox"), "buttons": set(),
                      "axes": (0, 0, 0, 0, 0, 0), "rumble": (0, 0)}
        self.running = True

    def stop(self):
        pass

    def loop(self):
        import math
        step = float(os.environ.get("DECKREMOTE_DEMO_STEP", "5"))
        seq = [("waiting", None), ("connected", "192.168.1.20"), ("off", None)]
        t0 = time.monotonic()
        while self.running:
            t = time.monotonic() - t0
            self.state["link"], self.state["client"] = seq[int(t // step) % len(seq)]
            k = int(t * 2)
            self.state["buttons"] = {[0, 1, 2, 3, 9, 10, 11, 14, 4, 6][k % 10]}
            a = t * 2.2
            self.state["axes"] = (int(math.cos(a) * 30000), int(math.sin(a) * 30000),
                                  int(math.sin(a * 0.7) * 20000), 0, 0, int((math.sin(a) + 1) * 16000))
            self.state["rumble"] = (int((math.sin(t * 1.3) + 1) * 110), int((math.cos(t * 0.9) + 1) * 60))
            time.sleep(0.03)


# ---------------------------------------------------------------- UI (design "Hologram")
def run_ui(pad, stop):
    import tkinter as tk
    import tkinter.font as tkfont
    if sys.platform == "win32":  # UI preview on Windows: real pixels, no DPI scaling
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass

    UI = os.path.join(HERE, "ui")
    with open(os.path.join(UI, "layout.json")) as f:
        L = json.load(f)
    settings = load_settings()
    state = {"lang": settings.get("lang") if settings.get("lang") in i18n.LANGUAGES else None}
    detected = i18n.steam_language() or "en"

    TXT, DIM, INK = "#f6f8fc", "#b0a8d6", "#0b0918"
    COLORS = {"connected": "#4ade80", "waiting": "#31e8ff", "off": "#f87171"}
    DOTS = {"connected": "dot_green.png", "waiting": "dot_cyan.png", "off": "dot_red.png"}

    root = tk.Tk()
    root.title("DeckRemote")
    root.configure(bg=INK)
    if "--windowed" in sys.argv:
        root.geometry("1280x800")
        root.resizable(False, False)
    else:
        root.attributes("-fullscreen", True)
    canvas = tk.Canvas(root, width=1280, height=800, bg=INK, highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    installed = set(tkfont.families())
    family = next((f for f in ("Noto Sans", "Segoe UI", "DejaVu Sans") if f in installed), "Sans")
    fonts = {}

    def font(size, bold=False):
        key = (size, bold)
        if key not in fonts:
            fonts[key] = tkfont.Font(root, family=family, size=-size, weight="bold" if bold else "normal")
        return fonts[key]

    images = {}

    def img(name):
        if name not in images:
            images[name] = tk.PhotoImage(file=os.path.join(UI, name))
        return images[name]

    def t(key, **kw):
        return i18n.text(state["lang"] or detected, key, **kw)

    def button(x, y, label, kind, command, size=17, anchor="nw"):
        """Pill button from pre-rendered images; kind 'v' (outline violet) or 'm' (filled magenta)."""
        f = font(size, bold=True)
        need = f.measure(label) + 40
        widths = L["pill_widths"]
        w = next((w for w in widths if w >= need), widths[-1])
        h = 48 if kind == "v" else 56
        if anchor == "ne":
            x -= w
        tag = f"btn{len(images)}_{x}_{y}"
        canvas.create_image(x - 6, y - 6, image=img(f"pill_{kind}_{w}.png"), anchor="nw", tags=(tag, "screen"))
        canvas.create_text(x + w / 2, y + h / 2, text=label, font=f, fill=TXT if kind == "v" else INK,
                           tags=(tag, "screen"))
        canvas.tag_bind(tag, "<ButtonRelease-1>", lambda e: command())
        return w

    def quit_app():
        stop()
        root.destroy()

    def switch_mode():
        settings["mode"] = "generic" if pad.state.get("mode", "xbox") == "xbox" else "xbox"
        save_settings(settings)
        stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    root.protocol("WM_DELETE_WINDOW", quit_app)

    # ---- language picker
    def show_languages():
        canvas.delete("all")
        canvas.create_image(0, 0, image=img("bg_plain.png"), anchor="nw")
        canvas.create_image(640, 92, image=img("wordmark_big.png"), anchor="center")
        canvas.create_text(640, 165, text=t("choose_lang"), font=font(24), fill=DIM)
        for i, code in enumerate(i18n.LANGUAGES):
            col, row = i % 4, i // 4
            x, y = 140 + col * 260, 230 + row * 110
            tag = f"lang_{code}"
            tile = "tile_c.png" if code == (state["lang"] or detected) else ("tile_v.png" if row != 1 else "tile_m.png")
            canvas.create_image(x - 6, y - 6, image=img(tile), anchor="nw", tags=tag)
            canvas.create_text(x + 115, y + 40, text=i18n.S[code]["lang_name"], font=font(22, True), fill=TXT, tags=tag)
            canvas.tag_bind(tag, "<ButtonRelease-1>", lambda e, c=code: choose(c))
        canvas.create_text(640, 600, text=t("lang_hint"), font=font(18), fill=DIM)

    def choose(code):
        state["lang"] = code
        settings["lang"] = code
        save_settings(settings)
        show_main()

    # ---- main screen
    live = {}

    def show_main():
        canvas.delete("all")
        live.clear()
        canvas.create_image(0, 0, image=img("bg_main.png"), anchor="nw")
        ox, oy = L["pad_origin"]
        live["pad"] = canvas.create_image(ox, oy, image=img("pad_dim.png"), anchor="nw")
        live["btns"] = {i: canvas.create_image(ox, oy, image=img(f"btn_{i}.png"), anchor="nw", state="hidden")
                        for i in (0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14)}
        live["sticks"] = [canvas.create_image(*L["left_stick"], image=img("stick_dot.png")),
                          canvas.create_image(*L["right_stick"], image=img("stick_dot.png"))]
        canvas.create_image(60, 72, image=img("wordmark_small.png"), anchor="w")
        canvas.create_image(*L["card_origin"], image=img("card.png"), anchor="nw")
        live["dot"] = canvas.create_image(92, 190, image=img("dot_cyan.png"))
        live["title"] = canvas.create_text(116, 190, text="", font=font(32, True), fill=TXT, anchor="w")
        live["line1"] = canvas.create_text(92, 222, text="", font=font(20), fill=TXT, anchor="nw", width=440)
        live["line2"] = canvas.create_text(92, 282, text="", font=font(17), fill=DIM, anchor="nw", width=440)
        xbox = pad.state.get("mode", "xbox") == "xbox"
        chip_label = t("chip_xbox") if xbox else t("chip_generic")
        f = font(15, True)
        cw = next((w for w in L["chip_widths"] if w >= f.measure(chip_label) + 36), L["chip_widths"][-1])
        canvas.create_image(92 - 6, 326 - 6, image=img(f"chip_{'c' if xbox else 'v'}_{cw}.png"), anchor="nw")
        canvas.create_text(92 + cw / 2, 326 + 19, text=chip_label, font=f, fill=INK if xbox else TXT)
        canvas.create_text(92, 392, text=t("rumble"), font=font(15, True), fill=DIM, anchor="w")
        if xbox:
            live["bars"] = []
            for i, (label, color) in enumerate(((t("strong"), "#ff4fd8"), (t("weak"), "#7c4dff"))):
                x0 = 92 + i * 230
                canvas.create_text(x0, 418, text=label, font=font(14), fill=DIM, anchor="w")
                canvas.create_line(x0 + 7, 444, x0 + 193, 444, width=14, capstyle="round", fill="#282246")
                live["bars"].append((canvas.create_line(x0 + 7, 444, x0 + 8, 444, width=14, capstyle="round",
                                                        fill=color, state="hidden"), x0 + 7, 186))
        else:
            live["bars"] = []
            canvas.create_text(92, 430, text=t("no_rumble"), font=font(15), fill=DIM, anchor="w")
        live["foot"] = canvas.create_text(92, 498, text="", font=font(16), fill=DIM, anchor="w", width=440)
        x = 52
        x += button(x, 700, "⇄  " + (t("to_generic") if xbox else t("to_xbox")), "v", switch_mode) + 16
        button(x, 700, "A/文  " + t("lang_name"), "v", show_languages)
        button(1280 - 52, 696, t("quit"), "m", quit_app, size=19, anchor="ne")
        live["last"] = {}
        tick()

    def setv(key, item, **kw):
        """itemconfigure only when something changed (avoids flicker)."""
        if live["last"].get(key) != kw:
            live["last"][key] = kw
            canvas.itemconfigure(item, **kw)

    def tick():
        if "pad" not in live or not canvas.winfo_exists():
            return
        s = pad.state
        link = s["link"] if s["link"] in COLORS else "off"
        setv("pad", live["pad"], image=img("pad_on.png" if link == "connected" else "pad_dim.png"))
        setv("dot", live["dot"], image=img(DOTS[link]))
        setv("title", live["title"], text=t(link), fill=COLORS[link])
        if link == "connected":
            setv("l1", live["line1"], text=t("pc", ip=s.get("client") or "?"))
            setv("l2", live["line2"], text=t("deck_info", ip=own_ip_cached(), bus=s.get("busid") or "…"))
        elif link == "waiting":
            setv("l1", live["line1"], text=t("attach", ip=own_ip_cached(), bus=s.get("busid") or "…"))
            setv("l2", live["line2"], text="")
        else:
            setv("l1", live["line1"], text=t("off_help", err=s["link"]))
            setv("l2", live["line2"], text="")
        setv("foot", live["foot"], text=t("deck_buttons") if s.get("pad") else t("pad_none"),
             fill=DIM if s.get("pad") else COLORS["off"])
        pressed = s.get("buttons", set())
        for i, item in live["btns"].items():
            setv(f"b{i}", item, state="normal" if i in pressed else "hidden")
        ax = s.get("axes", (0,) * 6)
        travel = L["stick_travel"]
        for n, (cx, cy) in enumerate((L["left_stick"], L["right_stick"])):
            canvas.coords(live["sticks"][n], cx + ax[2 * n] / 32767 * travel, cy + ax[2 * n + 1] / 32767 * travel)
        for (item, x0, length), val in zip(live["bars"], s.get("rumble", (0, 0))):
            if val:
                canvas.coords(item, x0, 444, x0 + max(1, length * val / 255), 444)
            setv(f"bar{item}", item, state="normal" if val else "hidden")
        root.after(33, tick)

    ip_cache = {"ip": None, "t": 0.0}

    def own_ip_cached():
        if time.monotonic() - ip_cache["t"] > 5:
            ip_cache["ip"], ip_cache["t"] = own_ip(), time.monotonic()
        return ip_cache["ip"]

    if state["lang"]:
        show_main()
    else:
        show_languages()
    if "--snap" in sys.argv:  # development: save a screenshot of the window, then quit
        out = sys.argv[sys.argv.index("--snap") + 1]
        root.attributes("-topmost", True)
        root.lift()

        def snap():
            from PIL import ImageGrab
            root.update()
            x, y = canvas.winfo_rootx(), canvas.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + 1280, y + 800)).save(out)
            quit_app()
        root.after(int(float(os.environ.get("DECKREMOTE_SNAP_AFTER", "2.5")) * 1000), snap)
    root.mainloop()


def start_guard():
    """If this app dies without cleaning up (e.g. Steam kills it), shut the virtual gamepad down.

    Runs as a transient *user* unit so it survives Steam killing the game's process tree, and
    it exits on its own right after the app does. It only acts when no DeckRemote is running.
    """
    pid = os.getpid()
    script = (f"while kill -0 {pid} 2>/dev/null; do sleep 2; done; "
              f"pgrep -f '^[^ ]*python3? [^ ]*deckremote[.]py' >/dev/null || sudo -n {HELPER} down >/dev/null 2>&1")
    try:
        subprocess.Popen(["systemd-run", "--user", "--collect", "--quiet", f"--unit=deckremote-guard-{pid}",
                          "/bin/sh", "-c", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def main():
    mode = load_settings().get("mode", "xbox")
    pad = DemoPad() if DEMO else Pad(mode)
    up = "demo" if DEMO else mode
    if not DEMO:
        start_guard()
    stopped = threading.Event()

    def stop(*_):
        if stopped.is_set():
            return
        stopped.set()
        pad.running = False
        time.sleep(0.05)
        if not DEMO:
            pad.stop()
            helper("down")

    def on_signal(*_):
        stop()
        os._exit(0)

    signal.signal(signal.SIGTERM, on_signal)
    if hasattr(signal, "SIGHUP"):  # not on Windows (UI preview with --demo)
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
