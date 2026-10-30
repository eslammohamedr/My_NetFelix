"""Public connection metadata for paired laptops; desktop access is authorized by RustDesk."""
import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / 'config/laptop-control.json'
WINDOWS_BUNDLE = CONFIG.parent / 'laptop-control-windows.zip'
CLIENT_APK = Path.home() / '.local/share/netfelix-tools/rustdesk/rustdesk-1.5.0-aarch64-signed.apk'


def snapshot(path=None):
    file = Path(path) if path else CONFIG
    if not file.is_file():
        return {'server':'', 'relay':'', 'key':'', 'devices':[]}
    data = json.loads(file.read_text())
    result = {}
    for key in ('server','relay'):
        value = data.get(key, '')
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9.-]+(?::[0-9]{1,5})?',value):
            raise ValueError('Invalid desktop server')
        result[key] = value
    public_key = data.get('key')
    if not isinstance(public_key,str) or not re.fullmatch(r'[A-Za-z0-9+/]{43}=',public_key):
        raise ValueError('Invalid server public key')
    result['key'] = public_key
    devices = data.get('devices',[])
    if not isinstance(devices,list) or len(devices)>30:
        raise ValueError('Invalid device list')
    result['devices'] = []
    for device in devices:
        if not isinstance(device,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{3,64}',str(device.get('id',''))):
            raise ValueError('Invalid laptop ID')
        name = device.get('name','')
        if not isinstance(name,str) or not 1<=len(name)<=64 or any(ord(c)<32 for c in name):
            raise ValueError('Invalid laptop name')
        os_name = device.get('os')
        if os_name not in ('Linux','Windows','macOS'):
            raise ValueError('Unknown laptop system')
        result['devices'].append({'id':device['id'],'name':name,'os':os_name})
    return result


def handle_get(handler,path):
    if path == '/api/laptops':
        try:
            handler._send_json(200,snapshot())
        except (OSError,ValueError,TypeError):
            handler._send_json(503,{'error':'Laptop setup is unavailable'})
    elif path == '/downloads/netfelix-windows-setup.zip':
        if not WINDOWS_BUNDLE.is_file():
            handler._send_json(404,{'error':'Windows setup has not been prepared'})
        else:
            import tv_settings
            tv_settings.send_bytes(handler,WINDOWS_BUNDLE.read_bytes(),'application/zip')
    elif path == '/downloads/netfelix-desktop-engine.apk':
        if not CLIENT_APK.is_file():
            handler._send_json(404,{'error':'Desktop client has not been downloaded'})
        else:
            import tv_settings
            tv_settings.send_bytes(handler,CLIENT_APK.read_bytes(),'application/vnd.android.package-archive')
    else:
        return False
    return True
