#!/usr/bin/env python3
"""Install the verified user-space Linux client; preserve existing unrelated setup."""
import hashlib,json,os,shlex,shutil,subprocess,urllib.request
from pathlib import Path

VERSION='1.5.0'
SHA256='4e2b9701d25a7ef373f3d09bda584a37d6902f97a6ab15f2e86d4a5783e2a0ec'
REPO=Path(__file__).resolve().parents[1]

def install():
    setup=json.loads((REPO/'config/laptop-control.json').read_text())
    if not setup.get('server') or not setup.get('key'):
        raise SystemExit('Start the private server and create config/laptop-control.json first')
    tools=Path.home()/'.local/share/netfelix-tools/rustdesk';tools.mkdir(parents=True,exist_ok=True)
    archive=tools/f'rustdesk-{VERSION}-x86_64.deb'
    if not archive.exists():
        urllib.request.urlretrieve(f'https://github.com/rustdesk/rustdesk/releases/download/{VERSION}/{archive.name}',archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise SystemExit('Client checksum does not match the verified release; refusing to run it')
    directory=tools/'linux'
    binary=directory/'usr/share/rustdesk/rustdesk'
    installed_version = subprocess.check_output([str(binary),'--version'],text=True).strip() if binary.is_file() else ''
    if installed_version != VERSION:
        subprocess.run(['dpkg-deb','-x',str(archive),str(directory)],check=True)
    config=Path.home()/'.config/rustdesk/RustDesk2.toml';config.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if config.exists():
        text=config.read_text()
        if setup['server'] not in text or setup['key'] not in text:
            raise SystemExit('Existing RustDesk configuration preserved. Import the new server through its Settings UI.')
    else:
        config.write_text('rendezvous_server = '+json.dumps(setup['server'])+'\nnat_type = 0\nserial = 0\n\n[options]\ncustom-rendezvous-server = '+json.dumps(setup['server'])+'\nrelay-server = '+json.dumps(setup['relay'])+'\nkey = '+json.dumps(setup['key'])+'\napprove-mode = "click"\n')
        config.chmod(0o600)
    binary=directory/'usr/share/rustdesk/rustdesk'
    launcher=Path.home()/'.local/bin/netfelix-desktop';launcher.parent.mkdir(parents=True,exist_ok=True)
    session_launcher=tools/'linux_session.py';shutil.copy2(REPO/'remote-desktop/linux_session.py',session_launcher)
    # The desktop entry and menu start the supervised host, rather than a second client.
    runtime='/run/user/'+str(os.getuid())
    service_dir=Path.home()/'.config/systemd/user';service_dir.mkdir(parents=True,exist_ok=True)
    shutil.copy2(REPO/'remote-desktop/netfelix-desktop.service',service_dir/'netfelix-desktop.service')
    launcher.write_text('#!/bin/sh\nexec /usr/bin/busctl --quiet --address='+shlex.quote('unix:path='+runtime+'/bus')+' call org.freedesktop.systemd1 /org/freedesktop/systemd1 org.freedesktop.systemd1.Manager StartUnit ss netfelix-desktop.service replace\n');launcher.chmod(0o755)
    # Use the real user session bus: XFCE/xrdp may export a different desktop bus,
    # and the manager's optional private control socket can be stale.
    manager=['busctl','--quiet','--address=unix:path='+runtime+'/bus','call','org.freedesktop.systemd1','/org/freedesktop/systemd1','org.freedesktop.systemd1.Manager']
    subprocess.run(manager+['Reload'],check=True)
    subprocess.run(manager+['EnableUnitFiles','asbb','1','netfelix-desktop.service','false','true'],check=True)
    subprocess.run(manager+['StartUnit','ss','netfelix-desktop.service','replace'],check=True)
    icon=next(iter(directory.glob('usr/share/icons/**/rustdesk.png')),None)
    desktop='[Desktop Entry]\nType=Application\nName=NetFelix Laptop Control (RustDesk)\nComment=Encrypted laptop sessions with authentication\nExec="'+str(launcher).replace('"','\\"')+'"\nTerminal=false\nCategories=Network;RemoteAccess;\n'
    if icon:desktop+='Icon='+str(icon)+'\n'
    for parent in (Path.home()/'.local/share/applications',Path.home()/'.config/autostart'):
        parent.mkdir(parents=True,exist_ok=True)
        entry=parent/'netfelix-desktop.desktop'
        if entry.exists() and 'NetFelix Laptop Control (RustDesk)' not in entry.read_text():
            raise SystemExit('Existing desktop entry preserved: '+str(entry))
        entry.write_text(desktop)
    print('Supervised Linux host and login startup installed. The laptop must be logged in to its physical X11 session.')

if __name__=='__main__':install()
