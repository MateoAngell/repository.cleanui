import importlib.util
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

properties = {}
root = None
home = types.SimpleNamespace(getProperty=lambda k: properties.get(k, ''),
    setProperty=lambda k,v: properties.__setitem__(k,v), clearProperty=lambda k: properties.pop(k,None))
sys.modules['xbmc'] = types.SimpleNamespace(
    getInfoLabel=lambda k:'12' if 'Memory' in k else '', getCondVisibility=lambda k:False,
    executeJSONRPC=lambda s:json.dumps({'result': [] if 'GetActivePlayers' in s else {}}),
    Player=object, Monitor=lambda:types.SimpleNamespace(abortRequested=lambda:False))
sys.modules['xbmcgui'] = types.SimpleNamespace(Window=lambda n:home)
sys.modules['xbmcaddon'] = types.SimpleNamespace(Addon=lambda *a:types.SimpleNamespace(getAddonInfo=lambda k:str(root) if k=='profile' else '0.1.0'))
sys.modules['xbmcvfs'] = types.SimpleNamespace(translatePath=lambda p:str(root/p.split('/')[-1]))
sys.path.insert(0, str(Path(__file__).parent/'diagnostics'))
spec=importlib.util.spec_from_file_location('diag',Path(__file__).parent/'diagnostics/core.py')
diag=importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        global root
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        properties.clear()

    def test_secrets_are_dropped(self):
        for key in ('token', 'Authorization', 'Cookie', 'license', 'pssh', 'profile', 'userdata', 'password'):
            self.assertIsNone(diag.sanitize_line('ERROR CVideoPlayer '+key+'=private'))
        self.assertIsNone(diag.sanitize_line('addon arbitrary account output'))

    def test_urls_addresses_paths_and_quoted_strings_are_redacted(self):
        raw='ERROR CVideoPlayer https://host/movie?id=opaque 192.168.1.5 "person name" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        clean=diag.sanitize_line(raw)
        for secret in ('host', 'movie', 'opaque', '192.168', 'person name', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.assertNotIn(secret, clean)
        self.assertIn('CVideoPlayer', clean)
        self.assertIn('buffer', diag.sanitize_line('WARNING CVideoPlayer buffer underrun'))
        self.assertNotIn('Mateo',diag.sanitize_line('ERROR CVideoPlayer C:\\Users\\Mateo\\private.mp4'))
        self.assertNotIn('Mateo',diag.sanitize_line('ERROR CVideoPlayer stalled Mateo unquoted'))

    def test_rotation_is_bounded_and_preserves_whole_json(self):
        writer=diag.Journal(root,limit=100)
        for i in range(20): writer.write({'event':'sample','time':i})
        for path in (writer.path,writer.previous):
            self.assertLessEqual(path.stat().st_size,100)
            for line in path.read_text().splitlines():json.loads(line)

    def test_snapshot_and_cache_are_allowlisted(self):
        (root/'advancedsettings.xml').write_text('<advancedsettings><cache><memorysize>1234</memorysize></cache><secret>password</secret></advancedsettings>')
        state=diag.snapshot(True)
        self.assertEqual(state['advanced_cache'],{'memorysize':'1234'})
        self.assertIsNone(state['labels']['System.CpuUsage'])
        self.assertNotIn('password',json.dumps(state))
        self.assertIsNone(state['cleanui']['slyguy.max.cleanui'])

    def test_report_uses_only_known_files_and_sanitized_logs(self):
        (root/'credentials.json').write_text('DO_NOT_EXPORT')
        (root/'kodi.log').write_text('header\nERROR CVideoPlayer buffer underrun\nERROR CVideoPlayer token=secret\n')
        report=diag.report()
        with zipfile.ZipFile(report) as z:
            self.assertNotIn('credentials.json',z.namelist())
            self.assertNotIn('secret',z.read('kodi.log').decode())
            self.assertIn('underrun',z.read('kodi.log').decode())
            self.assertEqual(z.testzip(),None)

    def test_stale_owner_is_not_recording_and_live_owner_is(self):
        properties[diag.ACTIVE]='old'
        properties[diag.BEAT]='0'
        self.assertFalse(diag.recording())
        properties[diag.BEAT]=str(diag.time.time())
        self.assertTrue(diag.recording())
        diag.record('different')
        self.assertFalse((root/'session.json').exists())

    def test_record_stop_releases_owner_and_builds_report(self):
        token='this-request'
        properties[diag.ACTIVE]=token
        calls=[]
        def wait(seconds):
            calls.append(seconds)
            properties[diag.STOP]=token
            return False
        with patch.object(diag.xbmc,'Monitor',return_value=types.SimpleNamespace(
                abortRequested=lambda:False,waitForAbort=wait)):
            diag.record(token)
        self.assertEqual(calls,[5])
        self.assertNotIn(diag.ACTIVE,properties)
        self.assertEqual(json.loads((root/'session.json').read_text())['status'],'finished')
        self.assertTrue((root/'latest-report.zip').exists())

    def test_late_release_cannot_clear_new_owner(self):
        properties[diag.ACTIVE]='new'
        diag.release('old')
        self.assertEqual(properties[diag.ACTIVE],'new')

    def test_resource_summary_cannot_inject_free_text(self):
        properties['cleanui.resources.slyguy.max.cleanui']=json.dumps({'stage':'secret', 'cards':'token=private', 'windows':1})
        result=diag.snapshot()['cleanui']['slyguy.max.cleanui']
        self.assertIsNone(result['cards'])
        self.assertIsNone(result['stage'])
        self.assertEqual(result['windows'],1)


if __name__=='__main__':unittest.main()
