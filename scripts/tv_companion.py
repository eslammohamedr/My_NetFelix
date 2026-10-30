"""LAN discovery and short-lived commands for the NetFelix dashboard."""
import json
import socket
import threading
import time
import uuid
from collections import deque

DISCOVERY_PORT = 8093
KEYS = {"UP":38, "DOWN":40, "LEFT":37, "RIGHT":39, "ENTER":13, "RETURN":10009,
        "HOME":36, "PLAY":415, "PAUSE":19, "STOP":413, "REWIND":412, "FF":417}
NATIVE_KEYS = set(KEYS) | {"VOLUP", "VOLDOWN", "MUTE", "CHUP", "CHDOWN"}


class CommandBus:
    def __init__(self):
        self.lock = threading.Lock()
        self.commands = deque(maxlen=50)
        self.sequence = 0
        self.epoch = uuid.uuid4().hex
        self.last_seen = 0

    def send(self, body):
        kind = body.get("kind")
        if kind == "key":
            if body.get("key") not in KEYS:
                raise ValueError("Unsupported dashboard key")
            command = {"kind":"key", "key":body["key"], "code":KEYS[body["key"]]}
        elif kind == "text":
            text = body.get("text")
            if not isinstance(text, str) or len(text) > 500 or any(ord(c) < 32 for c in text):
                raise ValueError("Enter up to 500 printable characters")
            command = {"kind":"text", "text":text}
        else:
            raise ValueError("Unknown remote command")
        with self.lock:
            if not self.last_seen or time.monotonic() - self.last_seen > 5:
                raise ValueError("Open NetFelix Home on the TV before using dashboard controls")
            self.sequence += 1
            command.update(sequence=self.sequence, expires=time.monotonic()+5)
            self.commands.append(command)
        return {"success":True, "message":"Command sent to NetFelix"}

    def poll(self, after=None, epoch=None):
        with self.lock:
            self.last_seen = time.monotonic()
            # First contact never replays another TV session's commands.
            commands = [] if epoch != self.epoch else [
                {k:v for k,v in c.items() if k != "expires"}
                for c in self.commands if c["sequence"] > after and c["expires"] > time.monotonic()]
            return {"epoch":self.epoch, "sequence":self.sequence, "commands":commands}

    def online(self):
        with self.lock:
            return self.last_seen > 0 and time.monotonic() - self.last_seen < 5


BUS = CommandBus()


def discovery_response(data):
    """Small versioned handshake; no server paths or household data are disclosed."""
    if len(data) > 200:
        return None
    try:
        query = json.loads(data)
        nonce = query.get("nonce")
        if query.get("service") != "netfelix-discover" or not isinstance(nonce, str) or len(nonce) != 32:
            return None
        return json.dumps({"service":"netfelix-companion", "version":1, "port":8092, "nonce":nonce}).encode()
    except (ValueError, AttributeError, UnicodeError):
        return None


def start_discovery():
    def listen():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", DISCOVERY_PORT))
                while True:
                    data, peer = sock.recvfrom(256)
                    response = discovery_response(data)
                    if response:
                        sock.sendto(response, peer)
        except OSError:
            # Manual server entry remains available when discovery cannot bind.
            import logging
            logging.getLogger(__name__).exception("Companion LAN discovery unavailable")
    threading.Thread(target=listen, name="companion-discovery", daemon=True).start()
