"""
Génère favicons, icônes PWA et logo de l'appli à partir de branding/logo-source.jpg.
Usage : pip install pillow numpy && python branding/generate_icons.py
"""

from PIL import Image, ImageDraw
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'branding' / 'logo-source.jpg'
PUB = ROOT / 'public'
CX, CY, R = 706, 331, 131          # cercle englobant l'emblème
BG = np.array([245, 250, 251])     # fond gris clair de l'image

a = np.asarray(Image.open(SRC).convert('RGB')).astype(float)
a = np.clip(a * 255.0 / BG, 0, 255).astype(np.uint8)   # fond gris -> blanc
# Tout ce qui est hors du cercle de l'emblème (texte, dégradé) passe en blanc
yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]
dist = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2)
fade = np.clip((dist - (R + 2)) / 4, 0, 1)[..., None]
a = (a * (1 - fade) + 255 * fade).astype(np.uint8)
full = Image.fromarray(a)

def emblem(size, ratio, shape):
    """ratio = rayon de l'emblème / taille ; shape = disc | square"""
    big = size * 4
    half = R / ratio / 2           # demi-côté du cadrage dans l'image source
    crop = full.crop((round(CX - half), round(CY - half), round(CX + half), round(CY + half)))
    crop = crop.resize((big, big), Image.LANCZOS).convert('RGBA')
    if shape == 'disc':
        mask = Image.new('L', (big, big), 0)
        pad = big * 0.01
        ImageDraw.Draw(mask).ellipse((pad, pad, big - pad, big - pad), fill=255)
        crop.putalpha(mask)
    return crop.resize((size, size), Image.LANCZOS)

for s in (16, 32, 96, 128):
    emblem(s, 0.46, 'disc').save(f'{PUB}/icons/favicon-{s}x{s}.png')
for s in (192, 512):
    emblem(s, 0.46, 'disc').save(f'{PUB}/icons/icon-{s}.png')
    emblem(s, 0.36, 'square').convert('RGB').save(f'{PUB}/icons/icon-maskable-{s}.png')
emblem(180, 0.42, 'square').convert('RGB').save(f'{PUB}/icons/apple-touch-icon.png')
emblem(256, 0.46, 'disc').save(PUB / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
emblem(256, 0.46, 'disc').save(ROOT / 'src' / 'assets' / 'logo.png')
