"""One session-scoped metadata worker; all control updates run via GUI callbacks."""
import threading
import weakref
import xbmc
import xbmcgui

class NavigationLoader:
    def __init__(self):
        self._condition=threading.Condition()
        self._sequence=0
        self._job=None
        self._ready=None
        self._closed=False
        self._running=False
        self._thread=threading.Thread(target=self._run,name='CleanUI-navigation',daemon=True)
        self._thread.start()

    @property
    def active(self):
        with self._condition:
            return self._running or self._job is not None or self._ready is not None

    def submit(self,window,build,apply):
        with self._condition:
            if self._closed:
                return False
            self._sequence+=1
            token=self._sequence
            self._ready=None
            self._job=(token,weakref.ref(window),xbmcgui.getCurrentWindowDialogId(),build,apply)
            window._loading_request=token
            window._last_load=(build,apply)
            self._condition.notify()
        window.setProperty('cleanui.loading','true')
        window.setProperty('cleanui.load_error','false')
        return True

    def cancel(self,window):
        with self._condition:
            if getattr(window,'_loading_request',None)==self._sequence:
                self._sequence+=1
                self._job=self._ready=None
            window._loading_request=None
            window._last_load=None
        window.setProperty('cleanui.loading','false')
        window.setProperty('cleanui.load_error','false')

    def finish(self,window):
        with self._condition:
            ready=self._ready
            if not ready or ready[0]!=getattr(window,'_loading_request',None):
                return False
            self._ready=None
        token,apply,result,error=ready
        window._loading_request=None
        window.setProperty('cleanui.loading','false')
        if error:
            window.setProperty('cleanui.load_error','true')
            window.setFocusId(4980)
            xbmc.log('[CLEANUI] Metadata load failed: '+type(error).__name__,xbmc.LOGWARNING)
            return False
        window.setProperty('cleanui.load_error','false')
        last_load=getattr(window,'_last_load',None)
        try:
            if apply(result) is False:
                raise RuntimeError('Metadata presentation rejected')
        except Exception as exc:
            window.setProperty('cleanui.load_error','true')
            window.setFocusId(4980)
            xbmc.log('[CLEANUI] Metadata presentation failed: '+type(exc).__name__,xbmc.LOGWARNING)
            return False
        if getattr(window,'_last_load',None) is last_load:
            window._last_load=None
        return True

    def close(self):
        with self._condition:
            self._closed=True
            self._sequence+=1
            self._job=self._ready=None
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                while not self._closed and self._job is None:
                    self._condition.wait()
                if self._closed:
                    return
                token,reference,window_id,build,apply=self._job
                self._job=None
                self._running=True
            result,error=None,None
            try:
                result=build()
            except Exception as exc:
                error=exc
            with self._condition:
                self._running=False
                current=not self._closed and token==self._sequence and reference() is not None
                if current:
                    self._ready=(token,apply,result,error)
            if current:
                # SendClick queues a native GUI message. The worker never
                # accesses controls, changes focus, or opens/closes windows.
                xbmc.executebuiltin('SendClick({},4999)'.format(window_id))
            del build,apply,result,error,reference
