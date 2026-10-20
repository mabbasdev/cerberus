================================================================================
CERBERUS - A Three-Headed Guard for Your Desktop
================================================================================

In Greek mythology, Cerberus guards the gates of the Underworld. In this
project, Cerberus guards your desktop with three layers of authentication:
your OS password, an authorized USB, and a live folder challenge on your
Desktop.


--------------------------------------------------------------------------------
LAYERS
--------------------------------------------------------------------------------

  Layer 1 - OS Login
      Handled by the operating system. Cerberus does not participate.

  Layer 2 - USB Head
      An authorized USB (verified by serial number) must be plugged in.

  Layer 3 - Folder Head
      You must create a folder named "unlock" on your Desktop within
      the configured timeout (default: 10 seconds).

Failure at layer 2 or 3 triggers an immediate shutdown of the machine.
In DEV_MODE the shutdown is simulated (logged only), so you can test safely.


--------------------------------------------------------------------------------
PROJECT FILES
--------------------------------------------------------------------------------

  config.py           - All tunable parameters (timeouts, USB whitelist, etc.)
  logger_setup.py     - Rotating file logger (writes to cerberus.log)
  usb_checker.py      - Layer 2: authorized USB detection
  folder_challenge.py - Layer 3: Desktop folder challenge
  popup.py            - Live Tkinter status window
  main.py             - Entry point; runs all layers


--------------------------------------------------------------------------------
DEV SETUP
--------------------------------------------------------------------------------

  1. Create and activate a virtual environment:

         python -m venv .venv
         .venv\Scripts\activate

  2. Install dependencies:

         pip install -r requirements.txt
         pip install wmi

     (wmi is required on Windows for serial-number lookup.)

  3. Run:

         python main.py


--------------------------------------------------------------------------------
FINDING YOUR USB SERIAL NUMBER
--------------------------------------------------------------------------------

  Linux:
      lsblk -o NAME,SERIAL,TRAN
      (look for a row where TRAN is "usb")

  Windows (PowerShell):
      Get-WmiObject Win32_DiskDrive |
        Select-Object Model,SerialNumber,InterfaceType

      Look for the row where InterfaceType is "USB". Copy the SerialNumber.

  macOS:
      system_profiler SPUSBDataType | grep "Serial Number"

  Paste the serial into config.py under USB_SERIAL_WHITELIST.


--------------------------------------------------------------------------------
IMPORTANT TESTING NOTES
--------------------------------------------------------------------------------

  * The DEV_MODE flag in config.py controls whether shutdowns actually
    happen. ALWAYS test with DEV_MODE = True first, in a virtual machine
    if possible. Only set DEV_MODE = False when you are ready for the
    machine to really power off.

  * Delete the "unlock" folder from your Desktop before each test run.
    If the folder is left over from a previous run, Layer 3 will pass
    instantly and the test will not reflect real behavior.

  * Delete cerberus.log before a demonstration run to keep the log clean
    and focused on the current session.

  * On Windows, shutdown.exe requires the SeShutdownPrivilege. Run
    Cerberus from an Administrator account, or the shutdown command
    will silently fail. You will see "Failed to issue shutdown command"
    in cerberus.log if this happens.


--------------------------------------------------------------------------------
RUNNING AS A LOGIN SERVICE
--------------------------------------------------------------------------------

  Windows Task Scheduler (recommended for the demo):

      1. Open Task Scheduler.
      2. Create Basic Task -> name it "Cerberus".
      3. Trigger: "When I log on".
      4. Action: "Start a program".
         Program:   C:\path\to\cerberus\.venv\Scripts\pythonw.exe
         Arguments: C:\path\to\cerberus\main.py
         Start in:  C:\path\to\cerberus
      5. Finish. Right-click the task and choose "Run" to test.

  Linux (systemd user unit):

      Create ~/.config/systemd/user/cerberus.service with:

          [Unit]
          Description=Cerberus USB Guard
          After=graphical-session.target

          [Service]
          ExecStart=/path/to/.venv/bin/python /path/to/main.py
          Restart=always

          [Install]
          WantedBy=default.target

      Then:

          systemctl --user daemon-reload
          systemctl --user enable --now cerberus

      Restart=always ensures an attacker cannot simply kill the process.


--------------------------------------------------------------------------------
SECURITY NOTES (for the project report)
--------------------------------------------------------------------------------

  1. Why "any USB" is weak:
     If any USB satisfies Layer 2, an attacker only needs a spare flash
     drive. Serial verification closes this gap. USB_SERIAL_WHITELIST is
     the correct configuration.

  2. USB serial spoofability:
     Advanced attackers can clone a USB serial by reflashing the device
     firmware. Real-world mitigations use hardware tokens (FIDO2,
     YubiKey) that sign challenges cryptographically. Mention this in
     your threat model.

  3. Folder challenge limits:
     The folder challenge is a knowledge/behavior factor, not a
     cryptographic one. It is best treated as a third factor on top of
     the OS password and the USB, not as a standalone control.

  4. Race conditions:
     A fast attacker could kill main.py before shutdown fires. In
     production, run Cerberus under a service manager (systemd or Task
     Scheduler) with Restart=always so killing it triggers an immediate
     restart. This is not implemented in the current version but is
     worth noting in the report.

  5. Log integrity:
     cerberus.log is plaintext and unsigned. Any attacker with file
     access can modify it. For a real deployment, sign log entries with
     HMAC under a key derived from the OS password.


--------------------------------------------------------------------------------
EXTENSION IDEAS
--------------------------------------------------------------------------------

  * Replace the folder challenge with an HMAC of a per-boot nonce.
  * Encrypt the USB whitelist with a key derived from the OS password.
  * Use pyudev (Linux) or WMI event subscriptions (Windows) instead of
    polling for USB presence.
  * Add a --bypass flag protected by a hashed password for demo safety.
  * Add a visual countdown bar to the popup during the Layer 3 timer.


--------------------------------------------------------------------------------
TROUBLESHOOTING
--------------------------------------------------------------------------------

  "No removable storage devices detected" with USB plugged in
      psutil did not see the drive. Open a Python shell and print
      psutil.disk_partitions() to check. If the drive does not appear,
      verify it is mounted and has a drive letter assigned.

  Serial shows as None repeatedly
      Ensure "wmi" is installed in the active virtual environment:
          pip install wmi
      If it is installed and serial is still None, the USB controller
      may not expose a serial. In that case set VERIFY_USB_SERIAL = False
      to test the rest of the flow, or switch to a different USB stick.

  Folder challenge never succeeds
      Check the log line "Desktop resolved to: ..." to verify the Desktop
      path. If it points somewhere unexpected, override get_desktop_path()
      in config.py or place the unlock folder at the reported path.

  Shutdown does not fire in real mode
      Ensure DEV_MODE = False in config.py. Run from an Administrator
      account on Windows. Check cerberus.log for "Failed to issue
      shutdown command" and adjust accordingly.

  Popup window flashes and disappears
      This should be fixed in the current version via wait_for_close().
      If it still happens, confirm main.py contains the two
      wait_for_close() calls near the end of main().

================================================================================
End of README
================================================================================