"""Build our geometric textures; no screenshot or packaged app asset is copied."""
from pathlib import Path
from math import exp, hypot
from PIL import Image

MEDIA = Path(__file__).resolve().parents[2] / 'source/slyguy.max.cleanui/resources/skins/Default/media'


def build():
    # Elliptical ambient light observed behind the TV profile picker.
    image = Image.new('RGB', (960, 540))
    pixels = image.load()
    for y in range(540):
        for x in range(960):
            v = exp(-2.2 * (((x - 480) / 720) ** 2 + ((y - 100) / 330) ** 2))
            fade = max(0.0, min(1.0, (500 - y) / 200))
            pixels[x, y] = tuple(round(c * v * fade) for c in (36, 40, 46))
    image.save(MEDIA / 'max-profile-atmosphere.png', optimize=True)
    image = Image.new('RGBA', (512, 512))
    pixels = image.load()
    for y in range(512):
        for x in range(512):
            radius = hypot(x - 255.5, y - 255.5)
            alpha = round(56 * exp(-((radius / 190) ** 2) * 2.2) * max(0, 1 - radius / 256))
            pixels[x, y] = (245, 245, 247, alpha)
    image.save(MEDIA / 'max-profile-focus-glow.png', optimize=True)


if __name__ == '__main__':
    build()
