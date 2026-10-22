import time
import json
import os
import queue
import colorsys
import winsound
import threading
import tkinter as tk
from tkinter import ttk, simpledialog
import ctypes
from ctypes import wintypes
from pynput import mouse, keyboard

user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001

ULONG_PTR = ctypes.POINTER(wintypes.ULONG)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", _INPUTunion),
    ]


def move_raw(dx, dy):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = dx
    inp.union.mi.dy = dy
    inp.union.mi.mouseData = 0
    inp.union.mi.dwFlags = MOUSEEVENTF_MOVE
    inp.union.mi.time = 0
    inp.union.mi.dwExtraInfo = None
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


SPEED_MAX = 2000.0
speed = float(int(user32.GetSystemMetrics(0) / 16))
left_down = False
right_down = False
enabled = False
running = True
capturing = False
toggle_key = keyboard.Key.f8
ui_queue = queue.Queue()

SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antirecoil-kbmGUI_saves.json")
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "antirecoil-kbmGUI_settings.json")


def key_to_str(key):
    if isinstance(key, keyboard.Key):
        return "key:" + key.name
    if key.char is not None:
        return "char:" + key.char
    return "vk:" + str(key.vk)


def str_to_key(s):
    try:
        if s.startswith("key:"):
            return keyboard.Key[s[4:]]
        if s.startswith("char:"):
            return keyboard.KeyCode.from_char(s[5:])
        if s.startswith("vk:"):
            return keyboard.KeyCode.from_vk(int(s[3:]))
    except Exception:
        pass
    return keyboard.Key.f8


def load_settings():
    global toggle_key
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            toggle_key = str_to_key(data.get("toggle_key", "key:f8"))
    except Exception:
        pass


def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"toggle_key": key_to_str(toggle_key)}, f, indent=2)


def load_saves():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_saves(data):
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def on_click(x, y, button, pressed):
    global left_down, right_down
    if button == mouse.Button.left:
        left_down = pressed
    elif button == mouse.Button.right:
        right_down = pressed


def play_toggle_sound(enabled):
    freq = 1000 if enabled else 600
    threading.Thread(target=lambda: winsound.Beep(freq, 150), daemon=True).start()


def on_press(key):
    global speed, enabled, running, toggle_key, capturing
    if capturing:
        toggle_key = key
        capturing = False
        save_settings()
        ui_queue.put(key)
        print("Toggle key set to", key_to_str(toggle_key), flush=True)
        return
    if key == toggle_key:
        enabled = not enabled
        play_toggle_sound(enabled)
        print("TOGGLE ->", "ON" if enabled else "OFF", flush=True)
    elif key == keyboard.Key.up:
        speed = min(SPEED_MAX, speed + 50)
        print(f"speed {speed}", flush=True)
    elif key == keyboard.Key.down:
        speed = max(1.0, speed - 50)
        print(f"speed {speed}", flush=True)
    elif key == keyboard.Key.f9:
        running = False
        return False


# ---------------- GUI ----------------
root = tk.Tk()
root.title("AntiRecoil KBM — RGB")
root.geometry("520x520")
root.configure(bg="#0a0a0f")

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass
style.configure("TNotebook", background="#0a0a0f", borderwidth=0)
style.configure("TNotebook.Tab", background="#1f1f2f", foreground="white", padding=[14, 6], font=("Arial", 10, "bold"))
style.map("TNotebook.Tab", background=[("selected", "#3a3a55")])

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

hue = 0.0
saves = load_saves()
current_name = "strength-1"


def set_speed(v):
    global speed
    speed = max(1.0, min(SPEED_MAX, float(v)))


def rgb_hex(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1.0, 1.0)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


# ---------------- Tab 1: Controls ----------------
tab_controls = ttk.Frame(notebook)
notebook.add(tab_controls, text="CONTROLS")

canvas = tk.Canvas(tab_controls, highlightthickness=0, bg="#0a0a0f")
canvas.pack(side="top", fill="both", expand=True)

control_bar = tk.Frame(tab_controls, bg="#0a0a0f")
control_bar.pack(side="bottom", fill="x")


