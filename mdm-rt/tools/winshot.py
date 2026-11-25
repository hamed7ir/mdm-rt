# MDM RT test helper (from 7-Zip RT tools/winshot.py): screenshots of one program's windows (PrintWindow, PW_RENDERFULLCONTENT), as PNG,
# and WM_COMMAND to open a menu item, so the dark theme can be checked on a build server without clicking.
#   python -I winshot.py shot <out-prefix> <pid> [timeout s]      every visible top-level window of that process
#   python -I winshot.py command <pid> <command id>                WM_COMMAND to the process's main window
#   python -I winshot.py close <pid>                               WM_CLOSE to every top-level window of it
import ctypes, os, struct, sys, time, zlib
from ctypes import wintypes as W

u32 = ctypes.WinDLL('user32', use_last_error=True)
g32 = ctypes.WinDLL('gdi32', use_last_error=True)
try:
    u32.SetProcessDPIAware()
except Exception:
    pass

EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u32.EnumWindows.argtypes = [EnumProc, W.LPARAM]
u32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
u32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
u32.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
u32.IsWindowVisible.argtypes = [W.HWND]
u32.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
u32.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
u32.GetDC.argtypes = [W.HWND]
u32.GetDC.restype = W.HDC
u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
u32.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
u32.GetWindow.argtypes = [W.HWND, W.UINT]
u32.GetWindow.restype = W.HWND
g32.CreateCompatibleDC.argtypes = [W.HDC]
g32.CreateCompatibleDC.restype = W.HDC
g32.CreateCompatibleBitmap.argtypes = [W.HDC, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = W.HBITMAP
g32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
g32.SelectObject.restype = W.HGDIOBJ
g32.DeleteObject.argtypes = [W.HGDIOBJ]
g32.DeleteDC.argtypes = [W.HDC]
g32.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]


def windows_of(pid):
    res = []
    def cb(h, _):
        p = W.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            t = ctypes.create_unicode_buffer(256)
            c = ctypes.create_unicode_buffer(256)
            u32.GetWindowTextW(h, t, 256)
            u32.GetClassNameW(h, c, 256)
            res.append((h, t.value, c.value))
        return True
    u32.EnumWindows(EnumProc(cb), 0)
    return res


def png(path, w, h, bgra):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        row = bgra[y * w * 4:(y + 1) * w * 4]
        for x in range(w):
            b, g, r = row[4 * x], row[4 * x + 1], row[4 * x + 2]
            raw += bytes((r, g, b))
    def chunk(t, c):
        return struct.pack('>I', len(c)) + t + c + struct.pack('>I', zlib.crc32(t + c) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
                chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b''))


def shot(h, path):
    r = W.RECT()
    u32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w <= 0 or hh <= 0:
        return False
    sdc = u32.GetDC(None)
    mdc = g32.CreateCompatibleDC(sdc)
    bmp = g32.CreateCompatibleBitmap(sdc, w, hh)
    old = g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(h, mdc, 2)   # PW_RENDERFULLCONTENT
    class BIH(ctypes.Structure):
        _fields_ = [('biSize', W.DWORD), ('biWidth', W.LONG), ('biHeight', W.LONG), ('biPlanes', W.WORD),
                    ('biBitCount', W.WORD), ('biCompression', W.DWORD), ('biSizeImage', W.DWORD),
                    ('biXPelsPerMeter', W.LONG), ('biYPelsPerMeter', W.LONG), ('biClrUsed', W.DWORD),
                    ('biClrImportant', W.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), w, -hh, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hh * 4)
    g32.SelectObject(mdc, old)
    g32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bih), 0)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(None, sdc)
    png(path, w, hh, buf.raw)
    return bool(ok)


def main():
    cmd = sys.argv[1]
    if cmd == 'shot':
        prefix, pid = sys.argv[2], int(sys.argv[3])
        timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 10
        t0 = time.time()
        wins = []
        while time.time() - t0 < timeout:
            wins = windows_of(pid)
            if wins:
                break
            time.sleep(0.3)
        time.sleep(0.8)   # let it paint
        wins = windows_of(pid)
        for i, (h, title, cls) in enumerate(wins):
            p = '%s-%d.png' % (prefix, i)
            shot(h, p)
            print('%s  [%s] %s' % (p, cls, title))
        if not wins:
            print('no window')
            sys.exit(1)
    elif cmd == 'command':
        pid, cid = int(sys.argv[2]), int(sys.argv[3])
        for h, title, cls in windows_of(pid):
            if u32.GetWindow(h, 4) is None:   # GW_OWNER: the main (unowned) window
                u32.PostMessageW(h, 0x0111, cid, 0)
                print('WM_COMMAND %d -> [%s] %s' % (cid, cls, title))
                break
    elif cmd == 'close':
        pid = int(sys.argv[2])
        for h, title, cls in windows_of(pid):
            u32.PostMessageW(h, 0x0010, 0, 0)
            print('WM_CLOSE -> [%s] %s' % (cls, title))
    else:
        sys.exit('usage: winshot.py shot|command|close ...')


if __name__ == '__main__':
    main()
