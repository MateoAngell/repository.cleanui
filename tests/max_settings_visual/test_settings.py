import ast
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui'
SOURCE = ROOT / 'resources/lib/ui/settings_window.py'
XML = ROOT / 'resources/skins/Default/1080i/ui_settings.xml'


class Setting:
    def __init__(self, label='Real option: No', private=False, enabled=True):
        self.label, self.description, self._label = label, 'Real description', 'Private option'
        self._private_value, self.is_enabled, self.is_visible = private, enabled, True
        self.calls = 0
    def on_select(self):
        self.calls += 1
        self.label = 'Real option: Yes'


class Category:
    def __init__(self, label, settings=(), categories=()):
        self.label, self.settings, self.categories = label, list(settings), list(categories)


class Item:
    def __init__(self, label, **kwargs): self.label, self.properties = label, {}
    def setProperty(self, key, value): self.properties[key] = value


class Control:
    def __init__(self): self.items, self.position = [], 0
    def reset(self): self.items = []
    def addItems(self, items): self.items.extend(items)
    def selectItem(self, position): self.position = position
    def getSelectedPosition(self): return self.position


class Window:
    def __init__(self, *args, **kwargs):
        self.controls = {6100:Control(),6200:Control()}
        self.properties, self.focus, self.closed = {}, 6100, False
    def setProperty(self, key, value): self.properties[key] = value
    def getControl(self, cid): return self.controls[cid]
    def setFocus(self, control): self.focus = next(cid for cid, c in self.controls.items() if c is control)
    def getFocusId(self): return self.focus
    def close(self): self.closed = True


class SettingsTests(unittest.TestCase):
    def window(self, root):
        tree = ast.parse(SOURCE.read_text())
        tree.body = [node for node in tree.body if not isinstance(node,(ast.Import,ast.ImportFrom))]
        self.messages = []
        env = {'xbmcgui':types.SimpleNamespace(WindowXMLDialog=Window,ListItem=Item,
                   Dialog=lambda:types.SimpleNamespace(ok=lambda *args:self.messages.append(args))),
               'C':types.SimpleNamespace(ACTION_BACK=(9,10,92),ACTION_RIGHT=(2,),ACTION_LEFT=(1,))}
        exec(compile(tree,str(SOURCE),'exec'),env)
        window = env['SettingsWindow'](root_category=root)
        window.onInit()
        return window

    def action(self, window, aid): window.onAction(types.SimpleNamespace(getId=lambda:aid))

    def test_real_category_hierarchy_and_root_actions_remain_accessible(self):
        root_setting, nested = Setting(), Setting()
        child = Category('Codecs',[nested])
        playback = Category('Playback',[],[child])
        root = Category('Settings',[root_setting],[playback])
        w = self.window(root)
        self.assertEqual([i.label for i in w.controls[6100].items],['General','Playback'])
        self.assertIs(w.rows[0][1],root_setting)
        w.controls[6100].position=1; w.onClick(6100)
        w.onClick(6200)
        self.assertIs(w.history[-1],child)
        w.onClick(6200)
        self.assertEqual(nested.calls,1)
        self.assertEqual(w.controls[6200].items[0].label,'Real option: Yes')
        self.action(w,92)
        self.assertIs(w.history[-1],playback)
        self.action(w,92)
        self.assertEqual(w.focus,6100)
        self.action(w,92)
        self.assertTrue(w.closed)

    def test_disabled_handler_keeps_its_original_explanation_and_hidden_item_is_not_called(self):
        setting=Setting(enabled=False)
        w=self.window(Category('Settings',[setting]))
        w.onClick(6200)
        self.assertEqual(setting.calls,1)  # on_select owns disabled reason, no duplicated guard/save
        setting.is_visible=False
        w.onClick(6200)
        self.assertEqual(setting.calls,1)

    def test_private_label_value_and_description_never_reach_listitem(self):
        class Private(Setting):
            _private_value=True
            is_enabled=True
            is_visible=True
            _label='Private setting'
            @property
            def label(self): raise AssertionError('private value read')
            @property
            def description(self): raise AssertionError('private description read')
        w=self.window(Category('Settings',[Private.__new__(Private)]))
        item=w.controls[6200].items[0]
        self.assertEqual(item.label,'Private setting')
        self.assertEqual(item.properties['cleanui.settings.description'],'Valor privado')

    def test_save_failure_does_not_leave_input_latched_or_expose_exception(self):
        setting=Setting()
        def fail(): raise RuntimeError('secret credential must not appear')
        setting.on_select=fail
        w=self.window(Category('Settings',[setting]))
        w.onClick(6200)
        self.assertFalse(w._selecting)
        self.assertNotIn('secret',str(self.messages))
        self.assertEqual(len(self.messages),1)

    def test_no_categories_is_safe_and_account_notice_has_no_fake_server_actions(self):
        w=self.window(Category('Settings'))
        self.assertEqual(w.rows,[])
        w.onClick(6100); w.onClick(6200)
        self.assertEqual(w.properties['cleanui.settings.empty'],'true')
        self.assertIn('app oficial',w.properties['cleanui.settings.account_notice'])

    def test_measured_layout_and_remote_focus_targets_are_defined(self):
        root=ET.parse(XML).getroot()
        cats=root.find(".//control[@id='6100']")
        rows=root.find(".//control[@id='6200']")
        self.assertEqual([cats.findtext(k) for k in ('left','top','width')],['130','232','385'])
        self.assertEqual([rows.findtext(k) for k in ('left','top','width')],['604','288','1187'])
        self.assertEqual(cats.find('focusedlayout').get('height'),'88')
        for control in (cats,rows):
            for tag in ('onleft','onright','onup','ondown'):
                self.assertIn(control.findtext(tag),('6100','6200'))
        for node in root.iter('control'):
            if node.find('texture') is not None:
                self.assertEqual(node.findtext('texture'),'white.png')


if __name__=='__main__': unittest.main()
