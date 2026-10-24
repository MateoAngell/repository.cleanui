import ast
import importlib.util
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / 'source/slyguy.max.cleanui'
UI = ADDON / 'resources/lib/ui'
XML = ADDON / 'resources/skins/Default/1080i/ui_profiles.xml'
spec = importlib.util.spec_from_file_location('profile_layout', UI / 'profile_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


class ProfileTests(unittest.TestCase):
    def window(self, profiles, current=None):
        class Control:
            selected = 0
            def reset(self): self.items = []
            def addItems(self, items): self.items = items
            def selectItem(self, n): self.selected = n
            def getSelectedPosition(self): return self.selected
            def setWidth(self, n): self.width = n
            def setPosition(self, x, y): self.position = (x, y)
        control = Control()
        class Window:
            closed = False
            def __init__(self, *args, **kwargs): pass
            def setProperty(self, key, value): pass
            def getControl(self, n): return control
            def setFocus(self, value): self.focus = value
            def close(self): self.closed = True
        class Item:
            def __init__(self, label, offscreen): self.label = label
            def setArt(self, art): self.art = art
        tree = ast.parse((UI / 'profile_window.py').read_text())
        klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ProfileWindow')
        env = {'xbmcgui': types.SimpleNamespace(WindowXMLDialog=Window, ListItem=Item),
               'effects': types.SimpleNamespace(prepare=lambda w: None),
               'userdata': types.SimpleNamespace(get=lambda key: {'id': current}),
               'C': types.SimpleNamespace(ACTION_BACK=(9, 10, 92)),
               'row_geometry': layout.row_geometry, 'PROFILE_MAX_VISIBLE': layout.PROFILE_MAX_VISIBLE}
        exec(compile(ast.Module(body=[klass], type_ignores=[]), 'profile_window', 'exec'), env)
        window = env['ProfileWindow'](profiles=profiles)
        window.onInit()
        return window, control

    def test_current_profile_and_exact_selected_object_survive_layout(self):
        rows = [{'id': str(i), 'profileName': 'Perfil ' + str(i), '_avatar': 'https://example/' + str(i)} for i in range(4)]
        window, control = self.window(rows, '2')
        self.assertEqual(control.selected, 2)
        self.assertEqual(len(control.items), 4)
        self.assertEqual(control.items[2].art['thumb'], rows[2]['_avatar'])
        window.onClick(4100)
        self.assertIs(window.selected, rows[2])
        self.assertTrue(window.closed)

    def test_long_profile_row_is_bounded_without_dropping_profiles(self):
        rows = [{'id': str(i)} for i in range(7)]
        window, control = self.window(rows, '6')
        self.assertEqual(len(control.items), 7)
        self.assertEqual(control.selected, 6)
        left, top = control.position
        self.assertGreaterEqual(left, 0)
        self.assertLessEqual(left + control.width, 1920)
        self.assertEqual(control.width, 1600)

    def test_invalid_selection_and_back_do_not_choose_another_profile(self):
        window, control = self.window([{'id': 'one'}])
        control.selected = 99
        window.onClick(4100)
        self.assertIsNone(window.selected)
        self.assertFalse(window.closed)
        window.onAction(types.SimpleNamespace(getId=lambda: 92))
        self.assertTrue(window.closed)
        self.assertIsNone(window.selected)

    def test_profile_count_never_invents_a_create_action(self):
        rows = [{'id': 'one'}, {'id': 'two'}]
        window, control = self.window(rows)
        self.assertEqual(len(control.items), len(rows))
        root = ET.parse(XML).getroot()
        self.assertNotIn('Agregar perfil', ''.join(root.itertext()))

    def test_focus_grows_around_same_center_without_cutting_names(self):
        row = ET.parse(XML).getroot().find(".//control[@id='4100']")
        normal = next(n for n in row.findall('itemlayout/control') if n.find('texture') is not None and n.find('texture').get('diffuse') == 'circle-hd.png')
        focused = next(n for n in row.findall("focusedlayout/control") if n.find("texture") is not None and n.find("texture").get("diffuse") == "circle-hd.png")
        def bounds(n): return tuple(int(n.findtext(k)) for k in ('left', 'top', 'width', 'height'))
        nx, ny, nw, nh = bounds(normal)
        fx, fy, fw, fh = bounds(focused)
        self.assertEqual((nx + nw / 2, ny + nh / 2), (fx + fw / 2, fy + fh / 2))
        self.assertGreater(fw, nw)
        self.assertGreaterEqual(fx, 0)
        self.assertLessEqual(fx + fw, int(row.find('focusedlayout').get('width')))
        for node in row.findall('.//control[@type="label"]'):
            self.assertLessEqual(int(node.findtext('top')) + int(node.findtext('height')), int(row.findtext('height')))


if __name__ == '__main__': unittest.main()
