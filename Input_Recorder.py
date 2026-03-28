"""
MacroRecorder - Roblox compatible keyboard macro recorder
Fully customizable hotkeys — set them inside the app.

Requirements: pip install pynput keyboard
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import time
import json
import ctypes
import os
import random

try:
    from pynput import keyboard as pynput_keyboard
    from pynput import mouse as pynput_mouse
    import keyboard as kb
except ImportError:
    print("Run: pip install pynput keyboard")
    exit(1)

user32 = ctypes.windll.user32

# ─── Key sending ───────────────────────────────────────────────────────────────

KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD  = 1

VK_MAP = {
    "Key.space": 0x20, "Key.enter": 0x0D, "Key.backspace": 0x08,
    "Key.tab": 0x09, "Key.shift": 0x10, "Key.shift_r": 0xA1,
    "Key.ctrl_l": 0xA2, "Key.ctrl_r": 0xA3, "Key.alt_l": 0xA4, "Key.alt_r": 0xA5,
    "Key.caps_lock": 0x14, "Key.esc": 0x1B, "Key.delete": 0x2E,
    "Key.left": 0x25, "Key.up": 0x26, "Key.right": 0x27, "Key.down": 0x28,
    "Key.f1": 0x70, "Key.f2": 0x71, "Key.f3": 0x72, "Key.f4": 0x73,
    "Key.f5": 0x74, "Key.f6": 0x75, "Key.f7": 0x76, "Key.f8": 0x77,
    "Key.f9": 0x78, "Key.f10": 0x79, "Key.f11": 0x7A, "Key.f12": 0x7B,
}

class KEYBDINPUT(ctypes.Structure): 
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _UNION)]

def send_key(key_str, key_up=False):
    """Send a key using the keyboard library"""
    try:
        # Clean up the key name
        key_name = key_str.replace("Key.", "") if isinstance(key_str, str) else key_str
        
        # Handle the key
        if not key_up:
            kb.press(key_name)
            print(f"[DEBUG] Pressed: {key_name}")
        else:
            kb.release(key_name)
            print(f"[DEBUG] Released: {key_name}")
    except Exception as e:
        print(f"[ERROR] Failed to send key '{key_str}': {e}")

def get_vk(key_str):
    """Return the key string as-is for use with keyboard library"""
    return key_str


def send_mouse(button, action):
    """Send a mouse click"""
    try:
        mouse = pynput_mouse.Controller()
        if action == "press":
            mouse.press(button)
            print(f"[DEBUG] Mouse pressed: {button}")
        elif action == "release":
            mouse.release(button)
            print(f"[DEBUG] Mouse released: {button}")
        elif action == "click":
            mouse.click(button)
            print(f"[DEBUG] Mouse clicked: {button}")
    except Exception as e:
        print(f"[ERROR] Failed to send mouse event: {e}")


# ─── Recorder ──────────────────────────────────────────────────────────────────

class MacroRecorder:
    def __init__(self):
        self.events = []
        self.recording = False
        self.playing = False
        self._start_time = None
        self._kb_listener = None
        self._mouse_listener = None
        self.hotkeys = {}  # filled by App: {"record": "f6", "stop": "f7", ...}
        # Recording options
        self.record_keyboard = True
        self.record_mouse = False
        self.on_event_recorded = None  # Callback for recording preview

    def start_recording(self):
        self.events = []
        self.recording = True
        self._start_time = time.time()
        try:
            if self.record_keyboard:
                self._kb_listener = pynput_keyboard.Listener(
                    on_press=self._on_press, on_release=self._on_release)
                self._kb_listener.start()
                print("[DEBUG] Keyboard listener started successfully")
            if self.record_mouse:
                self._mouse_listener = pynput_mouse.Listener(
                    on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
                self._mouse_listener.start()
                print("[DEBUG] Mouse listener started successfully")
        except Exception as e:
            print(f"[ERROR] Failed to start listener: {e}")
            self.recording = False
            raise

    def stop_recording(self):
        self.recording = False
        if self._kb_listener:
            self._kb_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()

    def _ts(self):
        return time.time() - self._start_time

    def _is_hotkey(self, char):
        return char in self.hotkeys

    def _on_press(self, key):
        if not self.recording:
            return
        try:
            char = key.char or str(key)
        except AttributeError:
            char = str(key)
        if self._is_hotkey(char) or self._is_hotkey(char.replace("Key.", "")):
            return
        print(f"[DEBUG] Key pressed: {char}")
        event = {"type": "key_press", "key": char, "time": self._ts()}
        self.events.append(event)
        if self.on_event_recorded:
            self.on_event_recorded(f"Key pressed: {char}")

    def _on_release(self, key):
        if not self.recording:
            return
        try:
            char = key.char or str(key)
        except AttributeError:
            char = str(key)
        if self._is_hotkey(char) or self._is_hotkey(char.replace("Key.", "")):
            return
        print(f"[DEBUG] Key released: {char}")
        event = {"type": "key_release", "key": char, "time": self._ts()}
        self.events.append(event)
        if self.on_event_recorded:
            self.on_event_recorded(f"Key released: {char}")

    def _on_move(self, x, y):
        """Record mouse movement"""
        if not self.recording:
            return
        # To avoid too much data, we could limit recording frequency
        # but for now we'll record all movements
        print(f"[DEBUG] Mouse moved to: {x}, {y}")
        self.events.append({"type": "mouse_move", "x": x, "y": y, "time": self._ts()})

    def _on_click(self, x, y, button, pressed):
        """Record mouse clicks"""
        if not self.recording:
            return
        action = "mouse_press" if pressed else "mouse_release"
        button_name = button.name
        print(f"[DEBUG] Mouse {action}: {button_name} at {x}, {y}")
        event = {"type": action, "button": button_name, "x": x, "y": y, "time": self._ts()}
        self.events.append(event)
        if self.on_event_recorded:
            self.on_event_recorded(f"Mouse {button_name} click @ {x},{y}")

    def _on_scroll(self, x, y, dx, dy):
        """Record mouse scroll"""
        if not self.recording:
            return
        print(f"[DEBUG] Mouse scrolled at {x}, {y}: {dx}, {dy}")
        self.events.append({"type": "mouse_scroll", "x": x, "y": y, "dx": dx, "dy": dy, "time": self._ts()})

    def play(self, speed=1.0, repeat=1, status_cb=None):
        self.playing = True
        iteration = 0
        mouse = pynput_mouse.Controller()
        try:
            while self.playing:
                iteration += 1
                if status_cb:
                    status_cb(f"Playing... loop {iteration}" if repeat != 1 else "Playing...")
                prev_time = 0
                for event in self.events:
                    if not self.playing:
                        break
                    delay = (event["time"] - prev_time) / speed
                    if delay > 0:
                        time.sleep(delay)
                    prev_time = event["time"]
                    
                    # Handle keyboard events
                    if event["type"] == "key_press":
                        send_key(event["key"], key_up=False)
                    elif event["type"] == "key_release":
                        send_key(event["key"], key_up=True)
                    
                    # Handle mouse events
                    elif event["type"] == "mouse_move":
                        mouse.position = (event["x"], event["y"])
                        print(f"[DEBUG] Moved mouse to {event['x']}, {event['y']}")
                    elif event["type"] == "mouse_press":
                        send_mouse(event["button"], "press")
                    elif event["type"] == "mouse_release":
                        send_mouse(event["button"], "release")
                    elif event["type"] == "mouse_click":
                        send_mouse(event["button"], "click")
                    elif event["type"] == "mouse_scroll":
                        mouse.scroll(event["dx"], event["dy"])
                        print(f"[DEBUG] Scrolled mouse: {event['dx']}, {event['dy']}")
                
                if repeat != 0 and iteration >= repeat:
                    break
        except Exception as e:
            if status_cb:
                status_cb(f"Error: {e}")
        finally:
            self.playing = False
            if status_cb:
                status_cb("Ready")

    def stop_playback(self):
        self.playing = False

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.events, f, indent=2)

    def load(self, path):
        with open(path, "r") as f:
            self.events = json.load(f)


# ─── GUI ───────────────────────────────────────────────────────────────────────

# Default hotkeys
DEFAULT_HOTKEYS = {
    "record": "f6",
    "stop":   "f9",
    "play":   "f10",
    "panic":  "f8",
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MacroRecorder")
        self.geometry("420x900")
        self.resizable(False, False)
        self.configure(bg="#0f0f0f")

        self.recorder = MacroRecorder()
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        self.recorder.hotkeys = {v for v in self.hotkeys.values()}
        self._registered = []
        self._listening_for = None  # which hotkey slot is being rebound
        self.autoclicker_running = False  # Flag to track autoclicker state

        self._build_ui()
        self._register_hotkeys()
        self._update_count()

    # ── UI Build ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        BG    = "#0f0f0f"
        CARD  = "#1a1a1a"
        ACCENT= "#00ff88"
        RED   = "#ff4444"
        TEXT  = "#e0e0e0"
        DIM   = "#555555"
        FONT  = ("Courier New", 10)

        # Title
        tf = tk.Frame(self, bg=BG)
        tf.pack(fill="x", padx=20, pady=(20,4))
        tk.Label(tf, text="⬤ MACRO", font=("Courier New",18,"bold"), bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(tf, text="RECORDER", font=("Courier New",18,"bold"), bg=BG, fg=TEXT).pack(side="left")
        tk.Label(tf, text="by Nölli_Hestur", font=("Courier New",9), bg=BG, fg="#555").pack(side="left", padx=(8,0))
        tk.Label(self, text="Customizable hotkeys",
                 font=("Courier New",9), bg=BG, fg=DIM).pack(anchor="w", padx=20)

        # Create notebook (tabs)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=[10, 5])
        style.map('TNotebook.Tab', background=[('selected', CARD)], foreground=[('selected', '#ffffff'), ('!selected', '#000000')])
        
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=10)

        # Create tabs
        recorder_tab = tk.Frame(self.notebook, bg=BG)
        autoclicker_tab = tk.Frame(self.notebook, bg=BG)
        randomized_tab = tk.Frame(self.notebook, bg=BG)
        profiles_tab = tk.Frame(self.notebook, bg=BG)
        
        self.notebook.add(recorder_tab, text=" Recorder ")
        self.notebook.add(autoclicker_tab, text=" Autoclicker ")
        self.notebook.add(randomized_tab, text=" Randomized ")
        self.notebook.add(profiles_tab, text=" Profiles ")
        
        # Initialize randomized playback state
        self.randomized_playing = False

        # ═══════════════════════════════════════════════════════════════════════
        # RECORDER TAB
        # ═══════════════════════════════════════════════════════════════════════

        # Hotkey configurator
        hk_card = tk.Frame(recorder_tab, bg=CARD, pady=12, padx=16)
        hk_card.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(hk_card, text="HOTKEYS  (click a button to rebind)",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        self._hk_buttons = {}
        actions = [
            ("record", "Start recording", RED),
            ("stop",   "Stop",            "#ffaa00"),
            ("play",   "Play macro",      ACCENT),
            ("panic",  "PANIC SHUTDOWN",  "#ff0000"),
        ]
        for key, label, color in actions:
            row = tk.Frame(hk_card, bg=CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=FONT, bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
            btn = tk.Button(row, text=self.hotkeys[key].upper(),
                            font=("Courier New",10,"bold"),
                            bg="#2a2a2a", fg=color, relief="flat", cursor="hand2",
                            width=8, activebackground="#333",
                            command=lambda k=key: self._start_rebind(k))
            btn.pack(side="left")
            self._hk_buttons[key] = btn

        self.rebind_label = tk.Label(hk_card, text="",
                                     font=("Courier New",9), bg=CARD, fg="#ffaa00")
        self.rebind_label.pack(anchor="w", pady=(4,0))

        self._sep_frame(recorder_tab)

        # Recording Options
        ro_card = tk.Frame(recorder_tab, bg=CARD, pady=12, padx=16)
        ro_card.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(ro_card, text="RECORDING OPTIONS",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        self.record_kb_var = tk.BooleanVar(value=True)
        self.record_mouse_var = tk.BooleanVar(value=False)
        
        r1 = tk.Frame(ro_card, bg=CARD)
        r1.pack(fill="x", pady=2)
        tk.Checkbutton(r1, text="Record Keyboard", variable=self.record_kb_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT,
                       command=self._update_record_options).pack(side="left")

        r2 = tk.Frame(ro_card, bg=CARD)
        r2.pack(fill="x", pady=2)
        tk.Checkbutton(r2, text="Record Mouse", variable=self.record_mouse_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT,
                       command=self._update_record_options).pack(side="left")

        self._sep_frame(recorder_tab)

        # Status
        sc = tk.Frame(recorder_tab, bg=CARD, pady=12, padx=16)
        sc.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(sc, text="STATUS", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w")
        self.status_var = tk.StringVar(value="Idle")
        self.status_lbl = tk.Label(sc, textvariable=self.status_var,
                                   font=("Courier New",13,"bold"), bg=CARD, fg=ACCENT)
        self.status_lbl.pack(anchor="w")
        self.count_var = tk.StringVar(value="0 events recorded")
        tk.Label(sc, textvariable=self.count_var, font=FONT, bg=CARD, fg=DIM).pack(anchor="w")

        self._sep_frame(recorder_tab)

        # Recording Preview (Toggleable)
        self.preview_visible = tk.BooleanVar(value=False)
        self.prev_header = tk.Frame(recorder_tab, bg=BG)
        self.prev_header.pack(fill="x", padx=0, pady=(0,0))
        tk.Checkbutton(self.prev_header, text="🔍 Show Recording Preview", variable=self.preview_visible,
                       font=("Courier New",8), bg=BG, fg="#888", selectcolor=BG,
                       activebackground=BG, activeforeground=ACCENT,
                       command=self._toggle_preview_visibility).pack(anchor="w", padx=20, pady=4)
        
        self.prev_card = tk.Frame(recorder_tab, bg=CARD, pady=8, padx=16)
        tk.Label(self.prev_card, text="RECORDING PREVIEW",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))
        
        # Scrollable preview listbox
        preview_frame = tk.Frame(self.prev_card, bg="#2a2a2a", relief="flat", bd=0, height=100)
        preview_frame.pack(fill="both", expand=False, padx=0, pady=(0,6))
        preview_frame.pack_propagate(False)
        
        scrollbar = tk.Scrollbar(preview_frame, bg="#333", troughcolor="#1a1a1a")
        scrollbar.pack(side="right", fill="y")
        
        self.preview_listbox = tk.Listbox(preview_frame, bg="#2a2a2a", fg=ACCENT,
                                          font=("Courier New", 9), yscrollcommand=scrollbar.set,
                                          relief="flat", bd=0, selectmode="none")
        self.preview_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.preview_listbox.yview)
        
        # Clear preview button
        tk.Button(self.prev_card, text="Clear Preview", font=("Courier New",8),
                  bg="#2a2a2a", fg="#666", relief="flat", cursor="hand2",
                  command=self._clear_preview).pack(anchor="w")

        # Record / Stop buttons
        bf = tk.Frame(recorder_tab, bg=BG)
        bf.pack(fill="x", padx=0, pady=5)
        self.rec_btn = tk.Button(bf, text="⬤  RECORD", font=("Courier New",10,"bold"),
            bg=RED, fg="white", relief="flat", cursor="hand2",
            activebackground="#cc0000", command=self._toggle_record, height=2)
        self.rec_btn.pack(side="left", expand=True, fill="x", padx=(0,5))
        self.stop_btn = tk.Button(bf, text="■  STOP", font=("Courier New",10,"bold"),
            bg="#333", fg=DIM, relief="flat", cursor="hand2",
            activebackground="#444", activeforeground=TEXT,
            command=self._stop_all, height=2, state="disabled")
        self.stop_btn.pack(side="left", expand=True, fill="x")

        self._sep_frame(recorder_tab)

        # Playback settings
        sc2 = tk.Frame(recorder_tab, bg=CARD, pady=12, padx=16)
        sc2.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(sc2, text="PLAYBACK SETTINGS", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w")

        r1 = tk.Frame(sc2, bg=CARD)
        r1.pack(fill="x", pady=(6,0))
        tk.Label(r1, text="Speed:", font=FONT, bg=CARD, fg=TEXT, width=12, anchor="w").pack(side="left")
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Scale(r1, from_=0.25, to=4.0, resolution=0.25, orient="horizontal",
                 variable=self.speed_var, bg=CARD, fg=ACCENT, troughcolor="#333",
                 highlightthickness=0, sliderlength=15, length=190).pack(side="left")

        r2 = tk.Frame(sc2, bg=CARD)
        r2.pack(fill="x", pady=(4,0))
        tk.Label(r2, text="Repeat:", font=FONT, bg=CARD, fg=TEXT, width=12, anchor="w").pack(side="left")
        self.repeat_var = tk.StringVar(value="1")
        vcmd = (self.register(lambda v: v.isdigit() or v == ""), "%P")
        tk.Entry(r2, textvariable=self.repeat_var, font=FONT, width=6,
                 bg="#2a2a2a", fg=ACCENT, insertbackground=ACCENT, relief="flat",
                 validate="key", validatecommand=vcmd).pack(side="left", padx=(0,8))
        self.loop_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r2, text="Loop forever", variable=self.loop_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT,
                       command=self._toggle_loop).pack(side="left")

        self.play_btn = tk.Button(recorder_tab, text="▶  PLAY MACRO",
            font=("Courier New",11,"bold"), bg=ACCENT, fg="#0f0f0f",
            relief="flat", cursor="hand2", activebackground="#00cc66",
            command=self._play, height=2, state="disabled")
        self.play_btn.pack(fill="x", padx=0, pady=5)

        self._sep_frame(recorder_tab)

        ff = tk.Frame(recorder_tab, bg=BG)
        ff.pack(fill="x", padx=0, pady=5)
        tk.Button(ff, text="💾  Save", font=FONT, bg="#1e3a2a", fg=ACCENT,
                  relief="flat", cursor="hand2", command=self._save,
                  padx=10, pady=6).pack(side="left", expand=True, fill="x", padx=(0,5))
        tk.Button(ff, text="📂  Load", font=FONT, bg="#1e2a3a", fg="#4488ff",
                  relief="flat", cursor="hand2", command=self._load,
                  padx=10, pady=6).pack(side="left", expand=True, fill="x")

        # ═══════════════════════════════════════════════════════════════════════
        # AUTOCLICKER TAB
        # ═══════════════════════════════════════════════════════════════════════

        ac_card = tk.Frame(autoclicker_tab, bg=CARD, pady=12, padx=16)
        ac_card.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(ac_card, text="AUTOCLICKER SETTINGS",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        # Click delay
        r3 = tk.Frame(ac_card, bg=CARD)
        r3.pack(fill="x", pady=4)
        tk.Label(r3, text="Click delay (ms):", font=FONT, bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
        self.click_delay_var = tk.StringVar(value="100")
        vcmd = (self.register(lambda v: v.isdigit() or v == ""), "%P")
        self.click_delay_entry = tk.Entry(r3, textvariable=self.click_delay_var, font=FONT, width=8,
                 bg="#2a2a2a", fg=ACCENT, insertbackground=ACCENT, relief="flat",
                 validate="key", validatecommand=vcmd)
        self.click_delay_entry.pack(side="left")

        # Mouse button selection
        r4 = tk.Frame(ac_card, bg=CARD)
        r4.pack(fill="x", pady=4)
        tk.Label(r4, text="Mouse button:", font=FONT, bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
        self.mouse_button_var = tk.StringVar(value="left")
        button_menu = tk.OptionMenu(r4, self.mouse_button_var, "left", "right", "middle")
        button_menu.config(bg="#2a2a2a", fg=ACCENT, relief="flat", highlightthickness=0)
        button_menu["menu"].config(bg="#2a2a2a", fg=ACCENT, activebackground="#444", activeforeground=ACCENT)
        button_menu.pack(side="left")

        self._sep_frame(autoclicker_tab)

        # Autoclicker status
        acs = tk.Frame(autoclicker_tab, bg=CARD, pady=12, padx=16)
        acs.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(acs, text="STATUS", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w")
        self.autoclick_status_var = tk.StringVar(value="Idle")
        self.autoclick_status_lbl = tk.Label(acs, textvariable=self.autoclick_status_var,
                                   font=("Courier New",13,"bold"), bg=CARD, fg=ACCENT)
        self.autoclick_status_lbl.pack(anchor="w")

        # Autoclicker buttons
        self.autoclick_btn = tk.Button(autoclicker_tab, text="▶  START AUTOCLICKER",
            font=("Courier New",11,"bold"), bg="#2a5a2a", fg="#00ff88",
            relief="flat", cursor="hand2", activebackground="#3a6a3a",
            command=self._start_autoclicker, height=2)
        self.autoclick_btn.pack(fill="x", padx=0, pady=5)

        self.autoclicker_stop_btn = tk.Button(autoclicker_tab, text="■  STOP AUTOCLICKER",
            font=("Courier New",11,"bold"), bg="#333", fg=DIM,
            relief="flat", cursor="hand2", activebackground="#444", activeforeground=TEXT,
            command=self._stop_autoclicker, height=2, state="disabled")
        self.autoclicker_stop_btn.pack(fill="x", padx=0, pady=5)

        self._sep_frame(autoclicker_tab)

        # PANIC SHUTDOWN BUTTON - Round E-Stop style
        panic_container = tk.Frame(autoclicker_tab, bg=BG)
        panic_container.pack(fill="x", padx=40, pady=10)
        self.panic_btn = tk.Button(panic_container, text="🛑",
            font=("Arial", 80), bg="#ff0000", fg="#ff0000",
            relief="raised", cursor="hand2", activebackground="#cc0000", activeforeground="#ffff00",
            command=self._panic_shutdown, height=1, width=3, bd=8)
        self.panic_btn.pack(expand=True)
        
        tk.Label(autoclicker_tab, text="PANIC SHUTDOWN",
                 font=("Courier New", 12, "bold"), bg=BG, fg="#ff0000").pack(pady=(0,2))
        self.panic_label = tk.Label(autoclicker_tab, text=f"Press {self.hotkeys['panic'].upper()} or click the big red button",
                 font=("Courier New", 9), bg=BG, fg="#ff0000")
        self.panic_label.pack()

        # ═══════════════════════════════════════════════════════════════════════
        # RANDOMIZED TAB
        # ═══════════════════════════════════════════════════════════════════════

        # Randomization settings
        rand_card = tk.Frame(randomized_tab, bg=CARD, pady=12, padx=16)
        rand_card.pack(fill="x", padx=0, pady=(0,10))
        
        tk.Label(rand_card, text="RANDOMIZED INPUTS SETTINGS",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        # Min/Max delays
        delay_row1 = tk.Frame(rand_card, bg=CARD)
        delay_row1.pack(fill="x", pady=4)
        tk.Label(delay_row1, text="Min delay (ms):", font=FONT, bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
        self.rand_min_delay_var = tk.StringVar(value="50")
        vcmd_int = (self.register(lambda v: v.isdigit() or v == ""), "%P")
        tk.Entry(delay_row1, textvariable=self.rand_min_delay_var, font=FONT, width=8,
                 bg="#2a2a2a", fg=ACCENT, insertbackground=ACCENT, relief="flat",
                 validate="key", validatecommand=vcmd_int).pack(side="left")

        delay_row2 = tk.Frame(rand_card, bg=CARD)
        delay_row2.pack(fill="x", pady=4)
        tk.Label(delay_row2, text="Max delay (ms):", font=FONT, bg=CARD, fg=TEXT, width=16, anchor="w").pack(side="left")
        self.rand_max_delay_var = tk.StringVar(value="200")
        tk.Entry(delay_row2, textvariable=self.rand_max_delay_var, font=FONT, width=8,
                 bg="#2a2a2a", fg=ACCENT, insertbackground=ACCENT, relief="flat",
                 validate="key", validatecommand=vcmd_int).pack(side="left")

        self._sep_frame(randomized_tab)

        # Button selection for randomization
        buttons_card = tk.Frame(randomized_tab, bg=CARD, pady=12, padx=16)
        buttons_card.pack(fill="x", padx=0, pady=(0,10))
        
        tk.Label(buttons_card, text="SELECT BUTTONS TO USE",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))
        
        buttons_frame = tk.Frame(buttons_card, bg=CARD)
        buttons_frame.pack(fill="x", pady=4)
        
        # Mouse buttons
        mouse_frame = tk.Frame(buttons_frame, bg=CARD)
        mouse_frame.pack(side="left", padx=(0,10))
        tk.Label(mouse_frame, text="Mouse Buttons:", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,4))
        
        self.rand_mouse_left_var = tk.BooleanVar(value=True)
        tk.Checkbutton(mouse_frame, text="Left Click", variable=self.rand_mouse_left_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_mouse_right_var = tk.BooleanVar(value=False)
        tk.Checkbutton(mouse_frame, text="Right Click", variable=self.rand_mouse_right_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_mouse_middle_var = tk.BooleanVar(value=False)
        tk.Checkbutton(mouse_frame, text="Middle Click", variable=self.rand_mouse_middle_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        # Keyboard buttons
        kb_frame = tk.Frame(buttons_frame, bg=CARD)
        kb_frame.pack(side="left", padx=(0,10))
        tk.Label(kb_frame, text="Keyboard Buttons:", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,4))
        
        self.rand_key_space_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="Space", variable=self.rand_key_space_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_key_enter_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="Enter", variable=self.rand_key_enter_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_key_a_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="A", variable=self.rand_key_a_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_key_w_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="W", variable=self.rand_key_w_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_key_d_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="D", variable=self.rand_key_d_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")
        
        self.rand_key_s_var = tk.BooleanVar(value=False)
        tk.Checkbutton(kb_frame, text="S", variable=self.rand_key_s_var,
                       font=FONT, bg=CARD, fg=TEXT, selectcolor="#2a2a2a",
                       activebackground=CARD, activeforeground=ACCENT).pack(anchor="w")

        self._sep_frame(randomized_tab)

        # Randomized playback status
        rps = tk.Frame(randomized_tab, bg=CARD, pady=12, padx=16)
        rps.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(rps, text="STATUS", font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w")
        self.randomized_status_var = tk.StringVar(value="Idle")
        self.randomized_status_lbl = tk.Label(rps, textvariable=self.randomized_status_var,
                                   font=("Courier New",13,"bold"), bg=CARD, fg=ACCENT)
        self.randomized_status_lbl.pack(anchor="w")

        # Randomized playback buttons
        self.randomized_btn = tk.Button(randomized_tab, text="▶  START RANDOMIZED",
            font=("Courier New",11,"bold"), bg="#2a5a2a", fg="#00ff88",
            relief="flat", cursor="hand2", activebackground="#3a6a3a",
            command=self._start_randomized, height=2, state="disabled")
        self.randomized_btn.pack(fill="x", padx=0, pady=5)

        self.randomized_stop_btn = tk.Button(randomized_tab, text="■  STOP RANDOMIZED",
            font=("Courier New",11,"bold"), bg="#333", fg=DIM,
            relief="flat", cursor="hand2", activebackground="#444", activeforeground=TEXT,
            command=self._stop_randomized, height=2, state="disabled")
        self.randomized_stop_btn.pack(fill="x", padx=0, pady=5)

        # ═══════════════════════════════════════════════════════════════════════
        # PROFILES TAB
        # ═══════════════════════════════════════════════════════════════════════

        # Create profiles directory
        self.profiles_dir = os.path.join(os.path.dirname(__file__), "profiles")
        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir)

        # Profile list
        plist_card = tk.Frame(profiles_tab, bg=CARD, pady=12, padx=16)
        plist_card.pack(fill="both", expand=True, padx=0, pady=(0,10))
        tk.Label(plist_card, text="SAVED PROFILES",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        # Scrollable profile list
        list_frame = tk.Frame(plist_card, bg="#2a2a2a", relief="flat", bd=0)
        list_frame.pack(fill="both", expand=True, pady=(0,8))

        scrollbar = tk.Scrollbar(list_frame, bg="#333", troughcolor="#1a1a1a")
        scrollbar.pack(side="right", fill="y")

        self.profiles_listbox = tk.Listbox(list_frame, bg="#2a2a2a", fg=ACCENT,
                                           font=("Courier New", 9), yscrollcommand=scrollbar.set,
                                           relief="flat", bd=0, height=10)
        self.profiles_listbox.pack(fill="both", expand=True)
        self.profiles_listbox.bind('<<ListboxSelect>>', self._on_profile_selected)
        scrollbar.config(command=self.profiles_listbox.yview)

        # Profile info
        self.profile_info_var = tk.StringVar(value="Select a profile")
        tk.Label(plist_card, textvariable=self.profile_info_var,
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(4,0))

        self._sep_frame(profiles_tab)

        # Save current recording as profile
        save_prof_card = tk.Frame(profiles_tab, bg=CARD, pady=12, padx=16)
        save_prof_card.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(save_prof_card, text="SAVE CURRENT RECORDING",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        input_frame = tk.Frame(save_prof_card, bg=CARD)
        input_frame.pack(fill="x", pady=(0,6))
        tk.Label(input_frame, text="Profile name:", font=FONT, bg=CARD, fg=TEXT).pack(side="left", padx=(0,6))
        self.profile_name_entry = tk.Entry(input_frame, font=FONT, width=20,
                                           bg="#2a2a2a", fg=ACCENT, insertbackground=ACCENT, relief="flat")
        self.profile_name_entry.pack(side="left", fill="x", expand=True)

        tk.Button(save_prof_card, text="💾  Save as Profile", font=FONT,
                  bg="#1e3a2a", fg=ACCENT, relief="flat", cursor="hand2",
                  command=self._save_profile, padx=10, pady=6).pack(fill="x")

        self._sep_frame(profiles_tab)

        # Profile management
        mgmt_card = tk.Frame(profiles_tab, bg=CARD, pady=12, padx=16)
        mgmt_card.pack(fill="x", padx=0, pady=(0,10))
        tk.Label(mgmt_card, text="PROFILE MANAGEMENT",
                 font=("Courier New",8), bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))

        btn_frame = tk.Frame(mgmt_card, bg=CARD)
        btn_frame.pack(fill="x")
        tk.Button(btn_frame, text="📂  Load", font=FONT,
                  bg="#1e2a3a", fg="#4488ff", relief="flat", cursor="hand2",
                  command=self._load_profile, padx=10, pady=6).pack(side="left", expand=True, fill="x", padx=(0,5))
        tk.Button(btn_frame, text="🗑️  Delete", font=FONT,
                  bg="#3a1e1e", fg="#ff6666", relief="flat", cursor="hand2",
                  command=self._delete_profile, padx=10, pady=6).pack(side="left", expand=True, fill="x")

        # Refresh profiles list on startup
        self._refresh_profiles_list()

    def _sep_frame(self, parent):
        """Separator line"""
        tk.Frame(parent, bg="#222", height=1).pack(fill="x", padx=0, pady=8)

    def _sep(self):
        """Separator line for backward compatibility"""
        tk.Frame(self, bg="#222", height=1).pack(fill="x", padx=20, pady=8)

    # ── Hotkey rebinding ───────────────────────────────────────────────────────

    def _start_rebind(self, action):
        """Start listening for a new key for the given action slot."""
        self._listening_for = action
        self._hk_buttons[action].config(text="Press a key...", fg="#ffaa00")
        self.rebind_label.config(text=f"Waiting for new key for '{action}'... press any key")
        # Grab next keypress via pynput (non-blocking)
        self._rebind_listener = pynput_keyboard.Listener(on_press=self._on_rebind_key)
        self._rebind_listener.start()

    def _on_rebind_key(self, key):
        """Called when user presses a key during rebind."""
        if self._listening_for is None:
            return False

        try:
            key_name = key.char if key.char else str(key).replace("Key.", "")
        except AttributeError:
            key_name = str(key).replace("Key.", "")

        action = self._listening_for
        self._listening_for = None
        self._rebind_listener.stop()

        # Check for conflicts
        conflict = None
        for a, k in self.hotkeys.items():
            if k == key_name and a != action:
                conflict = a
                break

        def update():
            if conflict:
                self.rebind_label.config(
                    text=f"'{key_name.upper()}' already used for '{conflict}'! Choose another.")
                colors = {"record": "#ff4444", "stop": "#ffaa00", "play": "#00ff88", "panic": "#ff0000"}
                self._hk_buttons[action].config(
                    text=self.hotkeys[action].upper(), fg=colors[action])
            else:
                self.hotkeys[action] = key_name
                self.recorder.hotkeys = set(self.hotkeys.values())
                colors = {"record": "#ff4444", "stop": "#ffaa00", "play": "#00ff88", "panic": "#ff0000"}
                self._hk_buttons[action].config(text=key_name.upper(), fg=colors[action])
                self.rebind_label.config(text=f"✓ '{action}' bound to {key_name.upper()}")
                # Update panic button label if panic hotkey was changed
                if action == "panic" and hasattr(self, 'panic_label'):
                    self.panic_label.config(text=f"Press {key_name.upper()} to panic shutdown")
                self._register_hotkeys()

        self.after(0, update)
        return False  # stop listener

    def _register_hotkeys(self):
        """Clear and re-register all hotkeys."""
        for hk in self._registered:
            try:
                kb.remove_hotkey(hk)
            except Exception:
                pass
        self._registered = []
        try:
            self._registered.append(kb.add_hotkey(self.hotkeys["record"], lambda: self.after(0, self._on_record_hotkey)))
            self._registered.append(kb.add_hotkey(self.hotkeys["stop"],   lambda: self.after(0, self._stop_all)))
            self._registered.append(kb.add_hotkey(self.hotkeys["play"],   lambda: self.after(0, self._play)))
            self._registered.append(kb.add_hotkey(self.hotkeys["panic"],  lambda: self.after(0, self._panic_shutdown)))
        except Exception as e:
            print(f"Hotkey registration error: {e}")

    # ── Recorder controls ──────────────────────────────────────────────────────

    def _on_record_hotkey(self):
        """Handle record hotkey - stop autoclicker if running, else toggle record"""
        if self.autoclicker_running:
            self._stop_autoclicker()
        else:
            self._toggle_record()

    def _panic_shutdown(self):
        """Emergency shutdown - stop everything"""
        self.recorder.playing = False
        self.recorder.recording = False
        if self.recorder._kb_listener:
            try:
                self.recorder._kb_listener.stop()
            except:
                pass
        if self.recorder._mouse_listener:
            try:
                self.recorder._mouse_listener.stop()
            except:
                pass
        self.autoclicker_running = False
        self._stop_autoclicker()
        self._stop_recording_only()
        self._set_status("PANIC!", "#ff0000")

    def _set_status(self, text, color="#00ff88"):
        self.status_var.set(text)
        self.status_lbl.config(fg=color)

    def _update_count(self):
        n = len(self.recorder.events)
        self.count_var.set(f"{n} event{'s' if n!=1 else ''} recorded")

    def _toggle_record(self):
        if self.recorder.recording:
            self._stop_recording_only()
        else:
            self.recorder.start_recording()
            self.recorder.on_event_recorded = self._on_event_recorded  # Set callback
            rec_key = self.hotkeys["record"].upper()
            stp_key = self.hotkeys["stop"].upper()
            self.rec_btn.config(text=f"⬤  RECORDING... ({stp_key} to stop)", bg="#ff6666")
            self.stop_btn.config(state="normal", bg="#555", fg="white")
            self.play_btn.config(state="disabled")
            self.randomized_btn.config(state="disabled")
            self._set_status("Recording...", "#ff4444")
            self._clear_preview()
            self._poll()

    def _poll(self):
        if self.recorder.recording:
            self._update_count()
            self.after(500, self._poll)

    def _stop_recording_only(self):
        if not self.recorder.recording:
            return
        self.recorder.stop_recording()
        self.rec_btn.config(text="⬤  RECORD", bg="#ff4444")
        self.stop_btn.config(state="disabled", bg="#333", fg="#555")
        self._update_count()
        n = len(self.recorder.events)
        if n > 0:
            self.play_btn.config(state="normal")
            self.randomized_btn.config(state="normal")
            self._set_status(f"Ready · {n} events", "#00ff88")
        else:
            self.play_btn.config(state="disabled")
            self.randomized_btn.config(state="disabled")
            self._set_status("Idle", "#00ff88")

    def _stop_all(self):
        self._stop_recording_only()
        if self.recorder.playing:
            self.recorder.stop_playback()
            self._set_status("Stopped", "#00ff88")
            self.stop_btn.config(state="disabled", bg="#333", fg="#555")
            self.play_btn.config(state="normal" if self.recorder.events else "disabled")
            self.randomized_btn.config(state="normal" if self.recorder.events else "disabled")
            self.rec_btn.config(state="normal")

    def _toggle_loop(self):
        self.repeat_var.set("0" if self.loop_var.get() else "1")

    def _update_record_options(self):
        """Update the recorder's recording options"""
        self.recorder.record_keyboard = self.record_kb_var.get()
        self.recorder.record_mouse = self.record_mouse_var.get()
        if not (self.recorder.record_keyboard or self.recorder.record_mouse):
            messagebox.showwarning("Warning", "Select at least one input type (keyboard or mouse)")
            self.record_kb_var.set(True)
            self.recorder.record_keyboard = True

    def _toggle_autoclicker(self):
        """Toggle autoclicker on/off (deprecated - kept for compatibility)"""
        pass

    def _on_event_recorded(self, description):
        """Called when an event is recorded - updates preview"""
        self.preview_listbox.insert(tk.END, description)
        self.preview_listbox.see(tk.END)  # Auto-scroll to end

    def _clear_preview(self):
        """Clear the recording preview"""
        self.preview_listbox.delete(0, tk.END)

    def _toggle_preview_visibility(self):
        """Toggle the recording preview visibility"""
        if self.preview_visible.get():
            self.prev_card.pack(fill="x", padx=0, pady=(0,10), after=self.prev_header)
        else:
            self.prev_card.pack_forget()

    # ── Profile Management ─────────────────────────────────────────────────────

    def _refresh_profiles_list(self):
        """Refresh the profiles listbox"""
        self.profiles_listbox.delete(0, tk.END)
        if not os.path.exists(self.profiles_dir):
            os.makedirs(self.profiles_dir)
        
        profiles = [f[:-5] for f in os.listdir(self.profiles_dir) if f.endswith(".json")]
        profiles.sort()
        
        for profile in profiles:
            self.profiles_listbox.insert(tk.END, profile)
        
        if not profiles:
            self.profile_info_var.set("No profiles saved yet")

    def _on_profile_selected(self, event):
        """Called when a profile is selected in the listbox"""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        
        profile_name = self.profiles_listbox.get(selection[0])
        profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        
        try:
            with open(profile_path, "r") as f:
                events = json.load(f)
            num_events = len(events)
            self.profile_info_var.set(f"📊 {profile_name}: {num_events} events")
        except:
            self.profile_info_var.set(f"Profile: {profile_name}")

    def _save_profile(self):
        """Save current recording as a named profile"""
        if not self.recorder.events:
            messagebox.showwarning("Nothing to save", "Record a macro first.")
            return
        
        profile_name = self.profile_name_entry.get().strip()
        if not profile_name:
            messagebox.showwarning("Empty name", "Enter a profile name.")
            return
        
        # Sanitize filename
        profile_name = "".join(c for c in profile_name if c.isalnum() or c in "-_ ")
        if not profile_name:
            messagebox.showwarning("Invalid name", "Profile name contains invalid characters.")
            return
        
        profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        
        if os.path.exists(profile_path):
            if not messagebox.askyesno("Profile exists", f"Overwrite profile '{profile_name}'?"):
                return
        
        try:
            with open(profile_path, "w") as f:
                json.dump(self.recorder.events, f, indent=2)
            messagebox.showinfo("Saved", f"Profile '{profile_name}' saved!")
            self.profile_name_entry.delete(0, tk.END)
            self._refresh_profiles_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save profile: {e}")

    def _load_profile(self):
        """Load a selected profile"""
        selection = self.profiles_listbox.curselection()
        if not selection:
            messagebox.showwarning("No selection", "Select a profile to load.")
            return
        
        profile_name = self.profiles_listbox.get(selection[0])
        profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        
        try:
            with open(profile_path, "r") as f:
                self.recorder.events = json.load(f)
            self._update_count()
            self.play_btn.config(state="normal")
            self.randomized_btn.config(state="normal")
            self._set_status(f"Loaded profile: {profile_name}", "#00ff88")
            self.profile_info_var.set(f"✓ Loaded: {profile_name} ({len(self.recorder.events)} events)")
            messagebox.showinfo("Loaded", f"Profile '{profile_name}' loaded!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load profile: {e}")

    def _delete_profile(self):
        """Delete a selected profile"""
        selection = self.profiles_listbox.curselection()
        if not selection:
            messagebox.showwarning("No selection", "Select a profile to delete.")
            return
        
        profile_name = self.profiles_listbox.get(selection[0])
        if not messagebox.askyesno("Confirm delete", f"Delete profile '{profile_name}'?"):
            return
        
        profile_path = os.path.join(self.profiles_dir, f"{profile_name}.json")
        try:
            os.remove(profile_path)
            messagebox.showinfo("Deleted", f"Profile '{profile_name}' deleted!")
            self._refresh_profiles_list()
            self.profile_info_var.set("Profile deleted")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete profile: {e}")

    def _start_autoclicker(self):
        """Start the autoclicker"""
        if self.autoclicker_running:
            return
        
        try:
            delay = int(self.click_delay_var.get()) / 1000.0  # Convert ms to seconds
            button = self.mouse_button_var.get()
            self.autoclicker_running = True
            self._run_autoclicker(delay, button)
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "Please enter a valid delay value in milliseconds")
            self.autoclicker_running = False

    def _stop_autoclicker(self):
        """Stop the autoclicker"""
        self.autoclicker_running = False
        self.autoclick_btn.config(state="normal")
        self.autoclicker_stop_btn.config(state="disabled")
        self.autoclick_status_var.set("Stopped")
        self.autoclick_status_lbl.config(fg="#ffaa00")

    def _run_autoclicker(self, delay, button):
        """Run the autoclicker"""
        def click_loop():
            self.autoclick_btn.config(state="disabled")
            self.autoclicker_stop_btn.config(state="normal")
            self.autoclick_status_var.set("Running...")
            self.autoclick_status_lbl.config(fg="#00ff88")
            mouse = pynput_mouse.Controller()
            start_time = time.time()
            
            try:
                while self.autoclicker_running:
                    # Fixed button clicking
                    if button == "left":
                        mouse.click(pynput_mouse.Button.left)
                        print(f"[DEBUG] Left click")
                    elif button == "right":
                        mouse.click(pynput_mouse.Button.right)
                        print(f"[DEBUG] Right click")
                    elif button == "middle":
                        mouse.click(pynput_mouse.Button.middle)
                        print(f"[DEBUG] Middle click")
                    
                    time.sleep(delay)
                    
                    # Check if we've exceeded a reasonable time limit (prevent infinite clicking)
                    if time.time() - start_time > 3600:  # 1 hour max
                        break
            except Exception as e:
                print(f"[ERROR] Autoclicker error: {e}")
            finally:
                self.autoclicker_running = False
                self.after(0, lambda: self.autoclick_btn.config(state="normal"))
                self.after(0, lambda: self.autoclicker_stop_btn.config(state="disabled"))
                self.after(0, lambda: self.autoclick_status_var.set("Idle"))
                self.after(0, lambda: self.autoclick_status_lbl.config(fg="#00ff88"))

        threading.Thread(target=click_loop, daemon=True).start()

    def _start_randomized(self):
        """Start randomized input playback"""
        if self.randomized_playing:
            return
        
        try:
            min_delay = int(self.rand_min_delay_var.get()) / 1000.0
            max_delay = int(self.rand_max_delay_var.get()) / 1000.0
            
            if min_delay < 0 or max_delay < 0 or min_delay > max_delay:
                messagebox.showerror("Invalid input", "Min delay must be less than or equal to max delay, and both must be positive")
                return
            
            # Check that at least one button is selected
            selected = []
            if self.rand_mouse_left_var.get():
                selected.append(("mouse", "left"))
            if self.rand_mouse_right_var.get():
                selected.append(("mouse", "right"))
            if self.rand_mouse_middle_var.get():
                selected.append(("mouse", "middle"))
            if self.rand_key_space_var.get():
                selected.append(("key", "space"))
            if self.rand_key_enter_var.get():
                selected.append(("key", "return"))
            if self.rand_key_a_var.get():
                selected.append(("key", "a"))
            if self.rand_key_w_var.get():
                selected.append(("key", "w"))
            if self.rand_key_d_var.get():
                selected.append(("key", "d"))
            if self.rand_key_s_var.get():
                selected.append(("key", "s"))
            
            if not selected:
                messagebox.showerror("No selection", "Select at least one button to randomize")
                return
            
            self.randomized_playing = True
            self._run_randomized(min_delay, max_delay, selected)
        except ValueError:
            messagebox.showerror("Invalid input", "Please enter valid delay values in milliseconds")
            self.randomized_playing = False

    def _stop_randomized(self):
        """Stop randomized input playback"""
        self.randomized_playing = False
        self.randomized_btn.config(state="normal")
        self.randomized_stop_btn.config(state="disabled")
        self.randomized_status_var.set("Stopped")
        self.randomized_status_lbl.config(fg="#ffaa00")

    def _run_randomized(self, min_delay, max_delay, selected_buttons):
        """Run randomized input playback"""
        def random_loop():
            self.randomized_btn.config(state="disabled")
            self.randomized_stop_btn.config(state="normal")
            self.randomized_status_var.set("Running...")
            self.randomized_status_lbl.config(fg="#00ff88")
            mouse = pynput_mouse.Controller()
            start_time = time.time()
            
            try:
                while self.randomized_playing:
                    # Pick random button and delay
                    current_delay = random.uniform(min_delay, max_delay)
                    button_type, button_name = random.choice(selected_buttons)
                    
                    if button_type == "mouse":
                        if button_name == "left":
                            mouse.click(pynput_mouse.Button.left)
                            print(f"[DEBUG] Randomized left click")
                        elif button_name == "right":
                            mouse.click(pynput_mouse.Button.right)
                            print(f"[DEBUG] Randomized right click")
                        elif button_name == "middle":
                            mouse.click(pynput_mouse.Button.middle)
                            print(f"[DEBUG] Randomized middle click")
                    elif button_type == "key":
                        send_key(button_name, key_up=False)
                        time.sleep(0.05)
                        send_key(button_name, key_up=True)
                        print(f"[DEBUG] Randomized key press: {button_name}")
                    
                    time.sleep(current_delay)
                    
                    # Check if we've exceeded a reasonable time limit (prevent infinite clicking)
                    if time.time() - start_time > 3600:  # 1 hour max
                        break
            except Exception as e:
                print(f"[ERROR] Randomized playback error: {e}")
            finally:
                self.randomized_playing = False
                self.after(0, lambda: self.randomized_btn.config(state="normal"))
                self.after(0, lambda: self.randomized_stop_btn.config(state="disabled"))
                self.after(0, lambda: self.randomized_status_var.set("Idle"))
                self.after(0, lambda: self.randomized_status_lbl.config(fg="#00ff88"))

        threading.Thread(target=random_loop, daemon=True).start()

    def _play(self):
        if not self.recorder.events or self.recorder.playing:
            return
        try:
            speed  = float(self.speed_var.get())
            repeat = int(self.repeat_var.get()) if self.repeat_var.get() else 1
        except ValueError:
            speed, repeat = 1.0, 1

        self.play_btn.config(state="disabled")
        self.randomized_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.stop_btn.config(state="normal", bg="#555", fg="white")
        self._set_status("Playing...", "#ffaa00")

        def run():
            self.recorder.play(speed=speed, repeat=repeat,
                status_cb=lambda s: self.after(0, lambda: self._set_status(s, "#ffaa00")))
            self.after(0, self._on_done)

        threading.Thread(target=run, daemon=True).start()

    def _on_done(self):
        self.play_btn.config(state="normal" if self.recorder.events else "disabled")
        self.randomized_btn.config(state="normal" if self.recorder.events else "disabled")
        self.rec_btn.config(state="normal")
        self.stop_btn.config(state="disabled", bg="#333", fg="#555")
        self._set_status("Ready", "#00ff88")

    def _save(self):
        if not self.recorder.events:
            messagebox.showwarning("Nothing to save", "Record a macro first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("Macro files","*.json")])
        if path:
            self.recorder.save(path)
            messagebox.showinfo("Saved", f"Saved to {path}")

    def _load(self):
        path = filedialog.askopenfilename(filetypes=[("Macro files","*.json")])
        if path:
            self.recorder.load(path)
            self._update_count()
            self.play_btn.config(state="normal")
            self.randomized_btn.config(state="normal")
            self._set_status(f"Loaded · {len(self.recorder.events)} events", "#00ff88")


if __name__ == "__main__":
    app = App()
    app.mainloop()