import ast
from pathlib import Path
import types
import unittest
import uuid
import weakref

SOURCE=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui/resources/lib/ui/navigation_relay.py'


class RelayTests(unittest.TestCase):
    def fixture(self, delayed=False):
        state=types.SimpleNamespace(now=0.0, current=13000, events=[], actions=[], closes=0)
        class Window:
            PLATFORM='max'
            _navigation_owner='live-owner'
            _window_id=13000
            _sidebar=[3011,3300]
            def __init__(self):self.properties={}
            def setProperty(self,k,v):self.properties[k]=v
            def getProperty(self,k):return self.properties.get(k,'')
            def clearProperty(self,k):self.properties.pop(k,None)
            def _activate_control(self,cid):state.actions.append(cid)
        parent,child=Window(),Window()
        controller=types.SimpleNamespace(_windows=[parent,child],exit_requested=False)
        parent.controller=child.controller=controller
        def close(window):
            state.closes+=1
            if not delayed:controller._windows.remove(window)
        controller.close_child_window=close
        env={'time':types.SimpleNamespace(monotonic=lambda:state.now),'uuid':uuid,'weakref':weakref,
             'xbmc':types.SimpleNamespace(executebuiltin=state.events.append),
             'xbmcgui':types.SimpleNamespace(getCurrentWindowDialogId=lambda:state.current)}
        tree=ast.parse(SOURCE.read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        exec(compile(tree,str(SOURCE),'exec'),env)
        return env,parent,child,state

    def test_close_then_consume_delivers_once_without_new_root(self):
        relay,parent,child,state=self.fixture()
        self.assertTrue(relay['request'](parent,child,3011))
        self.assertEqual(parent.controller._windows,[parent])
        self.assertEqual(state.closes,1)
        self.assertEqual(state.events,['SendClick(13000,4998)'])
        self.assertTrue(relay['consume'](parent))
        self.assertFalse(relay['consume'](parent))
        self.assertEqual(state.actions,[3011])
        self.assertEqual(parent.properties,{})

    def test_double_click_cannot_close_or_navigate_twice(self):
        relay,parent,child,state=self.fixture()
        relay['request'](parent,child,3300)
        self.assertFalse(relay['request'](parent,child,3300))
        relay['consume'](parent)
        self.assertFalse(relay['request'](parent,child,3300))
        self.assertEqual((state.closes,state.actions),(1,[3300]))

    def test_dead_parent_and_stale_token_are_discarded(self):
        for mode in ['dead','token','owner','expired','exit']:
            with self.subTest(mode=mode):
                relay,parent,child,state=self.fixture()
                relay['request'](parent,child,3011)
                if mode=='dead':parent.controller._windows.remove(parent)
                elif mode=='token':parent.properties[relay['TOKEN']]='unrelated'
                elif mode=='owner':parent._navigation_owner='replacement'
                elif mode=='expired':state.now=3.0
                else:parent.controller.exit_requested=True
                self.assertFalse(relay['consume'](parent))
                self.assertEqual(state.actions,[])
                self.assertIsNone(parent._pending_visual_navigation)

    def test_child_unwinds_before_later_gui_event(self):
        relay,parent,child,state=self.fixture(delayed=True)
        relay['request'](parent,child,3011)
        self.assertFalse(relay['consume'](parent))
        self.assertEqual(state.actions,[])
        parent.controller._windows.remove(child)
        self.assertTrue(relay['consume'](parent))
        self.assertEqual(state.actions,[3011])

    def test_unfinished_child_does_not_leave_an_unbounded_gui_queue(self):
        relay,parent,child,state=self.fixture(delayed=True)
        relay['request'](parent,child,3011)
        for unused in range(20):relay['consume'](parent)
        self.assertEqual(len(state.events),5)
        self.assertIsNone(parent._pending_visual_navigation)
        self.assertEqual(state.actions,[])

    def test_closed_child_without_pending_action_does_not_navigate(self):
        relay,parent,child,state=self.fixture()
        parent.controller._windows.remove(child)
        self.assertFalse(relay['consume'](parent))
        self.assertEqual(state.actions,[])

    def test_cannot_dispatch_playback_or_a_disney_root(self):
        relay,parent,child,state=self.fixture()
        self.assertFalse(relay['request'](parent,child,1000))
        parent.PLATFORM='disney'
        self.assertFalse(relay['request'](parent,child,3011))
        self.assertEqual(state.closes,0)


if __name__=='__main__':unittest.main()
