"""Opt-in Max playback presentation prototype; never resolves or opens media.

Not enabled by importing this module. The UI must explicitly arm an existing
Max plugin route before its unchanged controller.play(path) call. The original
SlyGuy player and observe_playback remain responsible for the media lifetime.
"""
import json
import os
import threading
import time
import weakref
from urllib.parse import urlsplit

import xbmc
import xbmcgui

ADDON_ID = 'slyguy.max.cleanui'
AUTO_HIDE_SECONDS = 4.0  # Prototype default, not verified against official playback.
ARM_TIMEOUT_SECONDS = 60.0
BACK = (9, 10, 92)
REVEAL = (1, 2, 3, 4, 7, 11, 24, 100)
PLAY_PAUSE = (12, 79, 229)
STOP = 13
STEP_FORWARD, STEP_BACK = 20, 21


def _prompt_visible():
    return any(xbmc.getCondVisibility('Window.IsVisible({})'.format(name))
               for name in ('busydialog', 'busydialognocancel', 'selectdialog',
                            'yesnodialog', 'okdialog', 'progressdialog'))
KEEPER, PLAY, BACK_TEN, FORWARD_TEN = 8199, 8101, 8102, 8103
AUDIO, SUBTITLES, STOP_BUTTON, STREAM_LIST = 8104, 8105, 8106, 8109


