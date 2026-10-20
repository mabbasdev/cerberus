"""
config.py
---------
Central configuration for Cerberus — a three-headed guard for your desktop.

Layer 1: OS login (handled by the OS, not us)
Layer 2: Authorized USB presence check
Layer 3: Desktop folder challenge ("unlock" folder within N seconds)
"""

import os
from pathlib import Path

# --- General ---
# Set to True while developing: shows warnings instead of shutting down.
DEV_MODE = False

# --- Layer 3: Desktop folder challenge ---
# Folder name the user must create ON THE DESKTOP to complete auth.
UNLOCK_FOLDER_NAME = "unlock"

# Time (seconds) the user has to create the folder after the USB check passes.
FOLDER_CREATION_TIMEOUT = 10

# How often we poll the Desktop for the folder (seconds).
FOLDER_POLL_INTERVAL = 0.25

# --- Layer 2: USB verification ---
# If True, only a USB whose serial matches the whitelist counts.
# If False, ANY mounted removable storage satisfies the check.
VERIFY_USB_SERIAL = True

# Whitelist of accepted USB serial numbers (add your own USB's serial).
# Linux:   lsblk -o NAME,SERIAL,TRAN
# Windows: wmic diskdrive get SerialNumber,InterfaceType
# macOS:   system_profiler SPUSBDataType | grep "Serial Number"
USB_SERIAL_WHITELIST = [
    # "YOUR_USB_SERIAL_HERE",
    "5B850F0005F8",
]

# Seconds to wait after service start before the first USB check —
# gives the desktop time to finish loading after OS login.
USB_CHECK_DELAY = 2

# How long to retry a serial lookup before declaring it absent (seconds).
SERIAL_RETRY_SECONDS = 3

# Delay between serial lookup retries (seconds).
SERIAL_RETRY_INTERVAL = 0.5


def get_desktop_path() -> Path:
    """
    Return the current user's Desktop directory in a cross-platform way.

    Why not just '~'? Because on localized systems the folder name varies
    (e.g., 'Bureau' on French Windows, 'Escritorio' on Spanish Linux).
    We try the most reliable signals first, then fall back.
    """
    home = Path.home()

    # 1) Respect XDG on Linux/macOS if present
    xdg_config = home / ".config" / "user-dirs.dirs"
    if xdg_config.exists():
        try:
            for line in xdg_config.read_text(encoding="utf-8").splitlines():
                if line.startswith("XDG_DESKTOP_DIR="):
                    raw = line.split("=", 1)[1].strip().strip('"')
                    # XDG allows $HOME expansion
                    raw = raw.replace("$HOME", str(home))
                    candidate = Path(raw)
                    if candidate.is_dir():
                        return candidate
        except OSError:
            pass

    # 2) Common English fallback
    for candidate in (home / "Desktop", home / "desktop"):
        if candidate.is_dir():
            return candidate

    # 3) Last resort — return the home path and warn later
    return home