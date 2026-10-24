from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui'


class HeroTests(unittest.TestCase):
    def test_summary_is_bound_to_selected_card_and_does_not_cover_actions(self):
        root = ET.parse(ROOT / 'resources/skins/Default/1080i/uihome.xml').getroot()
        gallery = root.find(".//control[@id='4600']")
        button_top = int(root.find(".//control[@id='7300']/top").text)
        for tag in ['itemlayout', 'focusedlayout']:
            controls = gallery.find(tag).findall('control')
            summary = next(n for n in controls if n.findtext('label') == '$INFO[ListItem.Property(cleanui.featured_summary)]')
            meta = next(n for n in controls if n.findtext('label') == '$INFO[ListItem.Property(cleanui.featured_meta)]')
            logo = next(n for n in controls if n.findtext('texture') == '$INFO[ListItem.Art(clearlogo)]')
            bottom = lambda n: int(n.findtext('top')) + int(n.findtext('height'))
            self.assertLessEqual(bottom(logo), int(meta.findtext('top')))
            self.assertLessEqual(bottom(meta), int(summary.findtext('top')))
            self.assertLessEqual(bottom(summary), button_top)
            self.assertLessEqual(int(summary.findtext('left')) + int(summary.findtext('width')), 1920)


if __name__ == '__main__': unittest.main()
