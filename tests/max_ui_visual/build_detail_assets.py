from pathlib import Path
from PIL import Image, ImageDraw


def build():
    root=Path(__file__).resolve().parents[2]/'source/slyguy.max.cleanui/resources/skins/Default/media'
    image=Image.new('RGBA',(512,128));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((3,3,508,124),radius=60,outline=(170,170,170,255),width=5)
    image.save(root/'max-tab-outline.png',optimize=True)


if __name__=='__main__':build()
