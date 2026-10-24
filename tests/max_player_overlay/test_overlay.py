"""Presentation contracts only; these mocks cannot validate Android rendering."""
import gc
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch
import weakref
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'source/slyguy.max.cleanui/resources/lib/ui/player_overlay.py'
XML = ROOT / 'source/slyguy.max.cleanui/resources/skins/Default/1080i/ui_player.xml'


def until(predicate):
    end = time.monotonic() + 2
    event = threading.Event()
    while not predicate():
        if time.monotonic() > end:
            raise AssertionError('Presentation worker did not finish its bounded transition')
        event.wait(0.005)


class Controller:
    addon_path = '/addons/slyguy.max.cleanui'
    _processing_playback = True
    exit_requested = False


class Environment:
    def __init__(self):
        self.video = True
        self.file = 'https://cdn.invalid/resolved-manifest.mpd'
        self.now = 0.0
        self.properties = {}
        self.abort = threading.Event()
        self.shown = []
        self.rpc_calls = []
        self.media_calls = []
        self.conditions = set()
        self.position = 25
        self.total = 100
        self.streams = {
            'audiostreams': [{'index': 3, 'language': 'es', 'codec': 'ac3', 'channels': 6},
                             {'index': 9, 'name': 'Original', 'language': 'en'}],
            'currentaudiostream': {'index': 9},
            'subtitles': [{'index': 5, 'language': 'es'}, {'index': 8, 'language': 'en'}],
            'currentsubtitle': {'index': 5}, 'subtitleenabled': True}
        env = self

        class Player:
            def isPlayingVideo(self): return env.video
            def getPlayingFile(self): return env.file
            def getTime(self): return env.position
            def getTotalTime(self): return env.total
            def pause(self): env.media_calls.append(('pause',))
            def stop(self): env.media_calls.append(('stop',))
            def seekTime(self, value): env.media_calls.append(('seek', value))

        class Monitor:
            def abortRequested(self): return env.abort.is_set()
            def waitForAbort(self, seconds): return env.abort.wait(min(seconds, 0.01))

        class Host:
            def __init__(self, number): pass
            def getProperty(self, key): return env.properties.get(key, '')

        class Control:
            def __init__(self): self.items = []; self.position = 0
            def reset(self): self.items = []
            def addItems(self, items): self.items += items
            def selectItem(self, value): self.position = value
            def getSelectedPosition(self): return self.position

        class Window:
            def __init__(self, *args, **kwargs):
                self.properties = {}; self.controls = {}; self.closed = False; self.focus = None
            def setProperty(self, key, value): self.properties[key] = value
            def setFocusId(self, value): self.focus = value
            def getControl(self, cid): return self.controls.setdefault(cid, Control())
            def show(self): env.shown.append(self); self.onInit()
            def close(self): self.closed = True
            def doModal(self): self.onInit()  # Cancellation for non-interactive unit tests.

        def rpc(raw):
            request = json.loads(raw); env.rpc_calls.append(request)
            method = request['method']
            if method == 'Player.GetActivePlayers': result = [{'playerid': 1, 'type': 'video'}]
            elif method == 'Player.GetProperties': result = env.streams
            elif method in ('Player.SetAudioStream', 'Player.SetSubtitle'): result = 'OK'
            else: raise AssertionError('Unexpected player request: ' + method)
            return json.dumps({'result': result})

        modules = {'xbmc': types.SimpleNamespace(Player=Player, Monitor=Monitor,
                   executeJSONRPC=rpc, getCondVisibility=lambda name: name in env.conditions,
                   log=lambda *args: None, LOGWARNING=2),
                   'xbmcgui': types.SimpleNamespace(Window=Host, WindowXMLDialog=Window,
                   ListItem=lambda **kwargs: kwargs)}
        spec = importlib.util.spec_from_file_location('max_overlay_test', SOURCE)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules): spec.loader.exec_module(self.module)


