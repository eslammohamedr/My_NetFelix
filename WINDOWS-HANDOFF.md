# Continue NetFelix laptop control on Windows

User intent: set up this Windows laptop for control from the existing Android NetFelix Companion, including automatic password authentication and a Windows host service that starts with Windows. Continue the implementation and verification; do not just repeat instructions.

The Linux computer remains the running NetFelix server at 192.168.1.15. Copy the project for Windows work; do not remove the live Linux folder or migrate/start the Linux Docker stack on Windows as part of this task.

## Ready now

- Download the prepared package on the same LAN: http://192.168.1.15:8092/downloads/netfelix-windows-setup.zip
- Or use config/laptop-control-windows.zip in a full local copy of this project (ignored by Git).
- ZIP contains the official unmodified RustDesk 1.5.0 x64 EXE, Setup-Windows.cmd, Setup-Windows.ps1, public server-settings.json, and READ-ME.txt.
- Installer SHA-256: 8555777215510d83d2d61c9dc984e4fcc838bd7e79f9d18a42585431f5e8bb47
- Public metadata can be fetched from http://192.168.1.15:8092/api/laptops. Never publish or reuse Linux private server keys as Windows client settings.
- ID server 192.168.1.15:21116; relay 192.168.1.15:21117. Public key is in package server-settings.json or the API. Leave API server blank.
- Android Companion 1.2.2 and official RustDesk Android 1.5.0 are installed. Laptops has Add laptop, View and control, Transfer files.

## Work to do on Windows

1. Inspect the actual Windows environment and existing RustDesk setup first. Preserve unrelated existing configuration. Verify the bundled installer checksum before execution.
2. Install RustDesk as a Windows service, rather than leaving only a portable process. The user authorizes setup; they still need to accept Windows UAC prompts when shown.
3. Configure the existing private ID/relay server and public key. The setup script copies RustDesk's public import code to the clipboard. It currently opens the installer/instructions; it does NOT perform a complete unattended installation.
4. Set a NEW strong permanent password for this Windows laptop and choose Accept sessions via password / Use permanent password. Do not put the password into repository files, API metadata, command output, or connection URLs. Do not change the Windows login password or enable Windows automatic login.
5. Verify the RustDesk service is running and starts automatically. Record the real Windows RustDesk ID.
6. Add Windows to Companion > Laptops using its ID without spaces. On first connection enter the Windows RustDesk password and select Remember password. USB/wireless ADB pairing may need to be established on Windows; the Linux ADB authorization does not automatically carry over.
7. Test screen, actual finger clicks, keyboard and a generated file transfer fixture. Only capture owned test windows, not personal files. Verify a fresh reconnect needs neither a local Accept click nor a password prompt. A reboot test needs user coordination; do not reboot while they are working.
8. Record real results and any unverified steps in docs/test-results/laptop-control/. Do not claim Windows was already tested: only the ZIP download, public-field filtering and EXE checksum have been verified from Linux.

## Existing Linux state

Linux RustDesk ID 460687646 uses the physical X11 :0 desktop and a remembered permanent password on the phone. The enabled user service netfelix-desktop.service restarts the host after an exit. Actual crash recovery and phone reconnection were verified. Server containers netfelix-desktop-rendezvous and netfelix-desktop-relay are configured with restart: unless-stopped; Docker is boot-enabled. Keep this computer awake and connected.

Source/setup details: remote-desktop/README.md, remote-desktop/prepare-windows.py, remote-desktop/windows/, scripts/laptop_control.py. The download is generated locally under ignored config/; it is not available from a Git clone alone.

## Session continuation

Copying this project does not by itself transfer a Codex conversation or grant access to Windows. Open a local Codex project on Windows and attach the copied folder. If the earlier chat is not available there, start a new local chat and ask: "Read WINDOWS-HANDOFF.md and complete Windows host setup and phone control tests."
