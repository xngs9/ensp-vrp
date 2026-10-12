import ctypes
import queue
import re
import threading
import time
import tkinter as tk
from ctypes import wintypes

from ensp_vrp_ime_helper import App, CommandStore, Keyboard, app_dir


class Monitor:
    def __init__(self):
        self.root_dir = app_dir()
        self.store = CommandStore(self.root_dir)
        self.store.load()
        self.buffer = ""
        self.current_view = "user-view"
        self.events = queue.Queue()
        self.user32 = ctypes.windll.user32
        self.hook = Keyboard(self.on_key)

        self.root = tk.Tk()
        self.root.title("VRP 助手监视面板")
        self.root.attributes("-topmost", True)
        self.root.geometry("760x520+80+80")
        self.root.configure(bg="#fff5fa")

        tk.Label(self.root, text="VRP 助手监视面板", font=("Microsoft YaHei UI", 18, "bold"), bg="#fff5fa").pack(pady=(12, 4))
        self.status = tk.Label(self.root, text="", font=("Consolas", 12), anchor="w", justify="left", bg="#fff5fa")
        self.status.pack(fill="x", padx=16)
        self.text = tk.Text(self.root, font=("Consolas", 12), bg="#ffffff", fg="#222222", height=18)
        self.text.pack(fill="both", expand=True, padx=16, pady=12)
        self.text.insert("end", "等待你在 eNSP Console 里输入...\n")
        self.text.configure(state="disabled")

        self.root.after(80, self.render)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def on_key(self, vk):
        hwnd = self.user32.GetForegroundWindow()
        target = App.window_text(hwnd)
        is_target = App.is_target_hwnd(hwnd)
        if not is_target:
            self.events.put((time.time(), target, vk, self.buffer, []))
            return False

        if vk == Keyboard.VK_RETURN:
            if self.buffer.strip():
                self.current_view = self.infer_view(self.buffer.strip(), self.current_view)
            self.buffer = ""
        elif vk == Keyboard.VK_ESCAPE:
            pass
        elif vk == Keyboard.VK_BACK:
            self.buffer = self.buffer[:-1]
        elif vk in (Keyboard.VK_LEFT, Keyboard.VK_RIGHT):
            pass
        else:
            ch = self.vk_to_char(vk)
            if ch is not None:
                self.buffer = (self.buffer + ch)[-80:]

        items, pages, total = self.store.search(self.buffer, 0, self.current_view)
        self.events.put((time.time(), target, vk, self.buffer, items[:9]))
        return False

    @staticmethod
    def infer_view(command, current):
        from ensp_vrp_ime_helper import infer_view_after_enter

        return infer_view_after_enter(command, current)

    @staticmethod
    def vk_to_char(vk):
        if 0x41 <= vk <= 0x5A:
            return chr(vk).lower()
        if 0x30 <= vk <= 0x39:
            return chr(vk)
        mapping = {
            0x20: " ",
            0xBA: ":",
            0xBD: "-",
            0xBE: ".",
            0xBF: "/",
            0xE2: "\\",
        }
        return mapping.get(vk)

    def render(self):
        latest = []
        while True:
            try:
                latest.append(self.events.get_nowait())
            except queue.Empty:
                break
        if latest:
            stamp, target, vk, buf, items = latest[-1]
            self.status.configure(text=f"window={target}\nview={self.current_view}  vk={vk}  buffer=[{buf}]")
            lines = [f"{time.strftime('%H:%M:%S', time.localtime(stamp))}  buffer: {buf}", "候选:"]
            for idx, item in enumerate(items, 1):
                lines.append(f"{idx}. {item['command']}    -> {item['insert']}    [{item.get('replaceMode')}]")
            lines.append("")
            self.text.configure(state="normal")
            self.text.insert("end", "\n".join(lines) + "\n")
            self.text.see("end")
            content = self.text.get("1.0", "end")
            if content.count("\n") > 260:
                self.text.delete("1.0", "80.0")
            self.text.configure(state="disabled")
        self.root.after(80, self.render)

    def run(self):
        thread = threading.Thread(target=self.hook.start, daemon=True)
        thread.start()
        self.root.mainloop()


if __name__ == "__main__":
    Monitor().run()
