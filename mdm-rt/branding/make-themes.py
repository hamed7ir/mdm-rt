# MDM RT: the RT themes (crates/app/assets/themes/rt-*.toml), 7-Zip RT's dark look in MDM's theme format.
#
# 7-Zip RT (github.com/hamed7ir/7zip-rt, CPP/7zip/UI/FileManager/DarkTheme.cpp) draws a dark theme from Kodi RT's
# purple palette (#4a1388 #6b3aa8 #a24bff #c76bff #e3cfff) and recolours it for its other accent presets: every
# colour keeps the purple palette's lightness and saturation and takes the accent's hue (a grey accent gives a grey
# theme). This script does the same arithmetic (RgbToHsl / Hsl / ApplyAccent, ported line for line) and writes one
# MDM theme file per preset. They are dark on both sides (View > Always dark changes nothing), as 7-Zip RT's is.
#
# Usage: python -I mdm-rt\branding\make-themes.py [<themes folder>]   (default: crates\app\assets\themes)
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(os.path.join(HERE, '..', '..', 'crates', 'app', 'assets', 'themes'))

# 7-Zip RT's accent presets, the default (Kodi RT's purple) first. id, menu name, accent
PRESETS = [
    ('rt-purple', 'RT Purple (Kodi RT)', 0xa24bff),
    ('rt-blue', 'RT Blue', 0x3d8bff),
    ('rt-teal', 'RT Teal', 0x22c7b8),
    ('rt-green', 'RT Green', 0x3ccf6e),
    ('rt-orange', 'RT Orange', 0xff8a2b),
    ('rt-red', 'RT Red', 0xff4d5e),
    ('rt-pink', 'RT Pink', 0xff5fb7),
    ('rt-gray', 'RT Gray', 0x9aa0a6),
]

# the hand-picked purple palette (DarkTheme.cpp k_*), used as it is for the default accent
PURPLE = dict(window=0x1a0b33, list=0x12051f, control=0x2a1150, header=0x1d0840, border=0x4a1388, text=0xeee6fa,
              texthead=0xe3cfff, textdim=0x8f7aad, accent=0xa24bff, select=0x6b3aa8, selectdim=0x3d2363,
              button=0x2a1150, buttonhot=0x4a1388, buttondown=0x6b3aa8, buttonoff=0x221040)


def clamp01(v):
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def rgb_to_hsl(c):
    r, g, b = ((c >> 16) & 255) / 255.0, ((c >> 8) & 255) / 255.0, (c & 255) / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    l = (mx + mn) / 2
    if d < 1e-9:
        return 0.0, 0.0, l
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx - r < 1e-9:
        h = 60 * ((g - b) / d) + (360 if g < b else 0)
    elif mx - g < 1e-9:
        h = 60 * ((b - r) / d) + 120
    else:
        h = 60 * ((r - g) / d) + 240
    return h, s, l


def hsl(h, s, l):
    s, l = clamp01(s), clamp01(l)
    c = (1 - abs(2 * l - 1)) * s
    hp = h / 60
    while hp >= 6:
        hp -= 6
    while hp < 0:
        hp += 6
    t = hp
    while t >= 2:
        t -= 2
    x = c * (1 - abs(t - 1))
    r = g = b = 0.0
    i = int(hp)
    if i == 0:
        r, g = c, x
    elif i == 1:
        r, g = x, c
    elif i == 2:
        g, b = c, x
    elif i == 3:
        g, b = x, c
    elif i == 4:
        r, b = x, c
    else:
        r, b = c, x
    m = l - c / 2
    q = lambda v: int(clamp01(v + m) * 255 + 0.5)
    return (q(r) << 16) | (q(g) << 8) | q(b)


def palette(accent):
    if accent == PRESETS[0][2]:
        return dict(PURPLE)
    h, s, l = rgb_to_hsl(accent)
    k = s
    p = dict(window=hsl(h, 0.645 * k, 0.122), list=hsl(h, 0.722 * k, 0.071), control=hsl(h, 0.649 * k, 0.190),
             header=hsl(h, 0.778 * k, 0.141), border=hsl(h, 0.755 * k, 0.304), text=hsl(h, 0.667 * k, 0.941),
             texthead=hsl(h, 1.000 * k, 0.906), textdim=hsl(h, 0.237 * k, 0.578),
             accent=hsl(h, s, 0.50 if l < 0.50 else (0.75 if l > 0.75 else l)),
             select=hsl(h, 0.487 * k, 0.443), selectdim=hsl(h, 0.478 * k, 0.263))
    p.update(button=p['control'], buttonhot=p['border'], buttondown=p['select'], buttonoff=hsl(h, 0.600 * k, 0.157))
    return p


def hexc(c):
    return '"#%06x"' % c


def theme_text(tid, name, accent):
    p = palette(accent)
    seeds = [('background', p['window']), ('surface', p['list']), ('header', p['header']), ('text', p['text']),
             ('accent', p['accent']), ('selection', p['select']),
             ('error', 0xff8f9e), ('warning', 0xffc561), ('success', 0x6ccb5f)]
    roles = [('window', p['window']), ('text.muted', p['textdim']), ('selection.inactive', p['selectdim']),
             ('field', p['control']), ('field.border', p['border']), ('field.disabled', p['buttonoff']),
             ('group.line', p['border']), ('button', p['button']), ('button.hot', p['buttonhot']),
             ('button.pressed', p['buttondown']), ('button.border', p['border']), ('button.bottom', p['border']),
             ('button.disabled', p['buttonoff']), ('button.default.border', p['accent']),
             ('button.default.bottom', p['accent']), ('link', p['texthead']), ('tab', p['header']),
             ('tab.page', p['window']), ('scroll.track', p['list']), ('scroll.thumb', p['border']),
             ('scroll.thumb.hot', p['select']), ('scroll.thumb.pressed', p['accent'])]
    lines = ['# %s: one of MDM RT\'s built-in themes, 7-Zip RT\'s dark look (made by mdm-rt/branding/make-themes.py:' % name,
             '# Kodi RT\'s purple palette, or its lightness and saturation in the accent\'s hue). Dark on both sides.',
             '',
             'name = "%s"' % name,
             'icons = "accent"',
             '']
    for side in ('light', 'dark'):
        lines.append('[seeds.%s]' % side)
        lines += ['%s = %s' % (k, hexc(v)) for k, v in seeds]
        lines.append('')
    lines.append('[colors]')
    lines += ['"%s" = %s' % (k, hexc(v)) for k, v in roles]
    lines.append('')
    return '\n'.join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    for tid, name, accent in PRESETS:
        path = os.path.join(OUT, tid + '.toml')
        open(path, 'w', encoding='utf-8', newline='\n').write(theme_text(tid, name, accent))
        print('%-10s %-22s accent #%06x -> %s' % (tid, name, palette(accent)['accent'], path))


if __name__ == '__main__':
    main()
