# MDM RT branding: the purple-on-dark app icon, made from Mister Download Manager's own (crates/app/assets/icons/app,
# which upstream's tools/icon/build_icon.py makes from art/Mister Download Manager.png) by recolouring it in Kodi RT's
# palette (#4a1388 #6b3aa8 #a24bff #c76bff #e3cfff), as 7-Zip RT's icon is purple. No Pillow needed (icotool.py).
#
#   python -I mdm-rt\branding\make-icons.py <repo root> [<out dir>]
#
# Each pixel keeps its lightness and alpha; the hues change: the green arrow, hat band and pixel trail become Kodi RT
# purple (#a24bff's hue), the blue globe a deeper violet; black (the hat, the moustache), greys and white stay.
# Writes, into <out dir> (default: mdm-rt\branding\icons):
#   mdm-rt.ico               every size of the source .ico (the installer, shortcuts)
#   mdm-rt-<size>.png        each size as PNG (the poster, the README)
# and with --app also over the app's own crates/app/assets/icons/app/mdm-<size>.png and mdm.ico, which the program
# embeds (window, taskbar, tray, About, the exe's icon): MDM RT's patch "purple icon".
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import icotool

ACCENT_HUE = 272.0      # #a24bff
GLOBE_HUE = 262.0       # a deeper violet for the blues


def rgb_to_hsl(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    l = (mx + mn) / 2
    if d < 1e-9:
        return 0.0, 0.0, l
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = 60 * ((g - b) / d) + (360 if g < b else 0)
    elif mx == g:
        h = 60 * ((b - r) / d) + 120
    else:
        h = 60 * ((r - g) / d) + 240
    return h, s, l


def hsl_to_rgb(h, s, l):
    s, l = max(0.0, min(1.0, s)), max(0.0, min(1.0, l))
    c = (1 - abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(hp) % 6]
    m = l - c / 2
    return tuple(int(max(0.0, min(1.0, v + m)) * 255 + 0.5) for v in (r, g, b))


def recolour(rgba):
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        r, g, b, a = out[i], out[i + 1], out[i + 2], out[i + 3]
        if a == 0:
            continue
        h, s, l = rgb_to_hsl(r, g, b)
        if s < 0.12:
            continue                                   # black, greys, white
        if 60 <= h < 175:                              # greens, yellow-greens, teal-greens: the arrow, band, trail
            nh, ns, nl = ACCENT_HUE, min(1.0, s * 1.0), l
        elif 175 <= h < 255:                           # cyan and blue: the globe's sea
            nh, ns, nl = GLOBE_HUE, s * 0.85, l * 0.82
        else:
            continue
        out[i], out[i + 1], out[i + 2] = hsl_to_rgb(nh, ns, nl)
    return bytes(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    app = '--app' in sys.argv
    repo = args[0]
    out = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icons')
    src_dir = os.path.join(repo, 'crates', 'app', 'assets', 'icons', 'app')
    os.makedirs(out, exist_ok=True)
    images = icotool.read_ico(os.path.join(src_dir, 'mdm.ico'))
    new = []
    for im in images:
        rgba = recolour(im['rgba'])
        new.append((im['w'], im['h'], rgba))
        icotool.write_png(os.path.join(out, 'mdm-rt-%d.png' % im['w']), im['w'], im['h'], rgba)
    icotool.write_ico(os.path.join(out, 'mdm-rt.ico'), new)
    print('mdm-rt.ico: %s px' % ', '.join(str(w) for w, _, _ in new))
    if app:
        for w, h, rgba in new:
            p = os.path.join(src_dir, 'mdm-%d.png' % w)
            if os.path.isfile(p):
                icotool.write_png(p, w, h, rgba)
        icotool.write_ico(os.path.join(src_dir, 'mdm.ico'), new)
        print('the app\'s icons replaced in', src_dir)


if __name__ == '__main__':
    main()
