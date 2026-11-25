# MDM RT branding (from 7-Zip RT's branding/icotool.py): small, dependency-free ICO/BMP/PNG helpers (no Pillow on the build server).
#   read_ico(path)   -> list of images: dict(w, h, bpp, rgba=bytes top-down RGBA)
#   write_ico(path, images)  images: list of (w, h, rgba); 256 px goes in as PNG, smaller as 32-bit DIBs
#   write_png(path, w, h, rgba)
#   Command line: python -I icotool.py dump <in.ico> <out-prefix>   (one PNG per image, to look at them)
import struct, sys, zlib


def _png_chunk(t, c):
    return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c) & 0xffffffff)


def png_bytes(w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]
    return (b'\x89PNG\r\n\x1a\n' + _png_chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
            _png_chunk(b'IDAT', zlib.compress(bytes(raw), 9)) + _png_chunk(b'IEND', b''))


def write_png(path, w, h, rgba):
    with open(path, 'wb') as f:
        f.write(png_bytes(w, h, rgba))


def _read_png(d):
    # 8-bit RGBA / RGB, non-interlaced only (what icon editors write)
    pos, w, h, ct, idat = 8, 0, 0, 0, b''
    while pos < len(d):
        n, t = struct.unpack_from('>I4s', d, pos)
        c = d[pos + 8:pos + 8 + n]
        if t == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', c)
            if bd != 8 or il != 0 or ct not in (2, 6):
                raise ValueError('unsupported PNG in icon')
        elif t == b'IDAT':
            idat += c
        pos += 12 + n
    bpp = 4 if ct == 6 else 3
    raw = zlib.decompress(idat)
    stride = w * bpp
    out, prev = bytearray(), bytearray(stride)
    i = 0
    for y in range(h):
        ft = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1: line[x] = (line[x] + a) & 255
            elif ft == 2: line[x] = (line[x] + b) & 255
            elif ft == 3: line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ft == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = line
        if bpp == 4:
            out += line
        else:
            for x in range(w):
                out += line[3 * x:3 * x + 3] + b'\xff'
    return w, h, bytes(out)


def _read_dib(d, off, w, h):
    hs, dw, dh, planes, bpp, comp = struct.unpack_from('<IiiHHI', d, off)
    ncol = struct.unpack_from('<I', d, off + 32)[0]
    if bpp <= 8 and ncol == 0:
        ncol = 1 << bpp
    pal = []
    p = off + hs
    for i in range(ncol if bpp <= 8 else 0):
        b, g, r, _ = d[p + 4 * i:p + 4 * i + 4]
        pal.append((r, g, b))
    p += 4 * len(pal)
    stride = ((w * bpp + 31) // 32) * 4
    mstride = ((w + 31) // 32) * 4
    xor_off = p
    and_off = p + stride * h
    rgba = bytearray(w * h * 4)
    has_alpha = False
    for y in range(h):
        row = xor_off + (h - 1 - y) * stride
        mrow = and_off + (h - 1 - y) * mstride
        for x in range(w):
            if bpp == 32:
                b, g, r, a = d[row + 4 * x:row + 4 * x + 4]
                if a: has_alpha = True
            elif bpp == 24:
                b, g, r = d[row + 3 * x:row + 3 * x + 3]; a = 255
            else:
                bit = x * bpp
                v = (d[row + bit // 8] >> (8 - bpp - bit % 8)) & ((1 << bpp) - 1)
                r, g, b = pal[v]; a = 255
            if bpp != 32 or True:
                if and_off + mstride * h <= len(d):
                    m = (d[mrow + x // 8] >> (7 - x % 8)) & 1
                    if m and bpp != 32:
                        a = 0
            rgba[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes((r, g, b, a))
    if bpp == 32 and not has_alpha:     # old 32-bit icons without alpha: use the AND mask
        for y in range(h):
            mrow = and_off + (h - 1 - y) * mstride
            for x in range(w):
                m = (d[mrow + x // 8] >> (7 - x % 8)) & 1
                rgba[(y * w + x) * 4 + 3] = 0 if m else 255
    return bpp, bytes(rgba)


def read_ico(path):
    d = open(path, 'rb').read()
    _, typ, n = struct.unpack_from('<HHH', d, 0)
    if typ != 1:
        raise ValueError(path + ': not an icon')
    imgs = []
    for i in range(n):
        w, h, cc, _, pl, bpp, size, off = struct.unpack_from('<BBBBHHII', d, 6 + 16 * i)
        w, h = w or 256, h or 256
        if d[off:off + 8] == b'\x89PNG\r\n\x1a\n':
            w, h, rgba = _read_png(d[off:off + size])
            imgs.append(dict(w=w, h=h, bpp=32, png=True, rgba=rgba))
        else:
            bpp, rgba = _read_dib(d, off, w, h)
            imgs.append(dict(w=w, h=h, bpp=bpp, png=False, rgba=rgba))
    return imgs


def dib_bytes(w, h, rgba):
    """32-bit BGRA DIB with an AND mask (alpha < 128 = transparent), as Windows XP+ icons use."""
    hdr = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    xor = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r, g, b, a = rgba[(y * w + x) * 4:(y * w + x) * 4 + 4]
            xor += bytes((b, g, r, a))
    mstride = ((w + 31) // 32) * 4
    mask = bytearray()
    for y in range(h - 1, -1, -1):
        row = bytearray(mstride)
        for x in range(w):
            if rgba[(y * w + x) * 4 + 3] < 128:
                row[x // 8] |= 0x80 >> (x % 8)
        mask += row
    return hdr + bytes(xor) + bytes(mask)


def write_ico(path, images, png_min=256):
    """png_min: images this wide or wider go in as PNG (Windows Vista and later read PNG at any size)"""
    images = sorted(images, key=lambda t: t[0])
    blobs = [png_bytes(w, h, rgba) if w >= png_min else dib_bytes(w, h, rgba) for (w, h, rgba) in images]
    out = bytearray(struct.pack('<HHH', 0, 1, len(images)))
    off = 6 + 16 * len(images)
    for (w, h, _), b in zip(images, blobs):
        out += struct.pack('<BBBBHHII', w if w < 256 else 0, h if h < 256 else 0, 0, 0, 1, 32, len(b), off)
        off += len(b)
    for b in blobs:
        out += b
    with open(path, 'wb') as f:
        f.write(bytes(out))


def read_bmp(path):
    """BMP (1/4/8/24/32 bpp, uncompressed) -> (w, h, bpp, palette, top-down index-or-rgb rows)."""
    d = open(path, 'rb').read()
    off = struct.unpack_from('<I', d, 10)[0]
    hs, w, h, planes, bpp, comp = struct.unpack_from('<IiiHHI', d, 14)
    if comp != 0:
        raise ValueError(path + ': compressed BMP')
    ncol = struct.unpack_from('<I', d, 14 + 32)[0] or (1 << bpp if bpp <= 8 else 0)
    pal = [tuple(d[14 + hs + 4 * i:14 + hs + 4 * i + 3][::-1]) for i in range(ncol)]
    return d, off, w, h, bpp, pal, 14 + hs


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'dump':
        for i, im in enumerate(read_ico(sys.argv[2])):
            p = '%s-%d-%dx%d-%dbpp.png' % (sys.argv[3], i, im['w'], im['h'], im['bpp'])
            write_png(p, im['w'], im['h'], im['rgba'])
            print(p)
    else:
        sys.exit(__doc__)
