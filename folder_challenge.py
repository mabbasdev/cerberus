"""
folder_challenge.py
-------------------
Layer 3 of Cerberus: the Desktop folder challenge.

After the USB check passes, the user has FOLDER_CREATION_TIMEOUT seconds
to create a folder named UNLOCK_FOLDER_NAME on their Desktop. This proves
the human (not just the token) is present and aware.

If the folder appears in time -> True.
If the timer expires         -> False.
"""

import os
import time

from config import (
    UNLOCK_FOLDER_NAME,
    FOLDER_CREATION_TIMEOUT,
    FOLDER_POLL_INTERVAL,
    get_desktop_path,
)
from logger_setup import get_logger

logger = get_logger("folder_challenge")


def wait_for_unlock_folder() -> bool:
    """
    Poll the Desktop until the unlock folder exists or the timeout fires.
    """
    desktop = get_desktop_path()
    target = desktop / UNLOCK_FOLDER_NAME

    logger.info("Desktop resolved to: %s", desktop)
    logger.info(
        "Waiting up to %.1fs for folder: %s",
        FOLDER_CREATION_TIMEOUT,
        target,
    )

    deadline = time.monotonic() + FOLDER_CREATION_TIMEOUT
    while time.monotonic() < deadline:
        if target.is_dir():
            logger.info("Unlock folder found: %s", target)
            return True
        time.sleep(FOLDER_POLL_INTERVAL)

    logger.warning("Timeout: unlock folder was not created on the Desktop.")
    return False