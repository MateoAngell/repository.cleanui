"""Share the same native navigation presentation in catalogue and entity views."""
from pathlib import Path
from copy import deepcopy
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui/resources/skins/Default/1080i'
IDS = {3003,3011,3012,3015,*range(3300,3320)}


def is_navigation(node):
    if node.get('id') and int(node.get('id')) in IDS: return True
    texture = node.findtext('texture') or ''
    label = node.findtext('label') or ''
    visible = node.findtext('visible') or ''
    if 'cleanui.nav.' in texture or 'cleanui.profile.avatar' in texture: return True
    if texture in ('max-nav-search.png','max-nav-watchlist.png'): return True
    if texture == 'max-nav-shade.png' and node.findtext('width') == '130': return True
    if node.get('type') == 'group' and 'cleanui.nav.open' in visible: return True
    if 'cleanui.nav.' in label or 'cleanui.profile.name' in label: return True
    if label in ('Buscar','Mis cosas','Ajustes','⚙') and 'cleanui.nav.open' in visible: return True
    if node.get('type') == 'image' and node.findtext('left') == '109' and 'cleanui.nav.open' in visible: return True
    return False


def build():
    home_path = ROOT / 'uihome.xml'; home = ET.parse(home_path).getroot(); source=home.find('controls')
    if source.find("control[@id='4998']") is None:
        button = ET.SubElement(source,'control',type='button',id='4998')
        for key,value in [('left','-20'),('top','-20'),('width','1'),('height','1'),('visible','false'),('enable','true'),('label','')]:ET.SubElement(button,key).text=value
    detail_path = ROOT / 'ui_detail.xml';detail=ET.parse(detail_path).getroot();target=detail.find('controls')
    for child in list(target):
        if is_navigation(child):target.remove(child)
    # Append after the entity body, before errors; a sidebar never becomes a
    # new root or a second metadata source.
    old_group=target.find("control[@id='5900']")
    if old_group is not None:target.remove(old_group)
    group=ET.Element('control',type='group',id='5900')
    for key,value in [('left','0'),('top','0'),('width','1920'),('height','1080'),('visible','!String.IsEqual(Window.Property(cleanui.detail.scrolled),true)')]:ET.SubElement(group,key).text=value
    for child in source:
        if is_navigation(child):group.append(deepcopy(child))
    insert_at=list(target).index(target.find("control[@id='5000']"))+1
    target.insert(insert_at,group)
    for path,root in [(home_path,home),(detail_path,detail)]:
        ET.indent(root,space='  ');path.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n')


if __name__ == '__main__':build()
