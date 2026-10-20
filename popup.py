"""
popup.py
--------
Live notification window for Cerberus.

A lightweight Tkinter window that mirrors every log message from the
terminal. It runs in a background thread so the main authentication
flow is never blocked.

Design notes:
  * Uses a thread-safe queue.Queue to pass log records from the
    calling thread (logging handler) to the Tkinter main loop.
  * Tkinter is NOT thread-safe — all widget updates happen on the
    thread that created the root window (the thread started by
    start_popup()).
  * The window is borderless-ish but closable; it does not steal
    focus so it never interferes with the folder challenge.
  * If Tkinter is unavailable (e.g., headless), it silently disables
    itself so Cerberus still runs on servers.
"""

import logging
import queue
import threading
import time
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk
    TK_AVAILABLE = True
except ImportError:  # pragma: no cover — headless environments
    TK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_message_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
_popup_thread: threading.Thread | None = None
_stop_event = threading.Event()

# Colors per log level — keeps the visual language consistent.
_LEVEL_COLORS = {
    "INFO":     "#2f80ed",   # blue
    "WARNING":  "#e2b93b",   # amber
    "ERROR":    "#eb5757",   # red
    "CRITICAL": "#bb0b0b",   # dark red
    "DEBUG":    "#888888",   # grey
}


# ---------------------------------------------------------------------------
# Logging handler that feeds the popup
# ---------------------------------------------------------------------------
class PopupHandler(logging.Handler):
    """
    Logging handler that pushes each record into the popup queue.

    We format a *simplified* message (no logger name, no full timestamp
    prefix) because the popup already shows the time in its own column.
    Full fidelity is preserved in cerberus.log via the file handler.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Short HH:MM:SS timestamp for the popup row.
            ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
            msg = record.getMessage()
            _message_queue.put((record.levelname, ts, msg))
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Tkinter UI loop (runs on its own thread)
# ---------------------------------------------------------------------------
def _run_popup_window() -> None:
    """Create the Tk root window and pump messages from the queue."""
    root = tk.Tk()
    root.title("Cerberus 🐺 — Live Status")
    root.geometry("620x360+40+40")
    root.configure(bg="#1e1e1e")
    root.attributes("-topmost", True)   # float above other windows
    # Do not steal keyboard focus from the user — they may be creating
    # the unlock folder at this very moment.
    root.attributes("-alpha", 0.96)

    # ---- Header -----------------------------------------------------------
    header = tk.Label(
        root,
        text="CERBERUS — LIVE AUTHENTICATION LOG",
        bg="#111111",
        fg="#ffffff",
        font=("Consolas", 11, "bold"),
        pady=8,
    )
    header.pack(fill="x")

    # ---- Scrollable text area --------------------------------------------
    frame = tk.Frame(root, bg="#1e1e1e")
    frame.pack(fill="both", expand=True, padx=8, pady=8)

    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")

    text = tk.Text(
        frame,
        bg="#1e1e1e",
        fg="#dcdcdc",
        font=("Consolas", 10),
        wrap="word",
        insertbackground="#ffffff",
        yscrollcommand=scrollbar.set,
        borderwidth=0,
        highlightthickness=0,
    )
    text.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=text.yview)

    # Tag styles per level (foreground colours).
    for level, color in _LEVEL_COLORS.items():
        text.tag_config(level, foreground=color)
    text.tag_config("time", foreground="#6c6c6c")

    # ---- Status bar -------------------------------------------------------
    status = tk.Label(
        root,
        text="Waiting for events...",
        bg="#111111",
        fg="#9c9c9c",
        font=("Consolas", 9),
        anchor="w",
        padx=8,
        pady=4,
    )
    status.pack(fill="x")

    # ---- Queue pump -------------------------------------------------------
    def pump() -> None:
        """Drain the queue and append messages; reschedule itself."""
        if _stop_event.is_set():
            root.destroy()
            return

        drained = 0
        while drained < 50:  # cap per tick to stay responsive
            try:
                level, ts, msg = _message_queue.get_nowait()
            except queue.Empty:
                break
            text.insert("end", f"[{ts}] ", "time")
            text.insert("end", f"{level:<8} {msg}\n", level)
            status.config(text=f"Last event: [{ts}] {level}")
            drained += 1

        if drained:
            text.see("end")  # auto-scroll to newest

        root.after(100, pump)

    root.after(100, pump)

    # ---- Graceful close ---------------------------------------------------
    def on_close() -> None:
        _stop_event.set()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def start_popup() -> None:
    """
    Launch the popup window in a daemon thread and register the
    PopupHandler on the root logger so every module's messages show up.
    """
    if not TK_AVAILABLE:
        return  # headless environment — silently skip

    global _popup_thread
    if _popup_thread is not None and _popup_thread.is_alive():
        return  # already running

    # Attach the handler once, to the root logger, so *all* child
    # loggers (cerberus, usb_checker, folder_challenge, ...) feed it.
    root_logger = logging.getLogger()
    # Avoid duplicate handlers if start_popup() is called more than once.
    if not any(isinstance(h, PopupHandler) for h in root_logger.handlers):
        root_logger.addHandler(PopupHandler())

    _stop_event.clear()
    _popup_thread = threading.Thread(
        target=_run_popup_window,
        name="cerberus-popup",
        daemon=True,
    )
    _popup_thread.start()


def wait_for_close(timeout: float | None = None) -> None:
    """
    Optional helper: block until the user closes the popup window.

    Useful at the end of main.py if you want the popup to stay visible
    after authentication finishes instead of vanishing immediately.
    """
    if _popup_thread is not None:
        _popup_thread.join(timeout)