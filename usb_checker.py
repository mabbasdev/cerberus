"""
usb_checker.py
--------------
Layer 2 of Cerberus: is an *authorized* USB storage device plugged in?

Two modes (see config.py):
  * Serial-verified — only a specific USB (by serial) satisfies the check.
  * Any-USB        — any mounted removable drive satisfies the check.

Real-world notes (learned the hard way during testing on Windows):
  * psutil cannot tell us the Windows DriveType, so the old heuristic
    of "mount point starts with D:/E:/etc." wrongly treated internal
    SSDs as removable. We now use WMI's Win32_LogicalDisk.DriveType
    to identify removable drives correctly (DriveType == 2).
  * Windows can return a blank SerialNumber for a USB stick that
    matched seconds earlier (WMI re-enumeration, sleep/wake, cheap
    controllers). We retry for SERIAL_RETRY_SECONDS before giving up.
  * WMI may list MULTIPLE USB drives. The old "first USB drive wins"
    approach returned the wrong serial. We now walk
    LogicalDisk -> Partition -> DiskDrive for the SPECIFIC drive
    letter, and read the serial from the disk that actually backs it.
  * We cache last-known-good serials per device path for the lifetime
    of the process. The cache is intentionally NOT persisted to disk,
    so a fresh boot never inherits trusted state.
"""

import os
import platform
import time

import psutil

from config import (
    VERIFY_USB_SERIAL,
    USB_SERIAL_WHITELIST,
    SERIAL_RETRY_SECONDS,
    SERIAL_RETRY_INTERVAL,
)
from logger_setup import get_logger

logger = get_logger("usb_checker")

# In-memory cache: device_path -> last known serial that matched the whitelist.
# Populated whenever a device passes; consulted when WMI returns None.
_KNOWN_GOOD: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Drive enumeration — cross-platform
# ---------------------------------------------------------------------------
def _windows_removable_drives() -> list[str]:
    """
    Return drive letters (e.g. ['E:']) for removable volumes on Windows.

    Win32_LogicalDisk.DriveType values:
        0 = Unknown
        1 = No Root Directory
        2 = Removable       <-- USB sticks, SD cards, card readers
        3 = Local Disk      <-- internal HDD/SSD — NOT what we want
        4 = Network Drive
        5 = CD-ROM
        6 = RAM Disk

    This is more accurate than checking drive letters, because the
    user may have internal drives at D:/E:/ and the USB at F:/G:/.
    """
    try:
        import wmi
    except Exception:
        return []

    try:
        c = wmi.WMI()
        return [
            ld.DeviceID
            for ld in c.Win32_LogicalDisk()
            if ld.DriveType == 2 and ld.DeviceID
        ]
    except Exception as exc:
        logger.info("WMI removable-drive enumeration failed: %s", exc)
        return []


