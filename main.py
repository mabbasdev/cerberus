"""
main.py
-------
Cerberus — a three-headed guard for your desktop.

Flow:
  Layer 1 (OS login) -> handled by the OS.
  Layer 2 (USB)      -> if not authorized -> shutdown.
  Layer 3 (folder)   -> user must create 'unlock' on Desktop within N seconds,
                        else -> shutdown.

Usage:
    python main.py
"""

import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)

import os
import sys
import time
import platform
import subprocess

from config import (
    DEV_MODE,
    USB_CHECK_DELAY,
    get_desktop_path,
    UNLOCK_FOLDER_NAME,
    FOLDER_CREATION_TIMEOUT,
)
from logger_setup import get_logger
from usb_checker import is_authorized_usb_connected
from folder_challenge import wait_for_unlock_folder
from popup import start_popup, wait_for_close

logger = get_logger("cerberus")


def shutdown_system(reason: str) -> None:
    """
    Shut down the machine immediately, no confirmation prompt.

    In DEV_MODE this only logs — critical so we never power off
    a development machine by accident during testing.
    """
    if DEV_MODE:
        logger.warning("DEV_MODE: would shut down now. Reason: %s", reason)
        print(f"\n[DEV MODE] Shutdown simulated. Reason: {reason}\n")
        return

    logger.critical("SHUTTING DOWN. Reason: %s", reason)
    system = platform.system()
    try:
        if system == "Windows":
            # Use the full path to shutdown.exe because Task Scheduler
            # may run us with a minimal PATH. The /f flag force-closes
            # applications so Windows doesn't wait for "save your work?"
            # prompts — matching the "no warning" requirement.
            shutdown_exe = os.path.join(
                os.environ.get("SystemRoot", r"C:\Windows"),
                "System32",
                "shutdown.exe",
            )
            subprocess.run([shutdown_exe, "/s", "/f", "/t", "0"], check=False)
        elif system == "Linux":
            subprocess.run(["shutdown", "-h", "now"], check=False)
        elif system == "Darwin":
            subprocess.run(
                ["osascript", "-e", 'tell app "System Events" to shut down'],
                check=False,
            )
    except Exception as exc:
        logger.exception("Failed to issue shutdown command: %s", exc)
        sys.exit(1)


def run_authentication() -> bool:
    """Execute Cerberus's layers 2 and 3. Returns True on full success."""
    # ---- Head 2: USB presence --------------------------------------------
    logger.info("=== Cerberus head 2: USB check ===")
    if not is_authorized_usb_connected():
        logger.warning("USB authentication FAILED.")
        return False
    logger.info("USB authentication PASSED.")

    # ---- Head 3: Desktop folder challenge --------------------------------
    logger.info("=== Cerberus head 3: Desktop folder challenge ===")
    logger.info(
        "Create a folder named '%s' on your Desktop within %.0fs.",
        UNLOCK_FOLDER_NAME,
        FOLDER_CREATION_TIMEOUT,
    )
    if not wait_for_unlock_folder():
        logger.warning("Folder challenge FAILED.")
        return False
    logger.info("Folder challenge PASSED.")
    return True


def main() -> int:
    # Start the popup first so every log line (including startup) appears.
    start_popup()

    logger.info("Cerberus starting (DEV_MODE=%s).", DEV_MODE)
    logger.info("Desktop path: %s", get_desktop_path())

    # Small delay so the desktop finishes loading after OS login.
    time.sleep(USB_CHECK_DELAY)

    try:
        ok = run_authentication()
    except Exception as exc:
        logger.exception("Unhandled error during authentication: %s", exc)
        ok = False

    if ok:
        logger.info("=== All Cerberus heads satisfied. System unlocked. ===")
        print("Cerberus: all three heads are calm. Welcome!")
        # Keep the popup visible until the user closes it. Without this,
        # main() would return immediately and the daemon popup thread
        # would be killed, causing the window to flash and vanish.
        wait_for_close()
        return 0

    shutdown_system("authentication failure")
    # In DEV_MODE nothing was actually shut down, so give the tester a
    # few seconds to read the popup before it disappears. In real mode,
    # the machine will already be powering off before this line runs.
    wait_for_close(timeout=8)
    return 1


if __name__ == "__main__":
    sys.exit(main())