def _rpc(method, params):
    response = json.loads(xbmc.executeJSONRPC(json.dumps({
        'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params})))
    if not isinstance(response, dict) or 'error' in response or 'result' not in response:
        raise RuntimeError('Kodi player request unavailable')
    return response['result']


def _max_route(path):
    if not isinstance(path, str) or any(ord(c) < 32 or ord(c) == 127 for c in path):
        return False
    try:
        parsed = urlsplit(path)
        return (parsed.scheme == 'plugin' and parsed.netloc == ADDON_ID and parsed.path.startswith('/')
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def _scope(controller):
    if controller is None or getattr(controller, 'exit_requested', False):
        return False
    path = getattr(controller, 'addon_path', '')
    if os.path.basename(os.path.normpath(path)) != ADDON_ID:
        return False
    if not getattr(controller, '_processing_playback', False):
        return False
    raw = xbmcgui.Window(10000).getProperty('CleanUI.External.Owner')
    if not raw:
        return True  # A locally opened Max session can also explicitly arm.
    try:
        return json.loads(raw).get('addon') == ADDON_ID
    except (ValueError, TypeError, AttributeError):
        return False


def _intro(path):
    return path.replace('\\', '/').split('?', 1)[0].lower().endswith('/resources/media/intro.mp4')


class MaxPlayerOverlay(xbmc.Player):
    """One observer and at most one worker, only while an armed video is live."""
    def __init__(self, controller, clock=time.monotonic):
        super(MaxPlayerOverlay, self).__init__()
        self._controller = weakref.ref(controller)
        self._clock = clock
        self._lock = threading.RLock()
        self._generation = 0
        self._armed_until = None
        self._active = None
        self._closed = False
        self._worker = None
        self._dialog = None
        self._stop_generation = None

    def arm(self, existing_path):
        """Record UI intent only. Does not execute, resolve, or retain the URL."""
        if not _max_route(existing_path):
            return False
        with self._lock:
            if self._closed:
                return False
            self._generation += 1
            self._armed_until = self._clock() + ARM_TIMEOUT_SECONDS
            self._active = None
        return True

    def cancel_arm(self):
        with self._lock:
            self._armed_until = None

    def onPlayBackStarted(self):
        # An unrelated new player must not inherit a previous overlay.
        with self._lock:
            self._active = None

    def onAVStarted(self):
        try:
            if not self.isPlayingVideo() or not _scope(self._controller()):
                return
            filename = self.getPlayingFile()
            if not filename or _intro(filename):
                self.cancel_arm()
                return
        except RuntimeError:
            return
        with self._lock:
            if self._closed:
                return
            if self._active and self._active[1] == filename:
                return  # Audio/video reconfiguration is not a new session.
            if self._armed_until is None or self._clock() > self._armed_until:
                self._active = None
                return
            self._armed_until = None
            self._generation += 1
            self._active = (self._generation, filename)
        self._ensure_worker()

    def _terminal(self, clear_arm=False):
        with self._lock:
            self._active = None
            if clear_arm:
                self._armed_until = None

    def onPlayBackEnded(self):
        self._terminal()

    def onPlayBackStopped(self):
        self._terminal()

    def onPlayBackError(self):
        self._terminal(clear_arm=True)

    def onPlayBackPaused(self):
        self._reveal_if_active()

    def onPlayBackResumed(self):
        self._reveal_if_active()

    def _reveal_if_active(self):
        with self._lock:
            window = self._dialog
        if window and self.is_active(window.generation):
            window.reveal()

    def is_active(self, generation, require_video=False):
        with self._lock:
            state = self._active
            allowed = not self._closed and state and state[0] == generation
        if not allowed or not _scope(self._controller()):
            return False
        try:
            if not self.isPlayingVideo():
                return not require_video  # Buffering is not a terminal event.
            current = self.getPlayingFile()
            return current == state[1] if current else not require_video
        except RuntimeError:
            return not require_video

    def _ensure_worker(self):
        with self._lock:
            if self._closed or self._active is None:
                return
            if self._worker is not None:
                return
            worker = threading.Thread(target=self._run, name='MaxOverlayPresentation', daemon=True)
            self._worker = worker
        worker.start()

    def _run(self):
        monitor = xbmc.Monitor()
        window = None
        try:
            while not monitor.abortRequested():
                with self._lock:
                    state = None if self._closed else self._active
                if state is None:
                    break
                generation = state[0]
                if not self.is_active(generation):
                    with self._lock:
                        if self._active == state:
                            self._active = None
                    continue
                if window is not None and (window.generation != generation or window._startup_rejected):
                    window.finish()
                    window = None
                    with self._lock:
                        self._dialog = None
                if self.isPlayingVideo():
                    # Never put the presentation over a native startup prompt.
                    busy = _prompt_visible()
                    if window is None and not busy:
                        controller = self._controller()
                        if controller is None:
                            break
                        window = _PlayerWindow('ui_player.xml', controller.addon_path,
                                               'Default', '1080i', owner=self,
                                               generation=generation)
                        del controller
                        with self._lock:
                            self._dialog = window
                        if self.is_active(generation, require_video=True):
                            window.show()
                    if window is not None:
                        if busy:
                            window.conceal(keep_focus=False)
                        else:
                            window.tick(self._clock())
                elif window is not None:
                    window.conceal()
                if monitor.waitForAbort(0.1):
                    break
        except Exception:
            # A failed presentation must never stop, replay or change the media.
            xbmc.log('[CLEANUI] Max playback presentation unavailable', xbmc.LOGWARNING)
            with self._lock:
                self._active = None
        finally:
            if window is not None:
                window.finish()
            with self._lock:
                self._dialog = None
                self._worker = None
                if monitor.abortRequested():
                    self._closed = True
                    self._active = None
                    self._armed_until = None
                restart = self._active is not None and not self._closed and not monitor.abortRequested()
            if restart:
                self._ensure_worker()

    def close(self, wait=True):
        """Cooperative disposal; never stops the Kodi player."""
        with self._lock:
            self._closed = True
            self._active = None
            self._armed_until = None
            worker = self._worker
        if wait and worker is not None and worker is not threading.current_thread():
            worker.join(0.75)

    def pause_or_resume(self, generation):
        if self.is_active(generation, require_video=True):
            try:
                self.pause()
                return True
            except RuntimeError:
                return False
        return False

    def seek_relative(self, generation, seconds):
        if seconds not in (-10, 10) or not self.is_active(generation, require_video=True):
            return False
        try:
            target = max(0.0, self.getTime() + seconds)
            total = self.getTotalTime()
            if total > 0:
                target = min(target, total)
            self.seekTime(target)
            return True
        except RuntimeError:
            return False

    def stop_requested(self, generation):
        if self.is_active(generation, require_video=True):
            with self._lock:
                if self._stop_generation == generation:
                    return False
                self._stop_generation = generation
            try:
                self.stop()
                return True
            except RuntimeError:
                return False
        return False

    def _player_id(self, generation):
        if not self.is_active(generation, require_video=True):
            return None
        players = _rpc('Player.GetActivePlayers', {})
        return next((p['playerid'] for p in players if p.get('type') == 'video'), None)

    def stream_options(self, generation, kind):
        """Query actual exposed tracks only when the user opens the selector."""
        if kind not in ('audio', 'subtitle'):
            return [], -1
        player_id = self._player_id(generation)
        if player_id is None:
            return [], -1
        properties = (['audiostreams', 'currentaudiostream'] if kind == 'audio'
                      else ['subtitles', 'currentsubtitle', 'subtitleenabled'])
        data = _rpc('Player.GetProperties', {'playerid': player_id, 'properties': properties})
        key = 'audiostreams' if kind == 'audio' else 'subtitles'
        current = (data.get('currentaudiostream' if kind == 'audio' else 'currentsubtitle') or {}).get('index')
        options = [] if kind == 'audio' else [('Desactivados', 'off')]
        selected = -1 if kind == 'audio' or data.get('subtitleenabled') else 0
        for track in data.get(key, []):
            if not isinstance(track, dict):
                continue
            index = track.get('index')
            if type(index) is not int or index < 0:
                continue
            label = str(track.get('name') or track.get('language') or 'Pista {}'.format(index + 1))
            details = []
            if track.get('language') and track['language'] != label:
                details.append(str(track['language']))
            if track.get('codec'):
                details.append(str(track['codec']).upper())
            if type(track.get('channels')) is int and track['channels'] > 0:
                details.append('{} canales'.format(track['channels']))
            if details:
                label += ' · ' + ' · '.join(details)
            if index == current and (kind == 'audio' or data.get('subtitleenabled')):
                selected = len(options)
            options.append((label, index))
        return options, selected

    def select_stream(self, generation, kind, index):
        if kind not in ('audio', 'subtitle'):
            return False
        if not (type(index) is int and index >= 0) and not (kind == 'subtitle' and index == 'off'):
            return False
        options, _ = self.stream_options(generation, kind)
        if index not in [value for _, value in options]:
            return False
        player_id = self._player_id(generation)
        if player_id is None:
            return False
        if kind == 'audio':
            result = _rpc('Player.SetAudioStream', {'playerid': player_id, 'stream': index})
        else:
            params = {'playerid': player_id, 'subtitle': index}
            if index != 'off':
                params['enable'] = True
            result = _rpc('Player.SetSubtitle', params)
        return result is not False


class _PlayerWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.owner = weakref.ref(kwargs.pop('owner'))
        self.generation = kwargs.pop('generation')
        self.controls_visible = False
        self._last_action = 0.0
        self._child = None
        self._startup_rejected = False
        super(_PlayerWindow, self).__init__(*args, **kwargs)

    def onInit(self):
        owner = self.owner()
        self.setProperty('max.player.mode', 'player')
        if _prompt_visible():
            self._startup_rejected = True
            self.close()
            return
        if not owner or not owner.is_active(self.generation, require_video=True):
            self.close()
            return
        self.reveal()

    def reveal(self):
        owner = self.owner()
        if self._child is not None or _prompt_visible():
            self.conceal(keep_focus=False)
            return
        if not owner or not owner.is_active(self.generation, require_video=True):
            return
        self._last_action = owner._clock()
        self.controls_visible = True
        self.setProperty('max.player.controls', '1')
        self.tick(self._last_action)
        self.setFocusId(PLAY)

    def conceal(self, keep_focus=True):
        self.controls_visible = False
        self.setProperty('max.player.controls', '0')
        if keep_focus:
            self.setFocusId(KEEPER)

    def tick(self, now):
        if self.controls_visible:
            self.setProperty('max.player.play.label', 'Reproducir' if xbmc.getCondVisibility('Player.Paused') else 'Pausa')
        if self._child is None and self.controls_visible and now - self._last_action >= AUTO_HIDE_SECONDS:
            self.conceal()

    def onFocus(self, control_id):
        owner = self.owner()
        if owner and control_id != KEEPER:
            self._last_action = owner._clock()

    def onAction(self, action):
        owner = self.owner()
        if not owner or not owner.is_active(self.generation, require_video=True):
            return
        action_id = action.getId()
        self._last_action = owner._clock()
        if action_id in BACK:
            if self.controls_visible:
                self.conceal()
            else:
                owner.stop_requested(self.generation)
        elif action_id in PLAY_PAUSE:
            owner.pause_or_resume(self.generation)
            self.reveal()
        elif action_id == STOP:
            owner.stop_requested(self.generation)
        elif action_id in (STEP_FORWARD, STEP_BACK):
            owner.seek_relative(self.generation, 10 if action_id == STEP_FORWARD else -10)
            self.reveal()
        elif action_id in REVEAL and not self.controls_visible:
            self.reveal()
        # Unrelated actions never become recursive Action(...) builtins.

    def onClick(self, control_id):
        owner = self.owner()
        if not owner or not owner.is_active(self.generation, require_video=True):
            return
        self._last_action = owner._clock()
        if control_id == PLAY:
            owner.pause_or_resume(self.generation)
        elif control_id in (BACK_TEN, FORWARD_TEN):
            owner.seek_relative(self.generation, -10 if control_id == BACK_TEN else 10)
        elif control_id == STOP_BUTTON:
            owner.stop_requested(self.generation)
        elif control_id in (AUDIO, SUBTITLES):
            self._streams('audio' if control_id == AUDIO else 'subtitle')

    def _streams(self, kind):
        owner = self.owner()
        if not owner:
            return
        try:
            self.setProperty('max.player.notice', '')
            options, selected = owner.stream_options(self.generation, kind)
            if not options:
                self.setProperty('max.player.notice', 'No hay pistas disponibles.')
                return
            controller = owner._controller()
            if controller is None or not owner.is_active(self.generation, require_video=True):
                return
            child = _StreamWindow('ui_player.xml', controller.addon_path, 'Default', '1080i',
                                  owner=owner, generation=self.generation, options=options,
                                  selected=selected, title='Audio' if kind == 'audio' else 'Subtítulos')
            del controller
            self._child = child
            try:
                child.doModal()
                if child.selected is not None:
                    owner.select_stream(self.generation, kind, child.selected)
            finally:
                child.close()
                self._child = None
                self.reveal()
        except (RuntimeError, ValueError, TypeError, KeyError):
            self.setProperty('max.player.notice', 'No se pudo cambiar la pista.')

    def finish(self):
        if self._child is not None:
            self._child.close()
            self._child = None
        self.close()


class _StreamWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.owner = weakref.ref(kwargs.pop('owner'))
        self.generation = kwargs.pop('generation')
        self.options = kwargs.pop('options')
        self.initial = kwargs.pop('selected')
        self.title = kwargs.pop('title')
        self.selected = None
        super(_StreamWindow, self).__init__(*args, **kwargs)

    def onInit(self):
        owner = self.owner()
        self.setProperty('max.player.mode', 'streams')
        self.setProperty('max.player.stream.title', self.title)
        if not owner or not owner.is_active(self.generation, require_video=True):
            self.close()
            return
        control = self.getControl(STREAM_LIST)
        control.reset()
        control.addItems([xbmcgui.ListItem(label=('✓ ' if i == self.initial else '') + text,
                                          offscreen=True) for i, (text, _) in enumerate(self.options)])
        if 0 <= self.initial < len(self.options):
            control.selectItem(self.initial)
        self.setFocusId(STREAM_LIST)

    def onClick(self, control_id):
        owner = self.owner()
        if control_id != STREAM_LIST or not owner or not owner.is_active(self.generation, require_video=True):
            return
        index = self.getControl(STREAM_LIST).getSelectedPosition()
        if 0 <= index < len(self.options):
            self.selected = self.options[index][1]
            self.close()

    def onAction(self, action):
        if action.getId() in BACK:
            self.close()
