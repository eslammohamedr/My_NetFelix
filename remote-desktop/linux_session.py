#!/usr/bin/env python3
"""Launch against the physical user's desktop, including its session bus."""
import os
import sys
from pathlib import Path

MANAGERS={'xfce4-session','gnome-session-binary','gnome-session','mate-session','cinnamon-session','lxqt-session','startplasma-x11'}
BASE={'HOME','USER','LOGNAME','SHELL','PATH','LANG','LC_ALL','DISPLAY','XAUTHORITY','DBUS_SESSION_BUS_ADDRESS','XDG_SESSION_TYPE','XDG_SESSION_ID','XDG_CURRENT_DESKTOP','DESKTOP_SESSION','XDG_RUNTIME_DIR','PULSE_SERVER','PULSE_COOKIE','SESSION_MANAGER','GTK_THEME','GDK_BACKEND'}

def desktop_environment():
    source=None
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit():continue
        try:
            if folder.stat().st_uid!=os.getuid():continue
            command=(folder/'cmdline').read_bytes().split(b'\0')[0].decode()
            if Path(command).name not in MANAGERS:continue
            values={k.decode():v.decode() for k,v in (x.split(b'=',1) for x in (folder/'environ').read_bytes().split(b'\0') if b'=' in x)}
            if values.get('DISPLAY')==':0' and values.get('DBUS_SESSION_BUS_ADDRESS'):
                source=values;break
        except (OSError,UnicodeError):continue
    if source is None:raise RuntimeError('Log into the physical X11 desktop before starting laptop control')
    # Do not pass unrelated API tokens from a terminal/automation environment.
    env={k:v for k,v in os.environ.items() if k in BASE or k.startswith('LC_')}
    env.update({k:v for k,v in source.items() if k in BASE or k.startswith('LC_')})
    env['DISPLAY']=':0';env.setdefault('XAUTHORITY',str(Path.home()/'.Xauthority'))
    return env

if __name__=='__main__':
    binary=Path.home()/'.local/share/netfelix-tools/rustdesk/linux/usr/share/rustdesk/rustdesk'
    os.execve(binary,[str(binary),*sys.argv[1:]],desktop_environment())
