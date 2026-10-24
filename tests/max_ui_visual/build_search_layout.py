"""Generate native TV controls from the measured 1080p reference geometry."""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

ADDON = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui'
PATH = ADDON / 'resources/skins/Default/1080i/uihome.xml'
MEDIA = ADDON / 'resources/skins/Default/media'
KEYS = 'abcdefghijklmnñopqrstuvwxyz1234567890'


def node(parent, kind, ident=None, **values):
    attrs = {'type': kind}
    if ident is not None: attrs['id'] = str(ident)
    element = ET.SubElement(parent, 'control', attrs)
    for key, value in values.items(): ET.SubElement(element, key).text = str(value)
    return element


def image(parent, x, y, w, h, texture, color=None, **values):
    element = node(parent, 'image', left=x, top=y, width=w, height=h, aspectratio='stretch', **values)
    ET.SubElement(element, 'texture', **({'colordiffuse': color} if color else {})).text = texture
    return element


def button(parent, ident, x, y, width, height, label):
    element = node(parent, 'button', ident, left=x, top=y, width=width, height=height,
                   font='font30_title', label=label, align='center', aligny='center',
                   textcolor='FFF5F5F7', focusedcolor='FF000000', textoffsetx=0, textoffsety=0)
    ET.SubElement(element, 'texturefocus', colordiffuse='FFF5F5F7').text = 'rounded-rect.png'
    ET.SubElement(element, 'texturenofocus', colordiffuse='FF282828').text = 'rounded-rect.png'
    return element


def build_icons():
    for name in ['backspace', 'space', 'clear']:
        image = Image.new('RGBA', (48, 48)); draw = ImageDraw.Draw(image)
        if name == 'backspace':
            draw.line([(7,24),(17,13),(38,13),(38,35),(17,35),(7,24)], fill='white', width=3)
            draw.line([(23,19),(31,28)], fill='white', width=3)
            draw.line([(31,19),(23,28)], fill='white', width=3)
        elif name == 'space':
            draw.line([(10,17),(10,31),(38,31),(38,17)], fill='white', width=3)
        else:
            draw.line([(11,14),(37,14)], fill='white', width=3)
            draw.line([(19,10),(29,10)], fill='white', width=3)
            draw.line([(15,15),(17,37),(31,37),(33,15)], fill='white', width=3)
            draw.line([(22,20),(22,32)], fill='white', width=2)
            draw.line([(27,20),(27,32)], fill='white', width=2)
        image.save(MEDIA / ('max-search-' + name + '.png'), optimize=True)


def build():
    root = ET.parse(PATH).getroot(); controls = root.find('controls')
    previous = controls.find("control[@id='5800']")
    if previous is not None: controls.remove(previous)
    group = node(controls, 'group', 5800, left=0, top=0, width=1920, height=1080,
                 visible='String.IsEqual(Window.Property(cleanui.screen.kind),search)')
    # Draw below the persistent sidebar and transient load/error controls.
    controls.remove(group); controls.insert(2, group)
    image(group, 0, 0, 1920, 1080, 'white.png', 'FF000000')
    image(group, 555, 83, 28, 28, 'max-nav-search.png', 'FFF5F5F7')
    for empty,color in [(True,'FF777777'),(False,'FFF5F5F7')]:
        node(group, 'label', left=598, top=67, width=1240, height=60, font='font40_title',
             textcolor=color, label='$INFO[Window.Property(cleanui.search.prompt)]', aligny='center',
             visible=('' if empty else '!')+'String.IsEmpty(Window.Property(cleanui.search.query))')
    node(group, 'label', left=555, top=170, width=1240, height=76, font='font27',
         textcolor='FFBDBDBD', label='$INFO[Window.Property(cleanui.search.hint)]', aligny='center',
         visible='String.IsEqual(Window.Property(cleanui.search.empty),true) + !String.IsEqual(Window.Property(cleanui.loading),true)')
    for index, letter in enumerate(KEYS):
        row, col = divmod(index, 6)
        key = button(group, 8000 + index, 130 + col * 62, 68 + row * 62, 56, 56, letter)
        links = {'onleft':8000+index-1 if col else 3011,
                 'onright':8000+index+1 if col<5 and index+1<len(KEYS) else 4510,
                 'onup':8000+index-6 if row else 8000+index,
                 'ondown':8000+index+6 if index+6<len(KEYS) else 8100+min(2,col//2)}
        for keyname,target in links.items(): ET.SubElement(key,keyname).text=str(target)
    for col in range(1, 6): image(group,130+col*62,440,56,56,'rounded-rect.png','FF282828')
    for index, name in enumerate(['backspace','space','clear']):
        ident = 8100+index; x=130+index*124
        key=button(group, ident, x,506,118,56,'')
        for keyname,target in {'onleft':ident-1 if index else 3011,'onright':ident+1 if index<2 else 4510,
                               'onup':8036 if index==0 else 8032+index,'ondown':ident}.items():ET.SubElement(key,keyname).text=str(target)
        for focused,color in [(False,'FFF5F5F7'),(True,'FF000000')]:
            image(group,x+35,510,48,48,'max-search-'+name+'.png',color,
                  visible=('' if focused else '!')+'Control.HasFocus('+str(ident)+')')
    panel=node(group,'panel',4510,left=544,top=146,width=1376,height=900,
               orientation='vertical',scrolltime=180,onleft=8005,onup=4510,ondown=4510,onright=4510)
    for tag,focused in [('itemlayout',False),('focusedlayout',True)]:
        layout=ET.SubElement(panel,tag,width='425',height='378')
        if focused:image(layout,0,0,407,239,'rounded-rect.png','FFF5F5F7',visible='Control.HasFocus(4510)')
        image(layout,11,11,385,217,'rounded-rect.png','FF282828')
        tile=image(layout,11,11,385,217,'$INFO[ListItem.Property(cleanui.display_art)]')
        tile.find('texture').set('background','true');tile.find('aspectratio').text='scale'
        node(layout,'textbox',left=11,top=245,width=385,height=68,font='font30_title',textcolor='FFF5F5F7',label='$INFO[ListItem.Label]')
        node(layout,'label',left=11,top=307,width=385,height=44,font='font27',textcolor='FFBDBDBD',label='$INFO[ListItem.Property(cleanui.search_meta)]',aligny='center')
    for image_control in controls.findall("control[@type='image']"):
        if image_control.findtext('texture')=='hbo-max-logo.png':
            visible=image_control.find('visible')
            if visible is None: visible=ET.SubElement(image_control,'visible')
            visible.text='!String.IsEqual(Window.Property(cleanui.screen.kind),search)'
    ET.indent(root,space='  ');PATH.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True)+b'\n')
    build_icons()


if __name__ == '__main__': build()
