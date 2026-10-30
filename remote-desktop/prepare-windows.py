#!/usr/bin/env python3
"""Bundle the verified Windows client with public server setup, never credentials."""
import base64
import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from laptop_control import snapshot

EXPECTED = '8555777215510d83d2d61c9dc984e4fcc838bd7e79f9d18a42585431f5e8bb47'

def main():
    source = Path.home() / '.local/share/netfelix-tools/rustdesk/rustdesk-1.5.0-x86_64.exe'
    if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Verified RustDesk 1.5.0 Windows installer not available')
    config = snapshot()
    if not config['server']:
        raise SystemExit('Configure the private server first')
    public = {k: config[k] for k in ('server', 'relay', 'key')}
    exported = json.dumps(dict(host=public['server'], relay=public['relay'], api='', key=public['key']), separators=(',', ':'))
    public['importCode'] = base64.urlsafe_b64encode(exported.encode()).decode().rstrip('=')[::-1]
    text = f'''NETFELIX WINDOWS LAPTOP SETUP (Windows 10/11 x64)

1. Connect Windows to the same home network as the Linux server.
2. Extract the entire ZIP, then double-click Setup-Windows.cmd.
3. RustDesk opens. Choose Install (not just portable mode), and accept the
   Windows administrator prompt. This installs the Windows startup service.
4. In RustDesk: Settings > Network > Unlock network settings > ID/Relay server.
   Use Import from clipboard if available (the setup copied the public config).
   Otherwise enter:
     ID server: {public['server']}
     Relay server: {public['relay']}
     Key: {public['key']}
     API server: leave blank
5. In Settings > Security, unlock settings if asked. Set a NEW permanent password
   for this Windows laptop. Select Use permanent password and Accept sessions
   via password. Do not reuse the Windows login password.
6. In Settings > General > Service control, confirm the service is running.
   Keep the laptop awake and connected to the network.
7. Note the ID displayed under Your Desktop.
8. On your phone: NetFelix Companion > Laptops > Add laptop.
   Name: Windows laptop. Laptop ID: the ID from step 7 (without spaces).
   Save, then View and control. Enter the permanent password and enable
   Remember password in RustDesk. Later connections need no Accept click.

The Linux server must stay on because it hosts the private connection server.
The Windows installer is official, unmodified RustDesk 1.5.0.
No access password or private server key is included in this ZIP.
Windows installation, restart and phone control still require live verification.

Official documentation: https://rustdesk.com/docs/en/client/windows/
'''
    out = REPO / 'config/laptop-control-windows.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(source, source.name)
        handoff = REPO / 'WINDOWS-HANDOFF.md'
        if handoff.is_file():
            bundle.write(handoff, handoff.name)
        for name in ('Setup-Windows.cmd', 'Setup-Windows.ps1'):
            bundle.write(REPO / 'remote-desktop/windows' / name, name)
        bundle.writestr('server-settings.json', json.dumps(public, indent=2))
        bundle.writestr('READ-ME.txt', text.replace('\n', '\r\n'))
    print(f'Windows setup ready: {out} ({out.stat().st_size} bytes)')

if __name__ == '__main__':
    main()
