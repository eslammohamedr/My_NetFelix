"""Only connection metadata is exposed; RustDesk performs access authorization."""
import base64,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import laptop_control

class LaptopMetadata(unittest.TestCase):
 def setUp(self):
  self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
  self.path=Path(self.folder.name)/'laptops.json'
  self.value={'server':'192.168.1.15:21116','relay':'192.168.1.15:21117','key':base64.b64encode(bytes(32)).decode(),'devices':[{'id':'460687646','name':'Linux laptop','os':'Linux'}]}
 def save(self,value):self.path.write_text(json.dumps(value))
 def test_missing_setup_has_no_devices(self):self.assertEqual(laptop_control.snapshot(self.path)['devices'],[])
 def test_private_or_unknown_fields_are_never_returned(self):
  self.value.update(privateKey='must not be served',password='must not be served')
  self.value['devices'][0]['password']='must not be served'
  self.save(self.value);out=laptop_control.snapshot(self.path)
  self.assertEqual(set(out),{'server','relay','key','devices'})
  self.assertEqual(set(out['devices'][0]),{'id','name','os'})
  self.assertNotIn('must not be served',json.dumps(out))
 def test_malformed_server_key_and_device_urls_are_rejected(self):
  for key,value in [('server','http://evil.test/a'),('server','user@evil.test'),('key','not-a-public-key'),('devices',[{'id':'123/r@evil.test','name':'Bad','os':'Linux'}]),('devices',[{'id':'123','name':'Bad\nname','os':'Linux'}])]:
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):
    self.save({**self.value,key:value});laptop_control.snapshot(self.path)
