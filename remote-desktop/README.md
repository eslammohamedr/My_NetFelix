# NetFelix laptop control — Linux first

The Android companion has a **Laptops** screen. It opens live screen, mouse/keyboard and file-transfer sessions in the unmodified RustDesk Android client. This is an integration with RustDesk, not a new remote-desktop engine. Windows uses the same client/protocol but is deferred until the Linux connection has been tested.

## Installed setup

- Own rendezvous/relay: `docker compose -f remote-desktop/compose.yml up -d`.
- RustDesk Server OSS 1.1.16, pinned by container digest. LAN bindings only: 192.168.1.15 TCP 21115–21117 and UDP 21116. WebSocket ports are not published.
- Linux RustDesk 1.5.0 lives under `~/.local/share/netfelix-tools/rustdesk/linux/`; no root package installation was needed. Release SHA-256 is checked by `install-linux.py`.
- Linux host: enabled user service `netfelix-desktop.service`, with `Restart=always` and a five-second recovery delay. It starts with the user session and retries while waiting for the physical X11 desktop. The menu/login launcher `~/.local/bin/netfelix-desktop` starts this service without launching duplicate clients. The host uses physical X11 `:0` (1366×768), rather than the separate xrdp `:10` session.
- The client registered successfully with the private server. At the user’s request, Linux now accepts authenticated sessions automatically: **Accept sessions via password**, **Use permanent password**. A strong random password was configured through RustDesk’s settings and remembered by the phone’s RustDesk client. No password is placed in the companion API, connection links, or repository.
- Private keys and live metadata are in ignored `config/rustdesk-server/` and `config/laptop-control.json`. `/api/laptops` only exposes the validated server public key, addresses and saved laptop IDs/names. It does not execute remote commands or expose private keys/passwords.
- Companion 1.2.2 and upstream RustDesk 1.5.0 were installed on the phone through its authorized wireless-debugging connection.

## Use

1. Unlock the phone and open NetFelix Companion → **Laptops**.
2. Select **Linux laptop → View and control**. RustDesk opens a connection to the private server with its public key pinned in the connection URI.
3. The saved RustDesk password authenticates the phone automatically; the Linux laptop does not need an Accept click. A new phone needs the password configured in RustDesk.
4. RustDesk provides the live screen and its touch/mouse and keyboard controls. Use **Transfer files** for a file-transfer session with the same authentication policy.

The Linux user must be logged into the physical X11 desktop. Pre-login, Wayland and wake-from-sleep access are not configured. This Linux setup does not install or control anything on the Windows laptop.

To restore manual approval, open RustDesk on Linux → Settings → Security → Password → **Accept sessions via click**. To change or revoke saved access, change the permanent password there; the phone will need the new password. The user-space agent still requires an awake laptop and a logged-in physical X11 session.

## Windows setup package

Prepare/update the Windows x64 package with `python3 remote-desktop/prepare-windows.py`. It verifies the cached official RustDesk 1.5.0 executable and bundles it with public server settings and instructions. The generated ZIP is ignored at `config/laptop-control-windows.zip` and served at `http://192.168.1.15:8092/downloads/netfelix-windows-setup.zip`.

Extract the ZIP on Windows and run `Setup-Windows.cmd`. It checks the installer hash, copies the public RustDesk import code to the clipboard and opens the installer plus instructions. Install RustDesk as a Windows service, import/enter the private server settings, and set a new permanent password on Windows. Save the displayed Windows ID in Companion → Laptops → Add laptop; remember its password in the phone’s RustDesk client on first connection. The Linux server must remain on for private rendezvous/relay.

Package download, executable checksum and public-only metadata were verified on Linux. Windows execution, service startup after reboot and phone-to-Windows control still need verification on the Windows laptop. No Windows access password is bundled or sent to the API.

## Reinstall / maintain

Run `python3 remote-desktop/install-linux.py` from this checkout to restore the verified user-space client, enable/start its supervised user service, and restore login startup. It refuses to overwrite an unrelated existing RustDesk configuration. To stop the server, run `docker compose -f remote-desktop/compose.yml down`; persisted keys remain in `config/`.

The Android client installer is also served at `/downloads/netfelix-desktop-engine.apk`. Companion backup: `/home/dell/Downloads/NetFelix-Companion-1.2.2.apk`.

## Validation status

- Fixed host going offline when its unsupervised process stopped. Verified the enabled service automatically starts a new host process after a forced process termination. Docker is also enabled at boot; both private-server containers already use `restart: unless-stopped`. See `docs/test-results/laptop-control/host-service.json`.

- Automatic authentication verified after stopping and reopening the Android RustDesk process: live test screen displayed with no password dialog and no Linux Accept click. Evidence: `docs/test-results/laptop-control/automatic-acceptance.png` and `build.json`. Temporary plaintext enrollment password was deleted after RustDesk saved it; no credential was added to API metadata.

- Linux binary dependencies resolved; physical desktop access confirmed.
- Client ID registered in the private rendezvous database.
- Metadata validation and private-field filtering tests passed.
- Companion assemble/lint passed; APK installed on the phone.
- Live physical desktop screen verified on the phone. The user confirmed real finger clicks; the Linux fixture recorded 10 clicks. Lowercase keyboard text arrived exactly as expected. Evidence: `docs/test-results/laptop-control/live-input.json`.
- File-transfer connection approved on Linux and remote file listing verified. A completed download has not been verified.
- Corrected connection URI path escaping and verified that RustDesk opens in its own Android task. Reopening Companion returns to its controls.
- Companion 1.2.2 assemble/lint and three metadata tests passed; installed APK matches the build. Temporary fixtures were removed, phone screen timeout restored, and the test screensaver inhibitor released.

Sources: [RustDesk project and source](https://github.com/rustdesk/rustdesk), [self-hosted Docker setup](https://rustdesk.com/docs/en/self-host/rustdesk-server-oss/docker/), [approval settings](https://rustdesk.com/docs/en/self-host/client-configuration/advanced-settings/), [Linux client](https://rustdesk.com/docs/en/client/linux/). Upstream client binaries remain unmodified and retain their upstream license/attribution.

## Repository handoff

Source code and public setup instructions are versioned. Generated installers, device captures, game libraries, vendor downloads, and live `config/` data stay local. Download the prepared Windows ZIP from the LAN link above. A fresh server deployment needs `.env` populated from `.env.example`; service credentials are loaded from that ignored local file rather than embedded in source.
