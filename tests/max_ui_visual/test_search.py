import ast
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui'
SOURCE = ROOT / 'resources/lib/ui/search_view.py'
XML = ROOT / 'resources/skins/Default/1080i/uihome.xml'


class SearchTests(unittest.TestCase):
    def view(self, query=''):
        class Item:
            def __init__(self): self.properties = {}
            def setProperty(self, key, value): self.properties[key] = value
        class Control:
            def reset(self): self.items = []
            def addItems(self, items): self.items = items
        controller = types.SimpleNamespace(calls=[], cancelled=0)
        def cancel(window): controller.cancelled += 1
        def load(window, build, apply): controller.calls.append((build, apply))
        controller.cancel_navigation = cancel
        controller.load_navigation = load
        controller.repository = types.SimpleNamespace(build_search=lambda q: q)
        control = Control()
        window = types.SimpleNamespace(screen=types.SimpleNamespace(_cleanui_search_query=query, rails=[]),
                                       screen_kind='search', controller=controller, _cards={}, properties={},
                                       _configure_navigation=lambda: None, getControl=lambda cid: control)
        window.setProperty = window.properties.__setitem__
        env = {'UIAdapter': types.SimpleNamespace(to_list_item=lambda card,style: Item()),
               'C': types.SimpleNamespace(STYLE_LANDSCAPE='landscape')}
        tree = ast.parse(SOURCE.read_text())
        tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
        exec(compile(tree, str(SOURCE), 'exec'), env)
        return env['SearchView'](window), window, control

    def test_empty_query_has_no_invented_popular_cards_or_request(self):
        view, window, control = self.view()
        view.present()
        self.assertEqual(window.controller.calls, [])
        self.assertEqual(control.items, [])
        self.assertIn('Escribe', window.properties['cleanui.search.hint'])

    def test_late_query_result_cannot_replace_new_query_or_another_page(self):
        view, window, control = self.view()
        view.activate(8001)  # b
        stale = window.controller.calls[-1][1]
        view.activate(8000)  # ba
        current = window.controller.calls[-1][1]
        card = types.SimpleNamespace(art={'fanart':'wide.jpg','poster':'tall.jpg'}, info={'year':2026,'mpaa':'PG'})
        result = types.SimpleNamespace(rails=[types.SimpleNamespace(items=[card])])
        self.assertFalse(stale(result))
        self.assertEqual(view.query, 'ba')
        self.assertTrue(current(result))
        self.assertIs(window._cards[4510][0], card)
        self.assertEqual(control.items[0].properties['cleanui.display_art'], 'wide.jpg')
        self.assertEqual(control.items[0].properties['cleanui.search_meta'], '2026  PG')
        window.screen_kind = 'home'
        self.assertFalse(current(result))

    def test_clear_cancels_and_persists_empty_search_state(self):
        view, window, control = self.view('batman')
        view.activate(8102)
        self.assertEqual(window.controller.cancelled, 1)
        self.assertEqual(window.controller.calls, [])
        self.assertEqual(window.screen._cleanui_search_query, '')
        self.assertEqual(window._cards[4510], [])

    def test_editor_bounds_and_space_do_not_generate_duplicate_requests(self):
        view, window, control = self.view('x' * 80)
        view.activate(8000)
        self.assertEqual(window.controller.calls, [])
        view.activate(8100)
        self.assertEqual(len(view.query), 79)
        view.activate(8101)
        self.assertEqual(len(view.query), 80)
        count = len(window.controller.calls)
        view.activate(8101)
        self.assertEqual(len(window.controller.calls), count)

    def test_keyboard_has_one_reachable_key_for_every_spanish_letter_and_digit(self):
        root = ET.parse(XML).getroot()
        keyboard = root.find(".//control[@id='5800']")
        controls = {int(node.get('id')):node for node in keyboard.findall('control') if node.get('id')}
        letters = [controls[cid].findtext('label') for cid in range(8000, 8037)]
        self.assertEqual(''.join(letters), 'abcdefghijklmnñopqrstuvwxyz1234567890')
        self.assertEqual(len(set(letters)), 37)
        self.assertTrue(all(cid in controls for cid in [8100,8101,8102,4510]))
        known = {int(n.get('id')) for n in root.iter('control') if n.get('id')}
        for cid, node in controls.items():
            if cid == 4510: continue
            for tag in ('onleft','onright','onup','ondown'):
                self.assertIn(int(node.findtext(tag)), known)


if __name__ == '__main__': unittest.main()
