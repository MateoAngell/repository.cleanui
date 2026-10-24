"""Deliver a child menu choice to the still-live Max catalogue window.

The native GUI queue is the handoff signal. No timer, worker, stream change or
new root window is involved. Owner/request tokens reject stale callbacks.
"""
import time
import uuid
import weakref
import xbmc
import xbmcgui

TOKEN = 'cleanui.max.navigation.token'
RECEIVER = 4998


def cancel(parent):
    parent._pending_visual_navigation = None
    parent.clearProperty(TOKEN)


def request(parent, child, target):
    controller = parent.controller
    if (getattr(parent, 'PLATFORM', None) != 'max' or child.controller is not controller
            or parent not in controller._windows or getattr(controller, 'exit_requested', False)
            or target not in getattr(parent, '_sidebar', ())
            or not getattr(parent, '_window_id', 0)
            or getattr(parent, '_pending_visual_navigation', None)
            or getattr(child, '_nav_dispatched', False)):
        return False
    token = uuid.uuid4().hex
    parent._pending_visual_navigation = dict(owner=parent._navigation_owner,
        token=token, target=target, child=weakref.ref(child), created=time.monotonic(), attempts=0)
    parent.setProperty(TOKEN, token)
    child._nav_dispatched = True
    try:
        controller.close_child_window(child)
        xbmc.executebuiltin('SendClick({},{})'.format(parent._window_id, RECEIVER))
    except Exception:
        cancel(parent)
        child._nav_dispatched = False
        raise
    return True


def consume(parent):
    pending = getattr(parent, '_pending_visual_navigation', None)
    if not pending:
        return False
    controller = parent.controller
    if (parent not in controller._windows or getattr(controller, 'exit_requested', False)
            or pending['owner'] != parent._navigation_owner
            or pending['token'] != parent.getProperty(TOKEN)
            or time.monotonic() - pending['created'] > 2.0):
        cancel(parent)
        return False
    child = pending['child']()
    ready = child not in controller._windows and xbmcgui.getCurrentWindowDialogId() == parent._window_id
    if not ready:
        # Kodi may deliver the queued message before doModal has unwound its
        # Python stack. Requeue a bounded GUI event, never sleep or busy-wait.
        pending['attempts'] += 1
        if pending['attempts'] <= 4:
            xbmc.executebuiltin('SendClick({},{})'.format(parent._window_id, RECEIVER))
        else:
            cancel(parent)
        return False
    target = pending['target']
    cancel(parent)  # consume before dispatch: double clicks cannot dispatch twice
    parent._activate_control(target)
    return True