def draw():
    global hue
    hue = (hue + 0.004) % 1.0
    w = canvas.winfo_width()
    h = canvas.winfo_height()
    canvas.delete("all")
    canvas.create_rectangle(0, 0, w, h, fill="#0a0a0f", outline=rgb_hex(hue), width=4)
    cx = max(w // 2, 200)

    status = "ENABLED" if enabled else "DISABLED"
    canvas.create_text(cx, 70, text="ANTIRECOIL  KBM", fill="white", font=("Arial", 20, "bold"))
    canvas.create_text(cx, 100, text=f"[ {status} ]   (toggle: {key_to_str(toggle_key)}, F9 quit)",
                       fill=rgb_hex((hue + 0.33) % 1.0),
                       font=("Arial", 12, "bold"))

    frac = max(0.0, min(1.0, speed / SPEED_MAX))
    bar_w, bar_h = 300, 40
    bx = cx - bar_w // 2
    by = 150
    canvas.create_text(cx, 130, text=f"STRENGTH: {int(speed)}", fill="white", font=("Arial", 15, "bold"))
    canvas.create_rectangle(bx, by, bx + bar_w, by + bar_h, outline="white", width=2)
    canvas.create_rectangle(bx, by, bx + int(bar_w * frac), by + bar_h,
                            fill=rgb_hex((hue + 0.33) % 1.0), outline="")

    names = list(saves.keys())
    canvas.create_text(cx, 220, text="SAVED STRENGTHS  (double-click to load)", fill="white", font=("Arial", 12, "bold"))
    y0 = 245
    for i, nm in enumerate(names):
        c = rgb_hex((hue + i * 0.1) % 1.0)
        canvas.create_rectangle(cx - 90, y0 + i * 30, cx + 90, y0 + i * 30 + 26, fill=c, outline="", tags=(f"saved{i}",))
        canvas.create_text(cx, y0 + i * 30 + 13, text=f"{nm}: {int(saves[nm])}", fill="#000",
                           font=("Arial", 9, "bold"), tags=(f"saved{i}",))


def on_canvas_double(event):
    item = canvas.find_closest(event.x, event.y)
    if not item:
        return
    for tag in canvas.gettags(item[0]):
        if tag.startswith("saved"):
            idx = int(tag[5:])
            names = list(saves.keys())
            if idx < len(names):
                apply_strength(names[idx])
            return


canvas.bind("<Double-Button-1>", on_canvas_double)


def apply_strength(nm):
    global current_name
    if nm not in saves:
        return
    set_speed(saves[nm])
    current_name = nm
    speed_slider.set(speed)
    speed_entry.delete(0, "end")
    speed_entry.insert(0, f"{int(speed)}")
    print(f"Loaded '{nm}' = {int(speed)}", flush=True)


def slider_changed(v):
    set_speed(float(v))


def entry_apply():
    try:
        val = float(speed_entry.get())
    except ValueError:
        return
    set_speed(val)
    speed_slider.set(speed)


def do_save():
    global current_name
    nm = simpledialog.askstring("Save Strength", "Label for this strength:", initialvalue=current_name, parent=root)
    if nm:
        saves[nm] = speed
        save_saves(saves)
        current_name = nm
        refresh_saves()
        print(f"Saved strength {int(speed)} as '{nm}'", flush=True)


speed_slider = tk.Scale(control_bar, from_=0, to=SPEED_MAX, orient="horizontal", length=280,
                        command=slider_changed, showvalue=True,
                        bg="#0a0a0f", fg="white", troughcolor="#1f1f2f", highlightthickness=0,
                        label="SPEED", sliderrelief="raised", sliderlength=24)
speed_slider.set(speed)
speed_slider.pack(side="left", padx=10, pady=6)

speed_entry = tk.Entry(control_bar, width=7, bg="#1f1f2f", fg="white", insertbackground="white",
                       font=("Arial", 12, "bold"), justify="center")
speed_entry.insert(0, f"{int(speed)}")
speed_entry.pack(side="left", padx=4)

apply_btn = tk.Button(control_bar, text="SET", command=entry_apply, bg="#1f1f2f", fg="white",
                      font=("Arial", 10, "bold"), activebackground="#3a3a55")
apply_btn.pack(side="left", padx=4)

save_btn = tk.Button(control_bar, text="SAVE STRENGTH", command=do_save, bg="#1f1f2f", fg="white",
                     font=("Arial", 10, "bold"), activebackground="#3a3a55")
save_btn.pack(side="left", padx=8)

# ---------------- Tab 2: Saved Strengths ----------------
tab_saved = ttk.Frame(notebook)
notebook.add(tab_saved, text="SAVED STRENGTHS")

saved_canvas = tk.Canvas(tab_saved, highlightthickness=0, bg="#0a0a0f")
saved_canvas.pack(side="top", fill="both", expand=True)

saved_bar = tk.Frame(tab_saved, bg="#0a0a0f")
saved_bar.pack(side="bottom", fill="x")

listbox = tk.Listbox(saved_canvas, bg="#12121a", fg="white", selectbackground="#3a3a55",
                     font=("Courier", 12, "bold"), highlightthickness=0)
listbox.pack(side="left", fill="both", expand=True, padx=10, pady=10)


def refresh_saves():
    listbox.delete(0, "end")
    for nm in list(saves.keys()):
        listbox.insert("end", f"{nm}  ->  {int(saves[nm])}")


def load_selected():
    sel = listbox.curselection()
    if not sel:
        return
    apply_strength(list(saves.keys())[sel[0]])


def delete_selected():
    sel = listbox.curselection()
    if not sel:
        return
    nm = list(saves.keys())[sel[0]]
    del saves[nm]
    save_saves(saves)
    refresh_saves()
    print(f"Deleted '{nm}'", flush=True)


def rename_selected():
    sel = listbox.curselection()
    if not sel:
        return
    nm = list(saves.keys())[sel[0]]
    new = simpledialog.askstring("Rename", "New label:", initialvalue=nm, parent=root)
    if new and new != nm:
        saves[new] = saves.pop(nm)
        save_saves(saves)
        refresh_saves()
        print(f"Renamed '{nm}' -> '{new}'", flush=True)


load_btn = tk.Button(saved_bar, text="LOAD", command=load_selected, bg="#1f1f2f", fg="white",
                     font=("Arial", 10, "bold"), activebackground="#3a3a55")
load_btn.pack(side="left", padx=6, pady=6)

del_btn = tk.Button(saved_bar, text="DELETE", command=delete_selected, bg="#1f1f2f", fg="white",
                    font=("Arial", 10, "bold"), activebackground="#3a3a55")
del_btn.pack(side="left", padx=4)

rename_btn = tk.Button(saved_bar, text="RENAME", command=rename_selected, bg="#1f1f2f", fg="white",
                       font=("Arial", 10, "bold"), activebackground="#3a3a55")
rename_btn.pack(side="left", padx=4)

refresh_saves()

# ---------------- Tab 3: Settings ----------------
load_settings()
tab_settings = ttk.Frame(notebook)
notebook.add(tab_settings, text="SETTINGS")

settings_frame = tk.Frame(tab_settings, bg="#0a0a0f")
settings_frame.pack(fill="both", expand=True, padx=20, pady=30)

toggle_key_label = tk.Label(settings_frame, text="TOGGLE KEY:  " + key_to_str(toggle_key),
                            bg="#0a0a0f", fg="white", font=("Arial", 16, "bold"))
toggle_key_label.pack(pady=(0, 20))

capture_hint = tk.Label(settings_frame, text="Click the button, then press any key.",
                        bg="#0a0a0f", fg="#888", font=("Arial", 10))
capture_hint.pack()


def begin_capture():
    global capturing
    capturing = True
    change_key_btn.config(state="disabled")
    capture_hint.config(text="Press any key to set as the new toggle...", fg=rgb_hex(0.5))


def end_capture():
    global capturing
    capturing = False
    change_key_btn.config(state="normal")
    capture_hint.config(text="Click the button, then press any key.", fg="#888")


change_key_btn = tk.Button(settings_frame, text="CHANGE TOGGLE KEY", command=begin_capture,
                           bg="#1f1f2f", fg="white", font=("Arial", 12, "bold"), activebackground="#3a3a55")
change_key_btn.pack(pady=(0, 10))


def gui_close():
    global running
    running = False
    end_capture()
    root.destroy()


root.protocol("WM_DELETE_WINDOW", gui_close)

mouse.Listener(on_click=on_click).start()
keyboard.Listener(on_press=on_press).start()

print(f"Running. Toggle={key_to_str(toggle_key)}, Up/Down=speed, F9=quit. GUI active.", flush=True)

dt = 1 / 120
last = time.perf_counter()
while running:
    try:
        try:
            while True:
                k = ui_queue.get_nowait()
                toggle_key_label.config(text="TOGGLE KEY:  " + key_to_str(k))
                change_key_btn.config(state="normal")
                capture_hint.config(text="Click the button, then press any key.", fg="#888")
        except queue.Empty:
            pass
        if enabled and right_down and left_down:
            move_raw(0, int(speed * dt))
        draw()
        root.update()
        elapsed = time.perf_counter() - last
        time.sleep(max(0.0, dt - elapsed))
        last = time.perf_counter()
    except tk.TclError:
        break

print("quit", flush=True)