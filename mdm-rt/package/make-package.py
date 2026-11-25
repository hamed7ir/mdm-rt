# MDM RT: gathers the folder of files the Setup installs (installer\build-installer.ps1 embeds it).
#   python -I mdm-rt\package\make-package.py <arm32|x64> <programs dir> <version> <deliver dir>
#                                            [--helpers <dir>] [--angle <dir>]
#     <programs dir>  build.py's output (out\arm32-thin, out\x64-thin): misterdownloadmanager*.exe
#     --helpers       ARM32: build-helpers.py's output (yt-dlp + Python, QuickJS, ffmpeg, versions.json)
#     --angle         ARM32: libEGL.dll, libGLESv2.dll, d3dcompiler_47.dll (Venetium's ARM32 release, win8-8.1 build)
# Writes <deliver>\MDM-RT-<version>-<arch>\ (no zip: the release is Setup only). x64 carries the programs only:
# there MDM downloads the official yt-dlp and ffmpeg itself, as upstream does.
import argparse, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
PROGRAMS = ['misterdownloadmanager.exe', 'misterdownloadmanager-nmhost.exe', 'misterdownloadmanager-cli.exe',
            'misterdownloadmanager-mcp.exe']
ANGLE = ['libEGL.dll', 'libGLESv2.dll', 'd3dcompiler_47.dll']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch', choices=['arm32', 'x64'])
    ap.add_argument('programs')
    ap.add_argument('version')
    ap.add_argument('deliver')
    ap.add_argument('--helpers')
    ap.add_argument('--angle')
    a = ap.parse_args()
    if a.arch == 'arm32' and not (a.helpers and a.angle):
        sys.exit('arm32 needs --helpers and --angle')
    out = os.path.join(a.deliver, 'MDM-RT-%s-%s' % (a.version, a.arch))
    if os.path.exists(out):
        sys.exit(out + ' exists already')
    os.makedirs(out)
    for f in PROGRAMS:
        shutil.copy2(os.path.join(a.programs, f), os.path.join(out, f))
    if a.arch == 'arm32':
        for f in ANGLE:
            shutil.copy2(os.path.join(a.angle, f), os.path.join(out, f))
        shutil.copytree(a.helpers, os.path.join(out, 'helpers'))
        # ANGLE's licence (BSD), from the Chromium tree Venetium is built from
        os.makedirs(os.path.join(out, 'licenses'))
        shutil.copy2(os.environ.get('MDMRT_ANGLE_LICENSE', r'F:\cr\src\third_party\angle\LICENSE'),
                     os.path.join(out, 'licenses', 'ANGLE.txt'))
    shutil.copy2(os.path.join(REPO, 'LICENSE'), os.path.join(out, 'LICENSE.txt'))
    shutil.copy2(os.path.join(REPO, 'ATTRIBUTION.md'), os.path.join(out, 'ATTRIBUTION.txt'))
    t = open(os.path.join(HERE, 'README-MDM-RT.txt'), encoding='utf-8').read().replace('\r\n', '\n')
    with open(os.path.join(out, 'README-MDM-RT.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(t.replace('@VERSION@', a.version).replace('@ARCH@', a.arch))
    n = sum(len(fs) for _, _, fs in os.walk(out))
    size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(out) for f in fs)
    print('package: %s (%d files, %d bytes)' % (out, n, size))


if __name__ == '__main__':
    main()
