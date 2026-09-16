from pathlib import Path
import tkinter as tk


def apply_icon(window):
    # __file__ resolves inside the bundled resources in PyInstaller builds.
    assets = Path(__file__).resolve().parents[1] / "assets"
    image = tk.PhotoImage(file=str(assets / "alien.png"))
    window.iconphoto(True, image)
    window._brand_icon = image
    if window.tk.call("tk", "windowingsystem") == "win32":
        window.iconbitmap(str(assets / "alien.ico"))
