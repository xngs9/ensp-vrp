import ctypes
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import ensp_vrp_ime_helper as helper


user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_window(title_part):
    needle = title_part.lower()
    found = []

    @EnumWindowsProc
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 512)
            user32.GetClassNameW(hwnd, cls, 256)
            if needle in title.value.lower():
                found.append((hwnd, title.value, cls.value))
                return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


app = helper.App(hook_smoke_test=False)
app.current_view = "user-view"


def drive():
    if not app.keyboard.installed.wait(timeout=5) or not app.keyboard.hook:
        print("keyboard hook not installed", app.keyboard.install_error)
        return
    target = find_window("LSW6")
    if not target:
        print("LSW6 window not found")
        return
    hwnd, title, cls = target
    print("focused", title, cls)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.8)
    app.buffer = ""
    app.items = []
    app.page = 0
    app.send_text("dis")


app.root.after(1000, lambda: threading.Thread(target=drive, daemon=True).start())
app.run()
