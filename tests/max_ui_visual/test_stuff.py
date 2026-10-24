import ast
from pathlib import Path
import types
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui'
SOURCE=ROOT/'resources/lib/ui/stuff_view.py'


class StuffTests(unittest.TestCase):
    def view(self,kind='watchlist',cards=None):
        class Item:
            def __init__(self):self.properties={}
            def setProperty(self,k,v):self.properties[k]=v
        class Control:
            def reset(self):self.items=[]
            def addItems(self,items):self.items=items
            def setVisibleCondition(self,value):self.visible=value
        controls={cid:Control() for cid in (4520,7601)}
        calls=[]
        window=types.SimpleNamespace(screen_kind=kind,_cards={},properties={},getControl=controls.__getitem__)
        window.screen=types.SimpleNamespace(rails=[types.SimpleNamespace(items=cards or [])])
        window.setProperty=window.properties.__setitem__
        def replace(screen,newkind):
            window.screen=screen;window.screen_kind=newkind;calls.append(('replace',newkind))
        window.replace_screen=replace
        window.controller=types.SimpleNamespace(cancel_navigation=lambda source:None,open_watchlist=lambda source:calls.append(('load-watchlist',source)))
        tree=ast.parse(SOURCE.read_text());tree.body=[n for n in tree.body if not isinstance(n,(ast.Import,ast.ImportFrom))]
        env={'UIAdapter':types.SimpleNamespace(to_list_item=lambda card,style:Item()),'C':types.SimpleNamespace(STYLE_LANDSCAPE='landscape')}
        exec(compile(tree,str(SOURCE),'exec'),env)
        return env['StuffView'](window),window,controls,calls

    def test_actual_watchlist_cards_and_wide_art_are_preserved(self):
        card=types.SimpleNamespace(kind='movie',art={'fanart':'wide.jpg','poster':'tall.jpg'},info={'year':2026})
        view,window,controls,calls=self.view(cards=[card]);view.present()
        self.assertIs(window._cards[4520][0],card)
        self.assertEqual(controls[4520].items[0].properties['cleanui.display_art'],'wide.jpg')
        self.assertEqual(controls[4520].items[0].properties['cleanui.stuff_meta'],'2026')
        self.assertEqual(window.properties['cleanui.stuff.continue_available'],'false')
        self.assertEqual(controls[7601].visible,'false')
        self.assertEqual(calls,[])

    def test_empty_backend_does_not_invent_continue_or_saved_titles(self):
        view,window,controls,calls=self.view();view.present();view.activate(7601)
        self.assertEqual(window._cards[4520],[])
        self.assertIn('No hay títulos disponibles',window.properties['cleanui.stuff.empty_message'])
        self.assertEqual(calls,[])
        window.screen._cleanui_continue_screen=types.SimpleNamespace(rails=[types.SimpleNamespace(items=[types.SimpleNamespace(kind='page')])])
        view.present();self.assertEqual(controls[7601].visible,'false')

    def test_continue_tab_requires_real_model_and_can_return_to_same_list(self):
        view,window,controls,calls=self.view()
        previous=window.screen
        real=types.SimpleNamespace(rails=[types.SimpleNamespace(items=[types.SimpleNamespace(kind='episode',art={},info={})])])
        previous._cleanui_continue_screen=real
        view.present();self.assertEqual(controls[7601].visible,'true')
        view.activate(7601);self.assertIs(window.screen,real)
        view.activate(7600);self.assertIs(window.screen,previous)
        self.assertEqual([name for name,arg in calls],['replace','replace'])

    def test_four_column_geometry_matches_observed_stuff_grid(self):
        root=ET.parse(ROOT/'resources/skins/Default/1080i/uihome.xml').getroot()
        panel=root.find(".//control[@id='4520']");layout=panel.find('itemlayout')
        x=int(panel.findtext('left'));step=int(layout.get('width'))
        self.assertEqual([x+11+i*step for i in range(4)],[130,555,980,1405])
        self.assertEqual(int(panel.findtext('top'))+11+int(layout.get('height')),683)
        self.assertEqual(int(panel.findtext('width'))//step,4)
        ids=[int(n.get('id')) for n in root.iter('control') if n.get('id')]
        self.assertEqual(len(ids),len(set(ids)))


if __name__=='__main__':unittest.main()