def _get_removable_mounts() -> list[dict]:
    """
    Return a list of dicts describing mounted removable storage devices.

    On Windows we use WMI DriveType to identify removable volumes.
    On Linux/macOS we rely on psutil's mount points and options.
    """
    system = platform.system()

    if system == "Windows":
        removable_letters = set(_windows_removable_drives())
        devices = []
        for part in psutil.disk_partitions(all=False):
            # part.device on Windows is like 'E:\\'
            letter = (part.device or "").rstrip("\\/").upper()
            if not letter.endswith(":"):
                letter += ":"
            if letter in removable_letters:
                devices.append(
                    {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "opts": part.opts,
                    }
                )
        return devices

    # Linux / macOS
    devices = []
    for part in psutil.disk_partitions(all=False):
        opts = part.opts.lower()
        is_removable = (
            "removable" in opts
            or "/media/" in part.mountpoint
            or "/run/media/" in part.mountpoint
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


# ---------------------------------------------------------------------------
# Windows: map drive letter -> serial via WMI association classes
# ---------------------------------------------------------------------------
def _windows_serial_for_drive(drive_letter: str) -> str | None:
    """
    Return the serial number of the *physical disk* backing a drive letter
    like 'E:'. Walks LogicalDisk -> Partition -> DiskDrive via WMI.

    We do NOT use the `associators()` helper because its behavior varies
    across `wmi` versions and can silently return empty results. Instead
    we iterate the raw association classes and match WMI paths by string.

    We also do NOT filter by InterfaceType. Windows reports many USB
    sticks as IDE or SCSI, so the interface filter only adds false
    negatives. The serial whitelist is the real security gate.
    """
    try:
        import wmi
    except Exception:
        return None

    try:
        c = wmi.WMI()
        drive_letter = drive_letter.rstrip("\\/").upper()
        if not drive_letter.endswith(":"):
            drive_letter += ":"

        # Step 1: find the logical disk object for this drive letter.
        logical = None
        for ld in c.Win32_LogicalDisk():
            if (ld.DeviceID or "").upper() == drive_letter:
                logical = ld
                break
        if logical is None:
            logger.info("No Win32_LogicalDisk found for %s", drive_letter)
            return None

        logical_path = logical.path_()

        # Step 2: find partitions associated with this logical disk.
        # Iterate the raw association class and match paths by string —
        # this works on every wmi version we've seen.
        partition_paths = []
        for assoc in c.Win32_LogicalDiskToPartition():
            if assoc.Dependent is None or assoc.Antecedent is None:
                continue
            if assoc.Dependent.Path_.Path == logical_path:
                partition_paths.append(assoc.Antecedent.Path_.Path)

        if not partition_paths:
            logger.info("No partition association for %s", drive_letter)
            return None

        # Step 3: find physical disks associated with those partitions.
        disk_paths = []
        for assoc in c.Win32_DiskDriveToDiskPartition():
            if assoc.Dependent is None or assoc.Antecedent is None:
                continue
            if assoc.Dependent.Path_.Path in partition_paths:
                disk_paths.append(assoc.Antecedent.Path_.Path)

        if not disk_paths:
            logger.info("No disk association for %s", drive_letter)
            return None

        # Step 4: read the serial from the matched physical disk(s).
        for disk in c.Win32_DiskDrive():
            if disk.path_() in disk_paths:
                serial = (disk.SerialNumber or "").strip()
                logger.info(
                    "%s -> %s (iface=%s, serial=%s)",
                    drive_letter,
                    disk.Model,
                    disk.InterfaceType,
                    serial,
                )
                if serial:
                    return serial
    except Exception as exc:
        logger.info("WMI drive-letter->serial lookup failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Linux: read /sys/block/<dev>/device/serial
# ---------------------------------------------------------------------------
def _linux_serial_for_device(device_path: str) -> str | None:
    base = os.path.basename(device_path).rstrip("0123456789")
    serial_file = f"/sys/block/{base}/device/serial"
    try:
        if os.path.exists(serial_file):
            with open(serial_file) as f:
                return f.read().strip() or None
    except OSError:
        pass
    return None


def _device_serial(device_path: str) -> str | None:
    """Best-effort retrieval of a USB device's serial number."""
    system = platform.system()
    if system == "Windows":
        return _windows_serial_for_drive(device_path)
    if system == "Linux":
        return _linux_serial_for_device(device_path)
    return None


def _serial_with_retry(device_path: str) -> str | None:
    """
    Retry the serial lookup for SERIAL_RETRY_SECONDS before giving up.

    Windows occasionally needs a moment to expose the serial after the
    device is enumerated (e.g., right after login). Logs each retry so
    testers can see what's happening.
    """
    deadline = time.monotonic() + SERIAL_RETRY_SECONDS
    attempt = 0
    while True:
        attempt += 1
        serial = _device_serial(device_path)
        if serial:
            return serial
        if time.monotonic() >= deadline:
            return None
        logger.info(
            "Serial lookup returned None for %s (attempt %d). Retrying...",
            device_path,
            attempt,
        )
        time.sleep(SERIAL_RETRY_INTERVAL)


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
        dev = m["device"]

        serial = _serial_with_retry(dev)

        # Fallback: if this device path previously passed, trust the cache.
        if serial is None and dev in _KNOWN_GOOD:
            serial = _KNOWN_GOOD[dev]
            logger.info(
                "Serial unavailable for %s — using cached known-good serial %s",
                dev,
                serial,
            )
        else:
            logger.info("Checking device %s -> serial=%s", dev, serial)

        if serial and serial in USB_SERIAL_WHITELIST:
            _KNOWN_GOOD[dev] = serial
            logger.info("Authorized USB serial matched: %s", serial)
            return True

    logger.warning("No USB with an authorized serial was found.")
    return False