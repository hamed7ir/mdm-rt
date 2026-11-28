# MDM RT: yt-dlp's zipapp with its modules byte-compiled, so Python doesn't compile yt-dlp from source at every start.
# A zipapp holds .py files only, and zipimport can't cache what it compiles: every run of yt-dlp compiled every module
# it imported. On a Surface RT (Cortex-A9) `yt-dlp --version` took 13.6 s, paid again by every look-up and download.
#
#   F:\kodi-rt\prefix\x64\python\python.exe -I compile-pyz.py <yt-dlp zipapp> <out .pyz>
#
# Run it WITH the helpers' Python version (the .pyc format is per version, not per CPU), as make-python-embed.py.
# Each module gets an unchecked-hash .pyc beside its .py (zipimport tries <name>.pyc before <name>.py and loads an
# unchecked-hash one without looking at the source); the .py files stay for readable tracebacks; other files (the
# JavaScript of yt_dlp_ejs) are copied as they are.
import importlib.util, os, py_compile, sys, tempfile, zipfile


def main(src, out):
    count = 0
    fd, tmp_py = tempfile.mkstemp(suffix='.py')
    os.close(fd)
    tmp_pyc = tmp_py + 'c'
    try:
        with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
            for info in zin.infolist():
                data = zin.read(info)
                zout.writestr(info.filename, data)
                if info.filename.endswith('.py'):
                    with open(tmp_py, 'wb') as f:
                        f.write(data)
                    py_compile.compile(tmp_py, cfile=tmp_pyc, dfile=info.filename, doraise=True,
                                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
                    with open(tmp_pyc, 'rb') as f:
                        zout.writestr(info.filename[:-3] + '.pyc', f.read())
                    count += 1
    finally:
        for p in (tmp_py, tmp_pyc):
            if os.path.exists(p):
                os.remove(p)
    print('%s: %d modules byte-compiled (magic %s), %d bytes' % (out, count, importlib.util.MAGIC_NUMBER.hex(),
                                                                 os.path.getsize(out)))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
