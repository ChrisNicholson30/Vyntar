"""Vyntar colour contract. Standard library only; no native tools required."""
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWATCHES = set('midnight panel raised line edge selection ice silver slate cyan violet blue mint orchid amber coral black bright_red bright_green bright_yellow bright_blue bright_cyan'.split())
ROLES = set('ui.background ui.surface ui.surface_raised ui.border ui.focus text.primary text.secondary text.muted editor.current_line editor.selection.bg editor.selection.fg editor.caret syntax.comment syntax.keyword syntax.function syntax.type syntax.string syntax.number syntax.constant syntax.attribute syntax.operator syntax.punctuation syntax.variable syntax.escape syntax.link syntax.interpolation diagnostic.error diagnostic.warning diagnostic.info diagnostic.hint diff.add.fg diff.remove.fg diff.change.fg diff.add.bg diff.remove.bg diff.change.bg'.split())

def load(root=ROOT):
    def read(name):
        def unique(pairs):
            d = {}
            for k, v in pairs:
                if k in d:
                    raise ValueError('duplicate key: ' + k)
                d[k] = v
            return d
        return json.loads((root / 'palette' / name).read_text(), object_pairs_hook=unique)
    p, roles, ansi = (read(n) for n in ('palette.json', 'semantics.json', 'ansi.json'))
    assert set(p) == {'version', 'base', 'variants'} and p['version'] == 1, 'palette structure'
    assert set(p['base']) == SWATCHES, 'swatch contract'
    assert set(p['variants']) == {'pulse', 'endurance'}, 'variant contract'
    assert set(roles) == ROLES, 'role contract'
    assert set(ansi) == {str(i) for i in range(16)}, 'ANSI slots must be 0–15'
    result = {}
    for slug, variant in p['variants'].items():
        assert set(variant) == {'name', 'overrides'}, 'variant structure'
        assert variant['name'] == 'Vyntar ' + slug.title(), 'canonical name'
        assert set(variant['overrides']) <= SWATCHES, 'unexpected override'
        swatches = dict(p['base'], **variant['overrides'])
        assert all(isinstance(v, str) and re.fullmatch(r'#[0-9A-F]{6}', v) for v in swatches.values()), 'opaque uppercase sRGB required'
        assert all(v in swatches for v in ansi.values()), 'unresolved ANSI swatch'
        assert all(v in swatches for k, v in roles.items() if not k.endswith('.bg') or k.startswith('editor.')), 'unresolved role'
        assert all(roles['diff.' + r + '.bg'] is None for r in ('add', 'remove', 'change')), 'diff backgrounds are forbidden'
        resolved = {k: swatches[v] if v is not None else None for k, v in roles.items()}
        result[slug] = {'name': variant['name'], 'swatches': swatches, 'roles': resolved, 'ansi': [swatches[ansi[str(i)]] for i in range(16)]}
    return result

def rgb(colour):
    return tuple(int(colour[i:i+2], 16) / 255 for i in (1, 3, 5))

def linear(x):
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4

def luminance(colour):
    return sum(a * linear(v) for a, v in zip((0.2126, 0.7152, 0.0722), rgb(colour)))

def contrast(a, b):
    lo, hi = sorted((luminance(a), luminance(b)))
    return (hi + .05) / (lo + .05)

def contrast_report(themes):
    rows = []
    for slug, t in themes.items():
        r = t['roles']
        fg = [k for k in r if k.startswith(('text.', 'syntax.', 'diagnostic.')) or k.endswith('.fg')]
        bg = ['ui.background', 'ui.surface', 'ui.surface_raised', 'editor.current_line', 'editor.selection.bg']
        for f in fg:
            for b in bg:
                ratio = contrast(r[f], r[b])
                rows.append((slug, f, b, ratio, 4.5))
        for i, colour in enumerate(t['ansi']):
            rows.append((slug, 'ansi.' + str(i), 'ui.background', contrast(colour, r['ui.background']), 4.5))
        for f in ('ui.focus', 'editor.caret'):
            for b in bg:
                rows.append((slug, f, b, contrast(r[f], r[b]), 3))
    return rows

def oklch(colour):
    """sRGB -> linear RGB -> OKLab -> polar OKLCH, hue in radians."""
    r, g, b = map(linear, rgb(colour))
    l = (.4122214708*r + .5363325363*g + .0514459929*b) ** (1/3)
    m = (.2119034982*r + .6806995451*g + .1073969566*b) ** (1/3)
    s = (.0883024619*r + .2817188376*g + .6299787005*b) ** (1/3)
    light = .2104542553*l + .793617785*m - .0040720468*s
    a = 1.9779984951*l - 2.428592205*m + .4505937099*s
    b = .0259040371*l + .7827717662*m - .808675766*s
    return {'gamut': 'sRGB', 'chroma': {'exact': math.hypot(a, b)}, 'hue': {'radians': math.atan2(b, a) % (2*math.pi)}, 'lightness': {'exact': light}, 'opacity': 1}