class OverlayContracts(unittest.TestCase):
    def setUp(self):
        self.env = Environment(); self.m = self.env.module
        self.controller = Controller()
        self.observer = self.m.MaxPlayerOverlay(self.controller, clock=lambda: self.env.now)
        self.addCleanup(self.observer.close)

    def start(self):
        self.assertTrue(self.observer.arm('plugin://slyguy.max.cleanui/?_=play&id=existing'))
        self.observer.onPlayBackStarted(); self.observer.onAVStarted()
        until(lambda: bool(self.env.shown))
        return self.env.shown[-1]

    def test_import_and_unarmed_observer_have_no_side_effects(self):
        self.observer.onAVStarted()
        self.assertIsNone(self.observer._worker)
        self.assertEqual(self.env.media_calls, []); self.assertEqual(self.env.rpc_calls, [])

    def test_route_validation_uses_exact_netloc(self):
        for path in ['plugin://slyguy.max.cleanui.evil/play', 'plugin://slyguy.disney.plus.cleanui/play',
                     'https://slyguy.max.cleanui/play', 'plugin://user@slyguy.max.cleanui/play',
                     'plugin://slyguy.max.cleanui:1/play', 'plugin://slyguy.max.cleanui',
                     'plugin://slyguy.max.cleanui/\nplay', None]:
            with self.subTest(path=path): self.assertFalse(self.observer.arm(path))
        self.assertTrue(self.observer.arm('plugin://slyguy.max.cleanui/play?id=7'))
        self.assertEqual(self.env.media_calls, [])

    def test_arming_does_not_create_worker_or_retain_route(self):
        path = 'plugin://slyguy.max.cleanui/play?id=private-title'
        self.observer.arm(path)
        self.assertIsNone(self.observer._worker)
        self.assertNotIn(path, vars(self.observer).values())

    def test_expired_or_cancelled_arm_does_not_activate(self):
        self.observer.arm('plugin://slyguy.max.cleanui/play'); self.env.now = 61
        self.observer.onAVStarted(); self.assertIsNone(self.observer._worker)
        self.env.now = 0; self.observer.arm('plugin://slyguy.max.cleanui/play')
        self.observer.cancel_arm(); self.observer.onAVStarted(); self.assertIsNone(self.observer._worker)

    def test_intro_never_opens_overlay_and_consumes_arm(self):
        self.observer.arm('plugin://slyguy.max.cleanui/play')
        self.env.file = '/addons/slyguy.max.cleanui/resources/media/intro.mp4'
        self.observer.onAVStarted(); self.env.file = 'http://minidlna.invalid/movie.mp4'
        self.observer.onAVStarted(); self.assertIsNone(self.observer._worker)

    def test_processing_and_max_owner_are_required(self):
        for owner in [json.dumps({'addon': 'slyguy.disney.plus.cleanui'}), 'bad JSON', '[]']:
            self.observer.arm('plugin://slyguy.max.cleanui/play')
            self.env.properties['CleanUI.External.Owner'] = owner
            self.observer.onAVStarted(); self.assertIsNone(self.observer._worker)
        self.env.properties.clear(); self.controller._processing_playback = False
        self.observer.onAVStarted(); self.assertIsNone(self.observer._worker)

    def test_non_max_controller_cannot_display(self):
        self.controller.addon_path = '/addons/slyguy.disney.plus.cleanui'
        self.observer.arm('plugin://slyguy.max.cleanui/play'); self.observer.onAVStarted()
        self.assertIsNone(self.observer._worker)

    def test_starting_audio_or_buffering_does_not_show(self):
        self.observer.arm('plugin://slyguy.max.cleanui/play'); self.env.video = False
        self.observer.onPlayBackStarted(); self.observer.onAVStarted()
        self.assertIsNone(self.observer._worker)

    def test_duplicate_av_events_keep_one_dialog_and_worker(self):
        window = self.start(); worker = self.observer._worker
        for _ in range(5): self.observer.onAVStarted()
        self.assertIs(self.observer._worker, worker)
        self.assertEqual(self.env.shown, [window])

    def test_terminal_events_close_without_stopping_media(self):
        for callback in ('onPlayBackEnded', 'onPlayBackStopped', 'onPlayBackError'):
            with self.subTest(callback=callback):
                self.env.shown.clear(); window = self.start()
                getattr(self.observer, callback)(); until(lambda: self.observer._worker is None)
                self.assertTrue(window.closed)
        self.assertEqual(self.env.media_calls, [])

    def test_buffering_hides_controls_without_ending_session(self):
        window = self.start(); self.env.video = False
        until(lambda: not window.controls_visible)
        self.assertIsNotNone(self.observer._worker); self.assertFalse(window.closed)
        self.env.video = True; window.reveal()
        self.assertTrue(window.controls_visible); self.assertEqual(self.env.media_calls, [])

    def test_owner_change_closes_and_stale_actions_are_ignored(self):
        window = self.start(); self.env.properties['CleanUI.External.Owner'] = json.dumps({'addon': 'slyguy.disney.plus.cleanui'})
        until(lambda: self.observer._worker is None)
        window.onClick(self.m.PLAY); self.assertEqual(self.env.media_calls, [])

    def test_worker_does_not_keep_controller_alive(self):
        self.start(); reference = weakref.ref(self.controller)
        del self.controller; gc.collect(); self.assertIsNone(reference())
        until(lambda: self.observer._worker is None)

    def test_close_and_abort_leave_no_inactive_worker(self):
        window = self.start(); self.env.abort.set()
        until(lambda: self.observer._worker is None)
        self.assertTrue(window.closed); self.assertIsNone(self.observer._active)
        self.assertFalse(self.observer.arm('plugin://slyguy.max.cleanui/play'))

    def test_busy_prompt_defers_hud(self):
        self.env.conditions.add('Window.IsVisible(yesnodialog)')
        self.observer.arm('plugin://slyguy.max.cleanui/play'); self.observer.onAVStarted()
        until(lambda: self.observer._worker is not None)
        self.assertEqual(self.env.shown, [])
        self.env.conditions.clear(); until(lambda: bool(self.env.shown))

    def test_pause_seek_clamps_and_stop_are_public_player_calls(self):
        window = self.start(); generation = window.generation
        self.assertTrue(self.observer.pause_or_resume(generation))
        self.env.position = 3; self.observer.seek_relative(generation, -10)
        self.env.position = 96; self.observer.seek_relative(generation, 10)
        self.assertFalse(self.observer.seek_relative(generation, 100))
        self.observer.stop_requested(generation); self.observer.stop_requested(generation)
        self.assertEqual(self.env.media_calls, [('pause',), ('seek', 0.0), ('seek', 100), ('stop',)])
        self.assertEqual(self.env.rpc_calls, [])

    def test_back_hides_then_stops_and_hidden_dpad_only_reveals(self):
        window = self.start(); action=lambda n: types.SimpleNamespace(getId=lambda:n)
        window.onAction(action(92)); self.assertFalse(window.controls_visible)
        window.onAction(action(1)); self.assertTrue(window.controls_visible)
        self.assertEqual(self.env.media_calls, [])
        window.onAction(action(92)); window.onAction(action(92))
        self.assertEqual(self.env.media_calls, [('stop',)])

    def test_autohide_preserves_dialog_for_next_remote_action(self):
        window = self.start(); self.env.now = 5
        until(lambda:not window.controls_visible)
        self.assertFalse(window.closed); self.assertEqual(window.focus, self.m.KEEPER)
        self.assertEqual(self.env.media_calls, [])

    def test_actual_stream_indices_and_selection_are_preserved(self):
        window=self.start(); choices, selected=self.observer.stream_options(window.generation,'audio')
        self.assertEqual([v for _,v in choices],[3,9]); self.assertEqual(selected,1)
        self.assertTrue(self.observer.select_stream(window.generation,'audio',9))
        setter=self.env.rpc_calls[-1]
        self.assertEqual(setter['method'],'Player.SetAudioStream')
        self.assertEqual(setter['params'],{'playerid':1,'stream':9})

    def test_unknown_tracks_cannot_be_selected(self):
        window=self.start(); self.assertFalse(self.observer.select_stream(window.generation,'audio',0))
        self.assertFalse(self.observer.select_stream(window.generation,'audio',True))
        self.assertFalse(any(c['method'].startswith('Player.Set')for c in self.env.rpc_calls))

    def test_subtitle_off_and_real_track_use_expected_kodi_calls(self):
        window=self.start(); gen=window.generation
        self.observer.select_stream(gen,'subtitle','off')
        self.assertEqual(self.env.rpc_calls[-1]['params'],{'playerid':1,'subtitle':'off'})
        self.observer.select_stream(gen,'subtitle',8)
        self.assertEqual(self.env.rpc_calls[-1]['params'],{'playerid':1,'subtitle':8,'enable':True})

    def test_new_generation_rejects_old_dialog_and_stream_selection(self):
        window=self.start(); old=window.generation
        self.observer.arm('plugin://slyguy.max.cleanui/play?id=next')
        self.assertFalse(self.observer.select_stream(old,'audio',9))
        window.onClick(self.m.PLAY); self.assertEqual(self.env.media_calls, [])
        self.assertEqual(self.env.rpc_calls, [])

    def test_replacement_media_without_arm_does_not_inherit_overlay(self):
        window=self.start(); self.observer.onPlayBackStarted()
        self.env.file='http://minidlna.invalid/other.mp4'; self.observer.onAVStarted()
        until(lambda:self.observer._worker is None)
        self.assertTrue(window.closed); self.assertEqual(len(self.env.shown),1)

    def test_track_dialog_cancellation_and_terminal_cleanup_do_not_set_tracks(self):
        window=self.start(); window.onClick(self.m.AUDIO)
        self.assertFalse(any(c['method'].startswith('Player.Set')for c in self.env.rpc_calls))
        child=types.SimpleNamespace(closed=False)
        child.close=lambda:setattr(child,'closed',True)
        window._child=child; self.observer.onPlayBackEnded()
        until(lambda:self.observer._worker is None); self.assertTrue(child.closed)

    def test_prompt_during_window_initialization_closes_and_retries_safely(self):
        window=self.start(); self.env.conditions.add('Window.IsVisible(yesnodialog)')
        window.onInit(); self.assertTrue(window.closed); self.assertTrue(window._startup_rejected)
        until(lambda:self.observer._dialog is None)
        self.env.conditions.clear(); until(lambda:len(self.env.shown)==2)
        self.assertEqual(self.env.media_calls, [])

    def test_disposed_observer_is_collectable_after_thread_finishes(self):
        env = Environment(); controller = Controller()
        observer = env.module.MaxPlayerOverlay(controller, clock=lambda: env.now)
        observer.arm('plugin://slyguy.max.cleanui/play'); observer.onAVStarted()
        until(lambda: bool(env.shown)); reference = weakref.ref(observer)
        observer.close(); del observer; gc.collect()
        self.assertIsNone(reference())

    def test_hidden_progress_and_title_use_kodi_info_not_catalog_requests(self):
        root=ET.parse(XML).getroot(); text=XML.read_text()
        self.assertIn('Player.Progress',text); self.assertIn('Player.Time',text)
        self.assertIn('Player.Duration',text); self.assertIn('VideoPlayer.Title',text)
        ids={int(c.get('id'))for c in root.iter('control')if c.get('id')}
        self.assertTrue({8199,8101,8102,8103,8104,8105,8106,8109}<=ids)
        self.assertNotIn('PlayMedia',SOURCE.read_text())
        self.assertNotIn('executebuiltin(',SOURCE.read_text())


if __name__=='__main__': unittest.main()
