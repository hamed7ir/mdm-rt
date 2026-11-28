# MDM RT: an embedded Python for the helpers, made from a python-rt prefix (Kodi RT's CPython 3.14 build: python.exe,
# python314.dll with its extension modules built in, Lib\) in the layout of python.org's "embeddable package":
#
#   python314.dll  python.exe  python314.zip (the standard library, byte-compiled)  python314._pth
# (Python's licence: build-helpers.py puts it in licenses\python.txt.)
#
# python314._pth makes Python ignore PYTHONPATH / PYTHONHOME and the registry and puts only python314.zip and this
# folder on sys.path (no site-packages). Left out of the zip: the tests, IDLE, tkinter (python-rt has no Tcl/Tk),
# turtle, ensurepip/venv, pydoc's data, and the build-only folders.
#
# Run it WITH a Python of the same version (the .pyc format is per version, not per CPU): the x64 or x86 build of
# the same python-rt, e.g.
#   F:\kodi-rt\prefix\x64\python\python.exe -I mdm-rt\helpers\make-python-embed.py <prefix> <out dir>
import os, py_compile, shutil, sys, zipfile, importlib.util

EXCLUDE_DIRS = {'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'venv', 'pydoc_data',
                'site-packages', '__pycache__', 'lib2to3', 'idle_test', '__phello__'}
EXCLUDE_FILES = {'turtle.py', 'antigravity.py', 'this.py'}


def main(prefix, out):
    ver = '%d%d' % sys.version_info[:2]
    dll = os.path.join(prefix, 'python%s.dll' % ver)
    if not os.path.isfile(dll):
        sys.exit('%s not found: run this with the Python version of the prefix' % dll)
    os.makedirs(out, exist_ok=True)
    lib = os.path.join(prefix, 'Lib')
    zpath = os.path.join(out, 'python%s.zip' % ver)
    tmp = os.path.join(out, '_pyc.tmp')
    count = 0
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, dirs, files in os.walk(lib):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
            for f in sorted(files):
                if not f.endswith('.py') or f in EXCLUDE_FILES:
                    continue
                src = os.path.join(root, f)
                rel = os.path.relpath(src, lib).replace(os.sep, '/')
                # unchecked-hash .pyc: valid without its .py beside it (zipimport, sourceless)
                py_compile.compile(src, cfile=tmp, dfile=rel, doraise=True,
                                   invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
                z.write(tmp, rel[:-3] + '.pyc')
                count += 1
    os.remove(tmp)
    for f in ('python%s.dll' % ver, 'python.exe'):
        shutil.copy2(os.path.join(prefix, f), os.path.join(out, f))
    with open(os.path.join(out, 'python%s._pth' % ver), 'w', encoding='ascii', newline='\r\n') as f:
        f.write('python%s.zip\n.\n' % ver)
    print('%d modules, %s %d bytes, magic %s' % (count, zpath, os.path.getsize(zpath),
                                                importlib.util.MAGIC_NUMBER.hex()))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
