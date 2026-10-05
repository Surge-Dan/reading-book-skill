"""Rasterize fixed display lettering; no font files are distributed.

Requires Pillow with RAQM and a local Gabriola font. Run only to regenerate
the two checked-in decorative assets, not during normal yearbook builds.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import argparse


def lettering(text, target, font_path):
    font = ImageFont.truetype(font_path, 360)
    features = ['ss01', 'ss02', 'ss03', 'ss04', 'ss05', 'ss06']
    proof = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    left, top, right, bottom = proof.textbbox((0, 0), text, font=font, features=features)
    padding = 24
    image = Image.new('RGBA', (right-left+padding*2, bottom-top+padding*2))
    ImageDraw.Draw(image).text((padding-left, padding-top), text, font=font,
                               features=features, fill='#24241f')
    image.save(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--font', default='C:/Windows/Fonts/Gabriola.ttf')
    args = parser.parse_args()
    out = Path(__file__).resolve().parents[1] / 'assets' / 'yearbook-art'
    out.mkdir(parents=True, exist_ok=True)
    for text, name in [('Reading', 'reading'), ('The Rhythm', 'rhythm')]:
        lettering(text, out / (name + '.png'), args.font)
