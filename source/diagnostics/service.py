"""One bounded recorder per Kodi profile. No network or GUI mutations."""
from collections import deque
import json
import os
import time
import uuid
import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs
import core
from protocol import ADDONS, SCHEMA, clean_record, event_input


def atomic_json(path, data):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        json.dump(data, output, ensure_ascii=True, allow_nan=False)
    os.replace(str(temporary), str(path))


class LogTail:
    def __init__(self):
        self.offset = 0
        self.identity = None
        self.pending = b''

    def read(self):
        path = xbmcvfs.translatePath('special://logpath/kodi.log')
        size = os.stat(path)
        identity = (size.st_dev, size.st_ino)
        if self.identity != identity or size.st_size < self.offset:
            self.offset, self.pending = 0, b''
            self.identity = identity
        gap = max(0, size.st_size - self.offset - 64 * 1024)
        if gap:
            self.offset += gap
            self.pending = b''
        with open(path, 'rb') as source:
            source.seek(self.offset)
            data = source.read(64 * 1024)
        self.offset += len(data)
        parts = (self.pending + data).split(b'\n')
        self.pending = parts.pop()[-2000:]
        if gap and parts:
            parts.pop(0)
        return [value.strip() for value in
                (core.sanitize_line(line.decode('utf-8', errors='replace')) for line in parts) if value], gap


def run():
    addon = xbmcaddon.Addon(core.ADDON)
    home = xbmcgui.Window(10000)
    if core.recording():
        return
    token = uuid.uuid4().hex
    root = core.folder()
    samples, logs = core.Journal(root), core.Journal(root, name='kodi')
    queue = deque(maxlen=256)
    dropped = [0]
    boot, seq = uuid.uuid4().hex, 0
    state_path, session_path = root / 'transfer.json', root / 'session.json'
    state = {'schema': SCHEMA, 'boot': boot, 'capture_enabled': False, 'status': 'starting',
             'started': time.time(), 'heartbeat': time.time(), 'files': []}

    def enqueue(event, **values):
        if len(queue) == queue.maxlen:
            dropped[0] += 1
        queue.append(dict(event=event, **values))

    class Monitor(xbmc.Monitor):
        def onNotification(self, sender, method, data):
            if sender != 'cleanui.diagnostics' or method != 'Other.cleanui.diagnostics.event':
                return
            try:
                if len(data) > 2048:
                    return
                event = event_input(json.loads(data))
                if event:
                    enqueue(**event)
            except (ValueError, TypeError):
                pass

        def onSettingsChanged(self):
            enqueue('configuration')

    monitor = Monitor()

    class Player(xbmc.Player):
        def onPlayBackStarted(self): enqueue('started')
        def onAVStarted(self): enqueue('av_started')
        def onPlayBackPaused(self): enqueue('paused')
        def onPlayBackResumed(self): enqueue('resumed')
        def onPlayBackStopped(self): enqueue('stopped')
        def onPlayBackEnded(self): enqueue('ended')
        def onPlayBackError(self): enqueue('error')

    player, tail = Player(), LogTail()
    last_cpu, next_sample, enabled = None, 0.0, False

    def write(event, target=samples, **values):
        nonlocal seq
        seq += 1
        record = clean_record(dict(schema=SCHEMA, boot=boot, seq=seq,
                                   time=time.time(), event=event, **values))
        if record:
            target.write(record)

    def save_state():
        state['heartbeat'] = time.time()
        state['files'] = samples.metadata() + logs.metadata()
        atomic_json(state_path, state)

    try:
        previous = {}
        try:
            previous = json.loads(session_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        save_state()
        while not monitor.abortRequested():
            wanted = addon.getSetting('capture_enabled') != 'false'
            if wanted != enabled:
                enabled = wanted
                state.update(capture_enabled=enabled, status='recording' if enabled else 'disabled')
                if enabled:
                    home.setProperty(core.ACTIVE, token)
                    home.setProperty(core.BEAT, str(time.time()))
                    home.clearProperty(core.STOP)
                    write('start', snapshot=core.snapshot(True))
                    if previous.get('status') == 'recording':
                        write('recovered', data={'time': previous.get('started')})
                    previous = {}
                    for line in core.log_extract('kodi.old.log').splitlines():
                        write('log', target=logs, log=line)
                    next_sample = 0.0
                else:
                    write('finished')
                    core.release(token)
                atomic_json(session_path, state)
                save_state()
            if enabled:
                if home.getProperty(core.STOP) == token:
                    addon.setSetting('capture_enabled', 'false')
                    continue
                home.setProperty(core.BEAT, str(time.time()))
                if dropped[0]:
                    write('queue_gap', data={'count': dropped[0]})
                    dropped[0] = 0
                while queue:
                    event = queue.popleft()
                    if event['event'] == 'configuration':
                        write('configuration', snapshot=core.snapshot(True))
                    else:
                        write(**event)
                now = time.monotonic()
                if now >= next_sample:
                    sample = core.snapshot()
                    cpu = sample['process'].get('cpu_seconds')
                    if last_cpu and cpu is not None:
                        sample['process']['cpu_percent'] = max(0.0, (cpu - last_cpu[0]) / max(0.001, now - last_cpu[1]) * 100)
                    last_cpu = (cpu, now) if cpu is not None else None
                    write('sample', snapshot=sample)
                    try:
                        lines, gap = tail.read()
                        if gap:
                            write('log_gap', data={'count': gap})
                        for line in lines:
                            write('log', target=logs, log=line)
                    except OSError:
                        write('capture_error')
                    active = sample['playing'] or any(home.getProperty(key) for key in
                        ('MaxCleanUI.Running', 'DisneyPlusCleanUI.Running') + tuple(a + '.LaunchOwner' for a in ADDONS))
                    next_sample = now + (5 if active else 15)
                    save_state()
            else:
                queue.clear()
            if monitor.waitForAbort(1):
                break
        # No JSON-RPC, ZIP compression or worker joins at shutdown.
        state.update(status='finished', capture_enabled=enabled, finished=time.time())
        if enabled:
            while queue:
                event = queue.popleft()
                if event['event'] != 'configuration':
                    write(**event)
            write('finished')
    except Exception:
        state.update(status='capture_error', finished=time.time())
        try:
            if enabled:
                write('capture_error')
        except OSError:
            pass
    finally:
        try:
            atomic_json(session_path, state)
            save_state()
        except OSError:
            pass
        core.release(token)
        del player, monitor


if __name__ == '__main__':
    run()
