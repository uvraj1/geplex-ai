# launcher.py
"""Dedicated entrypoint for the standalone Windows portable launcher.

Handles:
- Immediate GUI splash screen creation using tkinter.
- Suppressing console stream crashes in windowed GUI mode via NullWriter.
- Spawning system tray icon via pystray and Pillow (lazy-loaded).
- Auto-opening default browser pointing to the running backend.
- Launching the FastAPI server (importing and running app.py).
"""
import os
import sys
import threading
import time
import webbrowser
import traceback

# Define a dummy NullWriter to suppress standard stream crashes (isatty etc.) in GUI mode
class NullWriter:
    def write(self, text):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()


splash_root = None


def _runtime_dir():
    return os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


def _prepare_application_data():
    """Keep packaged-app runtime data beside the application, not in source."""
    runtime_dir = _runtime_dir()
    data_dir = os.path.join(runtime_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    os.environ.setdefault("GEPLEX_DATA_DIR", data_dir)


def _show_startup_error(error):
    log_dir = os.path.join(os.path.expanduser("~"), ".geplex", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "launcher.log")
    with open(log_path, "a", encoding="utf-8") as log:
        log.write("\n" + traceback.format_exc() + "\n")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "GepLex could not start",
            f"{error}\n\nDetails were saved to:\n{log_path}",
        )
        root.destroy()
    except Exception:
        pass

# If running from a frozen PyInstaller bundle, launch the splash screen IMMEDIATELY
if getattr(sys, 'frozen', False):
    import tkinter as tk

    def show_splash_instantly():
        global splash_root
        try:
            splash_root = tk.Tk()
            splash_root.title("GepLex")
            splash_root.overrideredirect(True)
            splash_root.configure(bg="#111827")

            # Accented borders
            splash_root.config(highlightbackground="#8b5cf6", highlightcolor="#8b5cf6", highlightthickness=1)

            w, h = 430, 220
            ws = splash_root.winfo_screenwidth()
            hs = splash_root.winfo_screenheight()
            x = (ws - w) // 2
            y = (hs - h) // 2
            splash_root.geometry(f"{w}x{h}+{x}+{y}")

            tk.Label(splash_root, text="GepLex", font=("Segoe UI", 27, "bold"), bg="#111827", fg="#a78bfa").pack(pady=(24, 0))
            tk.Label(splash_root, text="Your intelligent workspace", font=("Segoe UI", 10), bg="#111827", fg="#67e8f9").pack(pady=(0, 13))
            tk.Label(splash_root, text="Preparing your private AI environment", font=("Segoe UI", 11), bg="#111827", fg="#e5e7eb").pack()
            bar = tk.Canvas(splash_root, width=320, height=6, bg="#243044", highlightthickness=0)
            bar.pack(pady=(18, 10))
            bar.create_rectangle(0, 0, 120, 6, fill="#8b5cf6", outline="")
            tk.Label(splash_root, text="Starting securely • This window will open automatically", font=("Segoe UI", 8), bg="#111827", fg="#94a3b8").pack()

            splash_root.attributes("-topmost", True)
            splash_root.mainloop()
        except Exception:
            pass

    # Launch the GUI splash screen immediately on a background thread
    threading.Thread(target=show_splash_instantly, daemon=True).start()


def create_tray_image():
    # Generate a compact 64x64 icon matching the GepLex violet/cyan brand palette.
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    accent_violet = (139, 92, 246, 255)
    accent_cyan = (34, 211, 238, 255)
    soft_violet = (168, 85, 247, 160)

    # Draw a G-shaped bot mark with a polished signal node.
    dc.arc((10, 10, 54, 54), 40, 320, fill=accent_violet, width=10)
    dc.line((46, 32, 46, 46), fill=accent_cyan, width=8)
    dc.arc((26, 26, 46, 46), 0, 360, fill=soft_violet, width=8)
    dc.ellipse((22, 38, 30, 46), fill=accent_cyan)
    return image


def on_open_browser(icon, item, url):
    webbrowser.open(url)


def on_exit(icon, item):
    icon.stop()
    os._exit(0)


def setup_system_tray(url):
    try:
        import pystray
        icon_img = create_tray_image()
        menu = (
            pystray.MenuItem('Open GepLex', lambda icon, item: on_open_browser(icon, item, url), default=True),
            pystray.MenuItem('Exit', on_exit)
        )
        tray_icon = pystray.Icon(
            "GepLex",
            icon_img,
            "GepLex",
            menu
        )
        tray_icon.run()
    except Exception:
        pass


def open_browser(url):
    # Allow uvicorn and app lifecycles to complete warmups
    time.sleep(3.5)

    # Safely close the splash screen
    try:
        global splash_root
        if splash_root:
            splash_root.after(0, splash_root.destroy)
    except Exception:
        pass

    webbrowser.open(url)


if __name__ == "__main__":
    try:
        os.chdir(_runtime_dir())
        _prepare_application_data()
        import uvicorn
        from app import app

        bind_host = os.getenv("APP_BIND", "127.0.0.1")
        bind_port = int(os.getenv("APP_PORT", "7000"))
        url = f"http://{bind_host}:{bind_port}"

        if getattr(sys, 'frozen', False):
            threading.Thread(target=open_browser, args=(url,), daemon=True).start()
            threading.Thread(target=setup_system_tray, args=(url,), daemon=True).start()

        uvicorn.run(app, host=bind_host, port=bind_port, log_level="info")
    except Exception as error:
        _show_startup_error(error)
        raise
