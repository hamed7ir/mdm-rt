# MDM RT: the helpers folder MDM RT's ARM32 Setup installs beside the program (<install>\helpers\), which the tools
# crate finds (`mdm_tools::bundled`): yt-dlp (launcher + embedded Python + yt-dlp's zipapp), QuickJS for YouTube's
# challenges, ffmpeg, and versions.json.
#
#   python -I mdm-rt\helpers\build-helpers.py <arm32|x86|x64> <out dir> [--ffmpeg <folder with ffmpeg.exe + DLLs>]
#
# Inputs (override with environment variables):
#   MDMRT_PYTHON_PREFIX   python-rt prefix for the arch (Kodi RT's CPython 3.14 build)  F:\kodi-rt\prefix\<arch>\python
#   MDMRT_HOST_PYTHON     a host Python of the same version, to byte-compile the stdlib  F:\kodi-rt\prefix\x64\python\python.exe
#   MDMRT_YTDLP           yt-dlp's zipapp release file ("yt-dlp")                        F:\mdm-rt\dl\yt-dlp-2026.11.23\yt-dlp
#   MDMRT_QJS_AMALGAM     QuickJS-ng's quickjs-amalgam.zip                                F:\mdm-rt\dl\quickjs-ng-0.18.0\...
#   --ffmpeg              a folder with ffmpeg.exe (+ ffprobe.exe, DLLs); default: none (the Setup has no ffmpeg).
#                         ARM32: ffmpeg\build-ffmpeg.sh's <dist>\bin (static ffmpeg.exe + ffprobe.exe, with LAME), with
#                         --ffmpeg-licenses <dist>\licenses and MDMRT_FFMPEG_VERSION=9.0.2-mdm-rt (it can't run here)
#   --qjs-pgo             qjs.exe: none (default), gen (the counting build for the PGO kit: LLVM_PROFILE_FILE says
#                         where its counts go) or use=<profdata> (the release, with the merged profile and ThinLTO),
#                         as ffmpeg\build-lame.py's --pgo
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, '..'))
RT = os.environ.get('RT_TOOLCHAIN', r'F:\cr\rt24-cr')
VC = os.environ.get('RT_VCTOOLS', r'D:\Program Files\vs22buildtools\VC\Tools\MSVC\14.44.35207')
SDK = os.environ.get('RT_WINSDK', r'D:\Windows Kits\10')
SDKINC = '10.0.26100.0'
# ARM32: armv7-pc-windows-msvc, as ffmpeg's, LAME's and Opus's builds: the same Thumb-2 code as thumbv7a (compared
# instruction by instruction for qjs), and the spelling for which clang finds its profile runtime
# (lib\clang\<v>\lib\windows\clang_rt.profile-arm.lib) for --qjs-pgo gen
ARCH = {'arm32': ('armv7-pc-windows-msvc', 'arm', '10.0.19041.0', ',6.02'),
        'x86': ('i686-pc-windows-msvc', 'x86', '10.0.26100.0', ''),
        'x64': ('x86_64-pc-windows-msvc', 'x64', '10.0.26100.0', '')}
PYPREFIX = {'arm32': r'F:\kodi-rt\prefix\arm32\python', 'x86': r'F:\kodi-rt\prefix\x86\python',
            'x64': r'F:\kodi-rt\prefix\x64\python'}


def env_path(name, default):
    return os.environ.get(name, default)


def pgo_flags(pgo, src):
    """(compiler flags, link flags) for --qjs-pgo: none, gen or use=<profdata> (+ ThinLTO), as ffmpeg\\build-lame.py's.
    Static functions are named by their file alone (-static-func-strip-dirname-prefix = the separator count of
    `src`, the folder holding every source), so a profile fits any checkout and temp folder."""
    if pgo == 'none':
        return [], []
    strip = ['-mllvm', '-static-func-strip-dirname-prefix=%d' % sum(c in '/\\' for c in src.rstrip('/\\') + '\\')]
    if pgo == 'gen':
        # the profile runtime (clang_rt.profile-<arch>.lib), which the instrumented objects ask for
        rtlib = glob.glob(os.path.join(RT, 'lib', 'clang', '*', 'lib', 'windows'))
        if not rtlib:
            sys.exit('no clang runtime folder under ' + RT)
        return ['-fprofile-generate'] + strip, ['/LIBPATH:' + rtlib[0]]
    if pgo.startswith('use='):
        prof = os.path.abspath(pgo[4:])
        if not os.path.isfile(prof):
            sys.exit('no profile ' + prof)
        return ['-fprofile-use=' + prof, '-flto=thin', '-mllvm', '-pgso=false'] + strip, []
    sys.exit('--qjs-pgo: none, gen or use=<profdata>')


