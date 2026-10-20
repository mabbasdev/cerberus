"""
usb_checker.py
--------------
Layer 2 of Cerberus: is an *authorized* USB storage device plugged in?

We support two modes (see config.py):
  * Serial-verified — only a specific USB (by serial) satisfies the check.
  * Any-USB        — any mounted removable drive satisfies the check.
"""

import os
import platform
import psutil

from config import VERIFY_USB_SERIAL, USB_SERIAL_WHITELIST
from logger_setup import get_logger

logger = get_logger("usb_checker")


def _get_removable_mounts() -> list[dict]:
    """Return a list of dicts describing mounted removable storage devices."""
    devices = []
    for part in psutil.disk_partitions(all=False):
        opts = part.opts.lower()
        is_removable = (
            "removable" in opts
            or "/media/" in part.mountpoint
            or "/run/media/" in part.mountpoint
            or part.mountpoint.startswith(("D:", "E:", "F:", "G:", "H:"))
        )
        if is_removable:
            devices.append(
                {
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "opts": part.opts,
                }
            )
    return devices


def _device_serial(device_path: str) -> str | None:
    """Best-effort retrieval of a USB device's serial number."""
    system = platform.system()

    if system == "Linux":
        base = os.path.basename(device_path).rstrip("0123456789")
        serial_file = f"/sys/block/{base}/device/serial"
        try:
            if os.path.exists(serial_file):
                with open(serial_file) as f:
                    return f.read().strip()
        except OSError:
            pass
        return None

    if system == "Windows":
        try:
            import wmi  # optional dependency
            c = wmi.WMI()
            for drive in c.Win32_DiskDrive():
                if "USB" in (drive.InterfaceType or ""):
                    return (drive.SerialNumber or "").strip()
        except Exception:
            return None
        return None

    return None


def is_authorized_usb_connected() -> bool:
    """Public API: True iff an authorized USB storage device is mounted."""
    mounts = _get_removable_mounts()
    if not mounts:
        logger.info("No removable storage devices detected.")
        return False

    logger.info("Removable devices detected: %s", [m["mountpoint"] for m in mounts])

    if not VERIFY_USB_SERIAL:
        logger.info("Serial verification disabled — accepting any removable drive.")
        return True

    for m in mounts:
        serial = _device_serial(m["device"])
        logger.info("Checking device %s -> serial=%s", m["device"], serial)
        if serial and serial in USB_SERIAL_WHITELIST:
            logger.info("Authorized USB serial matched: %s", serial)
            return True

    logger.warning("No USB with an authorized serial was found.")
    return False