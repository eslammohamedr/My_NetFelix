import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import samsung_tv

class ConnectionTests(unittest.TestCase):
    def connect(self, ws):
        module=types.SimpleNamespace(create_connection=MagicMock(return_value=ws))
        with patch.dict(sys.modules, {'websocket':module}), patch.object(samsung_tv,'load_token',return_value=None):
            return samsung_tv.connect_tv_ws(timeout=1)
    def test_waits_for_authorization(self):
        ws=MagicMock();ws.recv.side_effect=[json.dumps({'event':'unrelated'}),json.dumps({'event':'ms.channel.connect'})]
        self.assertIs(self.connect(ws),ws)
        self.assertEqual(ws.recv.call_count,2);ws.close.assert_not_called()
    def test_rejection_closes_connection(self):
        ws=MagicMock();ws.recv.return_value=json.dumps({'event':'ms.channel.unauthorized'})
        with self.assertRaises(PermissionError):self.connect(ws)
        ws.close.assert_called_once()
    def test_missing_authorization_closes_connection(self):
        ws=MagicMock();ws.recv.side_effect=TimeoutError('timeout')
        with self.assertRaises(TimeoutError):self.connect(ws)
        ws.close.assert_called_once()
    def test_closed_socket_is_not_accepted(self):
        ws=MagicMock();ws.recv.return_value=''
        with self.assertRaises(ConnectionError):self.connect(ws)
        ws.close.assert_called_once()
if __name__=='__main__':unittest.main()