def cc(arch, out_exe, sources, includes=(), defines=(), extra=(), link_extra=()):
    """clang-cl, static CRT, a console program; ARM32 at subsystem 6.02 (Windows RT 8.1)."""
    triple, lib, sdklib, subver = ARCH[arch]
    env = dict(os.environ)
    vci = os.path.join(VC, 'include')
    sdki = os.path.join(SDK, 'Include', SDKINC)
    env['INCLUDE'] = ';'.join([vci] + [os.path.join(sdki, d) for d in ('ucrt', 'um', 'shared')])
    obj = tempfile.mkdtemp(prefix='mdmrt-cc-')
    cmd = [os.path.join(RT, 'bin', 'clang-cl.exe'), '--target=' + triple, '-nologo', '-O2', '-MT', '-DNDEBUG',
           '-Wno-everything', '/Fo' + obj + '\\', '/Fe' + out_exe] + list(extra)
    cmd += ['-I' + i for i in includes] + ['-D' + d for d in defines] + list(sources)
    cmd += ['-fuse-ld=lld', '/link', '/SUBSYSTEM:CONSOLE' + subver, '/OPT:REF', '/OPT:ICF',
            '/LIBPATH:' + os.path.join(VC, 'lib', lib),
            '/LIBPATH:' + os.path.join(SDK, 'Lib', sdklib, 'um', lib),
            '/LIBPATH:' + os.path.join(SDK, 'Lib', sdklib, 'ucrt', lib)] + list(link_extra)
    subprocess.run(cmd, check=True, env=env)
    shutil.rmtree(obj, ignore_errors=True)
    print('built', out_exe, os.path.getsize(out_exe))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch', choices=sorted(ARCH))
    ap.add_argument('out')
    ap.add_argument('--ffmpeg')
    ap.add_argument('--ffmpeg-licenses', help='a folder with the licence texts of that ffmpeg build')
    ap.add_argument('--qjs-pgo', default='none', help='qjs.exe: none, gen (counting build) or use=<profdata>')
    ap.add_argument('--qjs-only', action='store_true', help='build qjs.exe alone (PGO tests)')
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if os.path.exists(out):
        sys.exit(out + ' exists already (a fresh folder is needed)')
    os.makedirs(out)
    versions = {}

    # QuickJS-ng: qjs.exe from the amalgamation and qjs.c (both in one folder: the PGO names of static functions)
    amalgam = env_path('MDMRT_QJS_AMALGAM', r'F:\mdm-rt\dl\quickjs-ng-0.18.0\quickjs-amalgam.zip')
    qsrc = tempfile.mkdtemp(prefix='mdmrt-qjs-')
    zipfile.ZipFile(amalgam).extractall(qsrc)
    shutil.copyfile(os.path.join(HERE, 'qjs', 'qjs.c'), os.path.join(qsrc, 'qjs.c'))
    extra, link_extra = pgo_flags(a.qjs_pgo, qsrc)
    cc(a.arch, os.path.join(out, 'qjs.exe'),
       [os.path.join(qsrc, 'quickjs-amalgam.c'), os.path.join(qsrc, 'qjs.c')],
       includes=[qsrc], defines=['QJS_BUILD_LIBC'], extra=extra, link_extra=link_extra)
    m = re.search(r'#define QJS_VERSION_MAJOR (\d+)\s+#define QJS_VERSION_MINOR (\d+)\s+#define QJS_VERSION_PATCH (\d+)',
                  open(os.path.join(qsrc, 'quickjs-amalgam.c'), encoding='utf-8', errors='replace').read())
    versions['qjs'] = '.'.join(m.groups()) if m else 'unknown'
    shutil.rmtree(qsrc, ignore_errors=True)
    if a.qjs_pgo != 'none':
        print('qjs.exe PGO:', a.qjs_pgo)
    if a.qjs_only:
        return

    # Python (embedded) + the launcher, named yt-dlp.exe, + yt-dlp's zipapp as yt-dlp.pyz
    prefix = env_path('MDMRT_PYTHON_PREFIX', PYPREFIX[a.arch])
    host = env_path('MDMRT_HOST_PYTHON', r'F:\kodi-rt\prefix\x64\python\python.exe')
    subprocess.run([host, '-I', os.path.join(HERE, 'make-python-embed.py'), prefix, out], check=True)
    cc(a.arch, os.path.join(out, 'yt-dlp.exe'), [os.path.join(HERE, 'pylauncher', 'pylauncher.c')])
    ytdlp = env_path('MDMRT_YTDLP', r'F:\mdm-rt\dl\yt-dlp-2026.11.23\yt-dlp')
    # byte-compiled by the same Python version as the helpers' (compile-pyz.py): no compiling at every start
    subprocess.run([host, '-I', os.path.join(HERE, 'compile-pyz.py'), ytdlp, os.path.join(out, 'yt-dlp.pyz')],
                   check=True)
    with zipfile.ZipFile(ytdlp) as z:
        m = re.search(r"__version__ = '([^']+)'", z.read('yt_dlp/version.py').decode())
    versions['yt-dlp'] = m.group(1) if m else 'unknown'
    # Mozilla's root certificates beside the launcher, which names them in SSL_CERT_FILE (certs/README.md)
    shutil.copyfile(os.path.join(HERE, 'certs', 'cacert.pem'), os.path.join(out, 'cacert.pem'))

    # ffmpeg (+ ffprobe and its DLLs, if it has any)
    if a.ffmpeg:
        for f in os.listdir(a.ffmpeg):
            if f.lower().endswith(('.exe', '.dll')):
                shutil.copyfile(os.path.join(a.ffmpeg, f), os.path.join(out, f))
        r = subprocess.run([os.path.join(out, 'ffmpeg.exe'), '-version'], capture_output=True, text=True) \
            if a.arch != 'arm32' else None
        ver = None
        if r and r.returncode == 0:
            ver = r.stdout.split()[2] if r.stdout.startswith('ffmpeg version') else None
        versions['ffmpeg'] = ver or os.environ.get('MDMRT_FFMPEG_VERSION', 'unknown')

    with open(os.path.join(out, 'versions.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(versions, f, indent=2, sort_keys=True)
        f.write('\n')

    # their licences: Python's (PSF), QuickJS-ng's (MIT: every copyright line of the amalgamation), yt-dlp's
    # (the Unlicense: public domain), FFmpeg's (LGPL; the folder --ffmpeg-licenses)
    lic = os.path.join(out, 'licenses')
    os.makedirs(lic)
    shutil.copyfile(env_path('MDMRT_PYTHON_LICENSE', r'F:\kodi-rt\release\python-rt\LICENSE.txt'), os.path.join(lic, 'python.txt'))
    qtext = zipfile.ZipFile(amalgam).read('quickjs-amalgam.c').decode('utf-8', 'replace')
    holders = []
    for line in qtext.splitlines():
        m = re.match(r'^\s*\*\s*(Copyright \(c\) .*)$', line)
        if m and m.group(1).strip() not in holders:
            holders.append(m.group(1).strip())
    mit = re.search(r'(Permission is hereby granted.*?THE SOFTWARE\.)', qtext, re.S).group(1)
    mit = '\n'.join(l.strip().lstrip('*').strip() for l in mit.splitlines())
    with open(os.path.join(lic, 'quickjs-ng.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('QuickJS-ng %s (https://github.com/quickjs-ng/quickjs), qjs.exe\n\n' % versions['qjs'] + '\n'.join(holders) + '\n\n' + mit + '\n')
    with open(os.path.join(lic, 'yt-dlp.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('yt-dlp %s (https://github.com/yt-dlp/yt-dlp), yt-dlp.pyz: released into the public domain under the Unlicense\n'
                '(https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE). Its bundled parts keep their own licences.\n' % versions['yt-dlp'])
    with open(os.path.join(lic, 'cacert.txt'), 'w', encoding='utf-8', newline='\r\n') as f:
        f.write('cacert.pem: Mozilla\'s list of root certificates for TLS servers (Mozilla NSS, as MSYS2\'s ca-certificates\n'
                '20260816-1 extracts it), under the Mozilla Public License 2.0: https://mozilla.org/MPL/2.0/\n'
                'The list: https://www.mozilla.org/en-US/about/governance/policies/security-group/certs/\n')
    if a.ffmpeg_licenses:
        shutil.copytree(a.ffmpeg_licenses, os.path.join(lic, 'ffmpeg'))
    print('helpers:', out, versions)


if __name__ == '__main__':
    main()
