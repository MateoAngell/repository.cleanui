"""Focused checks for privacy, bounded capture, cancellation and transfer."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'diagnostics'))
import protocol
import collector
from test_diagnostics import diag, properties, home


def load_service():
    sys.modules['core'] = diag
    spec = importlib.util.spec_from_file_location('automatic_service', Path(__file__).parent/'diagnostics/service.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProtocolTests(unittest.TestCase):
    def test_no_arbitrary_text_or_accounts(self):
        clean = protocol.safe_log('ERROR CVideoPlayer stalled Alice Smith https://private/stream 192.0.2.99')
        self.assertNotIn('Alice', clean)
        self.assertNotIn('private', clean)
        self.assertNotIn('192.0.2', clean)
        self.assertIn('stalled', clean)
        self.assertIsNone(protocol.safe_log('ERROR CVideoPlayer token=private'))
        self.assertIn('typeerror', protocol.safe_log('TypeError: private title'))
        clean = protocol.safe_log('  File "/private/controller.py", line 33, in arbitrarymethod')
        self.assertIn('controller.py', clean)
        self.assertNotIn('arbitrarymethod', clean)

    def test_malformed_events_fail_closed(self):
        for value in (None, [], {'addon': [], 'event': []}, {'addon':'other', 'event':'started'}):
            self.assertIsNone(protocol.event_input(value))
        self.assertIsNone(protocol.number(10**1000))
        self.assertIsNone(protocol.number(float('nan')))
        state = protocol.snapshot_input({'labels':[], 'cleanui':None, 'settings': {'password':'bad'}})
        self.assertEqual(state['labels'], {})
        self.assertEqual(state['settings'], {})
        event = protocol.event_input({'addon':protocol.ADDONS[0], 'event':'activation',
            'session':'x'*32, 'data':{'control':1, 'title':'PRIVATE', 'screen':[]}})
        self.assertEqual(event['data'], {'control':1})
        self.assertNotIn('session',event)


class AutomaticTests(unittest.TestCase):
    def setUp(self):
        import test_diagnostics
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        test_diagnostics.root = self.root
        properties.clear()

    def run_capture(self, enabled=True, notification=False, error=False):
        settings = {'capture_enabled':'true' if enabled else 'false'}
        class Monitor:
            calls = 0
            def abortRequested(self): return self.calls >= 3
            def waitForAbort(self, seconds):
                self.calls += 1
                if notification:
                    self.onNotification('cleanui.diagnostics','Other.cleanui.diagnostics.event',
                        json.dumps({'addon':protocol.ADDONS[0], 'event':'activation',
                            'data':{'control':7, 'title':'DO_NOT_STORE'}}))
                    self.onNotification('another','Other.cleanui.diagnostics.event','{}')
                return self.calls >= 3
        addon = types.SimpleNamespace(getSetting=lambda k:settings[k],
            setSetting=lambda k,v:settings.__setitem__(k,v), getAddonInfo=lambda k:str(self.root))
        with patch.object(diag.xbmc,'Monitor',Monitor), patch.object(diag.xbmc,'Player',object), patch.object(diag.xbmcaddon,'Addon',return_value=addon):
            service = load_service()
            with patch.object(diag, 'snapshot', return_value={'process':{'cpu_seconds':0},'playing':False}), patch.object(diag,'log_extract',return_value=''), patch.object(service.LogTail,'read',return_value=([],0)), patch.object(service.time,'monotonic',side_effect=lambda:time.perf_counter()):
                if error:
                    with patch.object(diag.Journal,'write',side_effect=OSError('disk full')):
                        service.run()
                else:
                    service.run()

    def test_single_service_events_and_shutdown_cleanup(self):
        self.run_capture(notification=True)
        events = [json.loads(x) for x in (self.root/'samples.jsonl').read_text().splitlines()]
        self.assertTrue(any(x['event']=='activation' for x in events))
        self.assertTrue(any(x['event']=='sample' for x in events))
        self.assertEqual(events[-1]['event'],'finished')
        self.assertNotIn('DO_NOT_STORE',json.dumps(events))
        self.assertNotIn(diag.ACTIVE, properties)
        self.assertFalse((self.root/'latest-report.zip').exists())
        state = json.loads((self.root/'transfer.json').read_text())
        self.assertEqual(state['status'],'finished')
        self.assertTrue(state['files'])

    def test_disabled_never_captures_old_logs_or_events(self):
        (self.root/'session.json').write_text('{"status":"recording"}')
        self.run_capture(enabled=False,notification=True)
        self.assertFalse((self.root/'samples.jsonl').exists())
        self.assertFalse((self.root/'kodi.jsonl').exists())
        self.assertFalse(json.loads((self.root/'transfer.json').read_text())['capture_enabled'])

    def test_disk_failure_releases_owner(self):
        self.run_capture(error=True)
        self.assertNotIn(diag.ACTIVE,properties)
        self.assertEqual(json.loads((self.root/'transfer.json').read_text())['status'],'capture_error')

    def test_previous_unfinished_session_is_marked_not_declared_crash(self):
        (self.root/'session.json').write_text('{"status":"recording","started":123}')
        self.run_capture()
        self.assertIn('"event": "recovered"',(self.root/'samples.jsonl').read_text())

    def test_log_tail_rotation_and_partial_lines(self):
        with patch.object(diag.xbmc,'Monitor',object):
            service=load_service()
        path=self.root/'kodi.log'
        path.write_bytes(b'ERROR CVideoPlayer buffer')
        tail=service.LogTail()
        self.assertEqual(tail.read()[0],[])
        with path.open('ab') as stream: stream.write(b' underrun\n')
        self.assertIn('underrun',tail.read()[0][0])
        path.write_bytes(b'ERROR CVideoPlayer failed\n')
        self.assertIn('failed',tail.read()[0][0])
        self.assertEqual(tail.read()[0],[])


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.client=collector.Collector(self.root/'config.json',self.root/'records')
        self.raw=(json.dumps(dict(schema=1,boot='a'*32,seq=1,time=123,event='started',title='PRIVATE'))+'\n').encode()
        self.gen=hashlib.sha256(self.raw).hexdigest()
        self.transfer=dict(schema=1,capture_enabled=True,files=[
            dict(name='samples.jsonl',size=len(self.raw),generation=self.gen)])
        self.adb=types.SimpleNamespace(generation=lambda n:self.gen,read=lambda n,offset:self.raw[offset:])

    def test_incremental_and_rotation_dedup(self):
        self.client.sync(self.adb,self.transfer)
        self.client.sync(self.adb,self.transfer)
        self.transfer['files'][0]['name']='samples.previous.jsonl'
        self.client.sync(self.adb,self.transfer)
        path=next(self.client.root.glob('kodi-*.jsonl'))
        self.assertEqual(len(path.read_text().splitlines()),1)
        self.assertNotIn('PRIVATE',path.read_text())

    def test_rotation_race_is_discarded(self):
        self.adb.generation=lambda n:'b'*64
        self.client.sync(self.adb,self.transfer)
        self.assertFalse(list(self.client.root.glob('kodi-*.jsonl')))

    def test_partial_line_is_retried_not_lost(self):
        self.client.ingest('samples.jsonl',self.gen,self.raw[:-1])
        self.assertEqual(self.client.state['offsets'][self.gen],0)
        self.client.ingest('samples.jsonl',self.gen,self.raw)
        self.assertEqual(self.client.state['offsets'][self.gen],len(self.raw))

    def test_disabled_stops_android_and_unknown_files_are_not_read(self):
        self.transfer['capture_enabled']=False
        self.assertFalse(self.client.sync(self.adb,self.transfer))
        self.assertFalse(list(self.client.root.glob('kodi-*.jsonl')))
        self.transfer['capture_enabled']=True
        self.transfer['files'][0]['name']='../../credentials.json'
        with patch.object(self.adb,'read',side_effect=AssertionError('not permitted')):
            self.client.sync(self.adb,self.transfer)

    def test_retention_only_removes_own_old_journals(self):
        import os
        for name in ('kodi-20200101.jsonl','credentials.json','my-report.txt'):
            path=self.client.root/name
            path.write_text('private')
            os.utime(path,(0,0))
        self.client.prune()
        self.assertFalse((self.client.root/'kodi-20200101.jsonl').exists())
        self.assertTrue((self.client.root/'credentials.json').exists())
        self.assertTrue((self.client.root/'my-report.txt').exists())

    def test_wrong_device_never_selected(self):
        adb=collector.Adb(sys.executable,'adb-confirmed123')
        with patch.object(adb,'command',side_effect=[b'List of devices attached\nother device\n',
            b'other _adb-tls-connect._tcp 192.168.0.1:12345\n']) as command:
            with self.assertRaises(ConnectionError):adb.connect()
            self.assertEqual(command.call_count,2)
        with self.assertRaises(ValueError):adb.read('../private')

    def test_android_only_preserves_counters_and_exit_reasons(self):
        self.assertEqual(collector.android_metrics('TOTAL PSS: 1234\nAlice PRIVATE\nMemAvailable: 456 kB'),
            {'pss_kib':1234,'available_kib':456})
        parsed=collector.exit_metrics('ApplicationExitInfo #0: pid=123 reason=6 (ANR) status=0 description=PRIVATE')
        self.assertEqual(parsed,[{'pid':123,'reason':6,'status':0}])
        self.assertNotIn('PRIVATE',str(parsed))

    def test_missing_config_waits_without_creating_a_server(self):
        self.client.once()
        self.assertEqual(self.client.state['status'],'offline')


if __name__=='__main__':unittest.main()
