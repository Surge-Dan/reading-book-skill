"""Original SVG paper material and cutout primitives. No page layout or book taxonomy."""
from html import escape
import math
import random
import re


def paper(width: int, height: int, *, seed: int, color='#eee6d6', roughness=4) -> str:
    if any(type(n) is not int or n <= 0 for n in (width, height)) or not 0 <= roughness <= min(width, height) / 8:
        raise ValueError('纸张尺寸或边缘幅度无效。')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('纸色须为六位hex。')
    rng = random.Random(seed)
    points = []
    for start, end in (((0, 0), (width, 0)), ((width, 0), (width, height)),
                       ((width, height), (0, height)), ((0, height), (0, 0))):
        count = max(2, math.ceil(math.dist(start, end) / 17))
        for i in range(count):
            u = i / count
            x = start[0] + (end[0] - start[0]) * u
            y = start[1] + (end[1] - start[1]) * u
            x = min(width, max(0, x + rng.uniform(-roughness, roughness)))
            y = min(height, max(0, y + rng.uniform(-roughness, roughness)))
            points.append(f'{x:.2f},{y:.2f}')
    fibers = ''.join(f'<path d="M{rng.randrange(width)} {rng.randrange(height)}h{rng.randrange(2,9)}" stroke="#514839" stroke-opacity=".045"/>' for _ in range(min(90, width * height // 1800)))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-hidden="true"><polygon points="{" ".join(points)}" fill="{color}"/>{fibers}</svg>'


def cutout(asset_path: str, width: int, height: int, *, uid: str, contour: str) -> str:
    """Designer supplies an original contour; the image remains a registered local dependency."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', uid) or any(type(n) is not int or n <= 0 for n in (width, height)):
        raise ValueError('裁切ID或尺寸无效。')
    if not re.fullmatch(r'[MmLlHhVvCcSsQqTtAaZz0-9., +\-]+', contour):
        raise ValueError('裁切需要实际SVG路径。')
    if not asset_path or asset_path.startswith(('/', '\\')) or '\\' in asset_path or ':' in asset_path or '..' in asset_path.split('/'):
        raise ValueError('裁切素材须为本地相对路径。')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs><clipPath id="{uid}"><path d="{escape(contour, quote=True)}"/></clipPath></defs><image href="{escape(asset_path, quote=True)}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid slice" clip-path="url(#{uid})"/></svg>'
