# MDM RT: assembles a device test kit (folder + zip) from a build, the helpers folder and ANGLE.
#   python -I mdm-rt\kit\make-kit.py <preview|pgo> <programs dir> <helpers dir> <angle dir> <kit name> [--deliver DIR]
#     preview  the test kit (run-mdm*.cmd, browser-on/off.cmd, collect.cmd, README-preview.txt)
#     pgo      the PGO training kit: the counting build (build.py --pgo gen; helpers with the counting ffmpeg),
#              run-pgo.cmd, collect-pgo.cmd, README-pgo.txt
#     <programs dir>  build.py's output (out\arm32-thin): misterdownloadmanager*.exe
#     <helpers dir>   build-helpers.py's output (yt-dlp.exe, python314.*, yt-dlp.pyz, qjs.exe, ffmpeg..., versions.json)
#     <angle dir>     libEGL.dll, libGLESv2.dll, d3dcompiler_47.dll (Venetium's ARM32 release, win8-8.1 build)
# Writes <deliver>\<kit name>\ and <kit name>.zip (default deliver: F:\mdm-rt\deliver). .cmd/.txt files get CRLF.
import argparse, datetime, hashlib, json, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
PROGRAMS = ['misterdownloadmanager.exe', 'misterdownloadmanager-nmhost.exe', 'misterdownloadmanager-cli.exe',
            'misterdownloadmanager-mcp.exe']
ANGLE = ['libEGL.dll', 'libGLESv2.dll', 'd3dcompiler_47.dll']
MODES = {'preview': (['run-mdm.cmd', 'run-mdm-d3d9.cmd', 'run-mdm-d3d11.cmd', 'browser-on.cmd', 'browser-off.cmd',
                      'collect.cmd', 'ytdlp-time.cmd', 'ytdlp-speed.cmd', 'ytdlp-speed.py'], 'README-preview.txt'),
         'pgo': (['run-pgo.cmd', 'collect-pgo.cmd'], 'README-pgo.txt')}


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def crlf(src, dst, subst=None):
    t = open(src, encoding='utf-8').read().replace('\r\n', '\n')
    for k, v in (subst or {}).items():
        t = t.replace(k, v)
    with open(dst, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=sorted(MODES))
    ap.add_argument('programs')
    ap.add_argument('helpers')
    ap.add_argument('angle')
    ap.add_argument('name')
    ap.add_argument('--deliver', default=r'F:\mdm-rt\deliver')
    ap.add_argument('--setup', help='MDM-RT-Setup-<version>-arm32.exe to put beside the folder (README step 9)')
    ap.add_argument('--version', help='MDM RT\'s release number the build was made with (build.py --version, '
                                      'e.g. 1.1); default: the workspace\'s version (upstream\'s)')
    ap.add_argument('--selftest', help='pgo: the ARM32 counting test exe tools\\pgotest\\run-pgotest.py leaves '
                                       '(run-pgo.cmd checks it writes counts before MDM RT starts)')
    a = ap.parse_args()
    if a.mode == 'pgo' and not (a.selftest and os.path.isfile(a.selftest)):
        sys.exit('pgo needs --selftest <ARM32 counting pgotest.exe>')
    kit = os.path.join(a.deliver, a.name)
    if os.path.exists(kit) or os.path.exists(kit + '.zip'):
        sys.exit(kit + ' (or its zip) exists already')
    app = os.path.join(kit, 'MDM RT')
    os.makedirs(app)
    for f in PROGRAMS:
        shutil.copy2(os.path.join(a.programs, f), os.path.join(app, f))
    for f in ANGLE:
        shutil.copy2(os.path.join(a.angle, f), os.path.join(app, f))
    shutil.copytree(a.helpers, os.path.join(app, 'helpers'))
    os.makedirs(os.path.join(app, 'licenses'))
    shutil.copy2(os.environ.get('MDMRT_ANGLE_LICENSE', r'F:\cr\src\third_party\angle\LICENSE'),
                 os.path.join(app, 'licenses', 'ANGLE.txt'))
    shutil.copy2(os.path.join(REPO, 'LICENSE'), os.path.join(app, 'LICENSE.txt'))
    shutil.copy2(os.path.join(REPO, 'ATTRIBUTION.md'), os.path.join(app, 'ATTRIBUTION.txt'))
    version = a.version or open(os.path.join(REPO, 'Cargo.toml'),
                                encoding='utf-8').read().split('version = "', 1)[1].split('"', 1)[0]
    stamp = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(a.programs, PROGRAMS[0]))).strftime('%Y-%m-%d %H:%M')
    if a.setup:
        want = 'MDM-RT-Setup-%s-arm32.exe' % version
        if os.path.basename(a.setup) != want:
            sys.exit('--setup must be %s (the README names it)' % want)
        shutil.copy2(a.setup, os.path.join(kit, want))
    if a.mode == 'pgo':
        os.makedirs(os.path.join(kit, 'tools'))
        shutil.copy2(a.selftest, os.path.join(kit, 'tools', 'pgo-selftest.exe'))
    scripts, readme = MODES[a.mode]
    for s in scripts:
        crlf(os.path.join(HERE, s), os.path.join(kit, s))
    crlf(os.path.join(HERE, readme), os.path.join(kit, 'README.txt'), {'@VERSION@': version, '@DATE@': stamp})
    with open(os.path.join(kit, 'SHA256SUMS.txt'), 'w', encoding='ascii', newline='\r\n') as f:
        for root, _, files in os.walk(kit):
            for n in sorted(files):
                p = os.path.join(root, n)
                if n != 'SHA256SUMS.txt':
                    f.write('%s  %s\n' % (sha256(p), os.path.relpath(p, kit).replace('\\', '/')))
    zpath = kit + '.zip'
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _, files in os.walk(kit):
            for n in sorted(files):
                p = os.path.join(root, n)
                z.write(p, os.path.join(a.name, os.path.relpath(p, kit)).replace('\\', '/'))
    print('kit: %s\nzip: %s %d bytes sha256 %s' % (kit, zpath, os.path.getsize(zpath), sha256(zpath)))


if __name__ == '__main__':
    main()
