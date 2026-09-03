#!/usr/bin/env python3
"""Helper script to create a Windows Desktop Shortcut for 1-Click Launch."""

import os
import sys
import subprocess
from pathlib import Path

def get_windows_desktop_path() -> Path:
    try:
        import ctypes.wintypes
        CSIDL_DESKTOP = 0
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf)
        p = Path(buf.value)
        if p.exists():
            return p
    except Exception:
        pass
    
    # Fallbacks
    userprofile = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    candidates = [
        userprofile / "OneDrive" / "Desktop",
        userprofile / "Desktop",
    ]
    for c in candidates:
        if c.exists():
            return c
    return userprofile / "Desktop"

def create_shortcut():
    desktop = get_windows_desktop_path()
    if not desktop.exists():
        os.makedirs(str(desktop), exist_ok=True)

    base_dir = Path(__file__).resolve().parent
    root_bat = base_dir.parent / "START_BOT.bat"
    target_bat = root_bat if root_bat.exists() else base_dir / "START_BOT.bat"
    shortcut_path = desktop / "GepLex AI Bot.lnk"
    icon_path = base_dir / "assets" / "branding" / "geplex-logo.ico"

    vbs_code = f'''
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{str(shortcut_path)}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{str(target_bat)}"
oLink.WorkingDirectory = "{str(base_dir)}"
oLink.Description = "Start GepLex AI Workspace in 1 Click"
'''
    if icon_path.exists():
        vbs_code += f'oLink.IconLocation = "{str(icon_path)}"\n'

    vbs_code += 'oLink.Save\n'

    vbs_file = base_dir / "_temp_shortcut.vbs"
    try:
        vbs_file.write_text(vbs_code, encoding="utf-8")
        subprocess.run(["cscript", "//Nologo", str(vbs_file)], check=True)
        if vbs_file.exists():
            vbs_file.unlink()
        print(f"[+] Desktop shortcut successfully created: {shortcut_path}")
        return True
    except Exception as e:
        print(f"[-] Error creating shortcut: {e}")
        if vbs_file.exists():
            vbs_file.unlink()
        return False

if __name__ == "__main__":
    create_shortcut()
