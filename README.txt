# CERBERUS — A Three-Headed Guard for Your Desktop

In Greek mythology, Cerberus guards the gates of the Underworld. In this project, Cerberus guards your desktop with three layers of authentication: your OS password, an authorized USB, and a live folder challenge on your Desktop.

## Layers

### Layer 1 — OS Login
Handled by the operating system. Cerberus does not participate.

### Layer 2 — USB Head
An authorized USB (verified by serial number) must be plugged in.

### Layer 3 — Folder Head
You must create a folder named `unlock` on your Desktop within the configured timeout (default: 10 seconds).

**Failure at Layer 2 or 3 triggers an immediate shutdown of the machine.**

In `DEV_MODE`, the shutdown is simulated (logged only), so you can test safely.

---

## Project Files

| File | Description |
|---|---|
| `config.py` | All tunable parameters (timeouts, USB whitelist, etc.) |
| `logger_setup.py` | Rotating file logger (writes to `cerberus.log`) |
| `usb_checker.py` | Layer 2: authorized USB detection |
| `folder_challenge.py` | Layer 3: Desktop folder challenge |
| `popup.py` | Live Tkinter status window |
| `main.py` | Entry point; runs all layers |

---

## Dev Setup

### 1. Create and Activate a Virtual Environment

```bash
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install wmi
```

> **Note:** `wmi` is required on Windows for serial-number lookup.

### 3. Run Cerberus

```bash
python main.py
```

---

## Finding Your USB Serial Number

### Linux

```bash
lsblk -o NAME,SERIAL,TRAN
```

Look for a row where `TRAN` is `usb`.

### Windows (PowerShell)

```powershell
Get-WmiObject Win32_DiskDrive |
    Select-Object Model,SerialNumber,InterfaceType
```

Look for the row where `InterfaceType` is `USB`. Copy the `SerialNumber`.

### macOS

```bash
system_profiler SPUSBDataType | grep "Serial Number"
```

Paste the serial into `config.py` under `USB_SERIAL_WHITELIST`.

---

## Important Testing Notes

- The `DEV_MODE` flag in `config.py` controls whether shutdowns actually happen. **Always test with `DEV_MODE = True` first**, in a virtual machine if possible. Only set `DEV_MODE = False` when you are ready for the machine to really power off.

- Delete the `unlock` folder from your Desktop before each test run. If the folder is left over from a previous run, Layer 3 will pass instantly, and the test will not reflect real behavior.

- Delete `cerberus.log` before a demonstration run to keep the log clean and focused on the current session.

- On Windows, `shutdown.exe` requires the `SeShutdownPrivilege`. Run Cerberus from an Administrator account, or the shutdown command may fail. You will see `Failed to issue shutdown command` in `cerberus.log` if this happens.

---

## Running as a Login Service

### Windows Task Scheduler (Recommended for the Demo)

1. Open Task Scheduler.
2. Select **Create Basic Task** and name it `Cerberus`.
3. Set the trigger to **When I log on**.
4. Set the action to **Start a program**.
   - **Program:**
     ```text
     C:\path\to\cerberus\.venv\Scripts\pythonw.exe
     ```
   - **Arguments:**
     ```text
     C:\path\to\cerberus\main.py
     ```
   - **Start in:**
     ```text
     C:\path\to\cerberus
     ```
5. Finish the wizard. Right-click the task and choose **Run** to test.

### Linux (systemd User Unit)

Create `~/.config/systemd/user/cerberus.service` with the following contents:

```ini
[Unit]
Description=Cerberus USB Guard
After=graphical-session.target

[Service]
ExecStart=/path/to/.venv/bin/python /path/to/main.py
Restart=always

[Install]
WantedBy=default.target
```

Then run:

```bash
systemctl --user daemon-reload
systemctl --user enable --now cerberus
```

`Restart=always` ensures that the service manager restarts Cerberus if the process exits. However, this does not prevent every possible way of disabling the protection.

---

## Security Notes (For the Project Report)

### 1. Why "Any USB" Is Weak

If any USB satisfies Layer 2, an attacker only needs a spare flash drive. Serial verification closes this gap. `USB_SERIAL_WHITELIST` is the correct configuration.

### 2. USB Serial Spoofability

Advanced attackers can clone a USB serial by reflashing the device firmware. Real-world mitigations use hardware tokens such as FIDO2 devices or YubiKeys that sign challenges cryptographically. Mention this in your threat model.

### 3. Folder Challenge Limits

The folder challenge is a knowledge/behavior factor, not a cryptographic one. It is best treated as a third factor on top of the OS password and the USB, not as a standalone control.

### 4. Race Conditions

A fast attacker could kill `main.py` before shutdown fires. In production, run Cerberus under a service manager (systemd or Task Scheduler) with `Restart=always` so the service manager attempts to restart it if the process exits.

This is not implemented in the current version but is worth noting in the report.

### 5. Log Integrity

`cerberus.log` is plaintext and unsigned. Any attacker with file access can modify it. For a real deployment, consider signing log entries with an HMAC under a securely managed key.

---

## Extension Ideas

- Replace the folder challenge with an HMAC of a per-boot nonce.
- Encrypt the USB whitelist with a key derived from the OS password.
- Use `pyudev` (Linux) or WMI event subscriptions (Windows) instead of polling for USB presence.
- Add a `--bypass` flag protected by a hashed password for demo safety.
- Add a visual countdown bar to the popup during the Layer 3 timer.

---

## Troubleshooting

### "No removable storage devices detected" With USB Plugged In

`psutil` did not see the drive. Open a Python shell and print `psutil.disk_partitions()` to check. If the drive does not appear, verify that it is mounted and has a drive letter assigned.

### Serial Shows as `None` Repeatedly

Ensure `wmi` is installed in the active virtual environment:

```bash
pip install wmi
```

If it is installed and the serial is still `None`, the USB controller may not expose a serial. In that case, set `VERIFY_USB_SERIAL = False` to test the rest of the flow, or switch to a different USB stick.

### Folder Challenge Never Succeeds

Check the log line `Desktop resolved to: ...` to verify the Desktop path. If it points somewhere unexpected, override `get_desktop_path()` in `config.py` or place the `unlock` folder at the reported path.

### Shutdown Does Not Fire in Real Mode

Ensure `DEV_MODE = False` in `config.py`. Run from an Administrator account on Windows. Check `cerberus.log` for `Failed to issue shutdown command` and adjust accordingly.

> **Safety warning:** Test real shutdown behavior only on a machine you control, after saving your work. Prefer testing in a virtual machine with `DEV_MODE = True` first.

### Popup Window Flashes and Disappears

This should be fixed in the current version via `wait_for_close()`. If it still happens, confirm that `main.py` contains the two `wait_for_close()` calls near the end of `main()`.

---

**End of README**
