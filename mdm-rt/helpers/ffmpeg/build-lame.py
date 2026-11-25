# MDM RT helpers: LAME's MP3 encoder (libmp3lame 3.100, LGPL) as a static library, for ffmpeg's --enable-libmp3lame
# (MDM's "Audio only MP3" choices: yt-dlp -x --audio-format mp3 runs ffmpeg -acodec libmp3lame).
#
#   python -I build-lame.py <arm32|x86> <lame-3.100 source dir> <prefix dir>
#
# Compiles libmp3lame\*.c (not vector\xmm_quantize_sub.c: x86 SSE only) with llvm-rt's clang-cl, -MT (the static C
# runtime, as ffmpeg's build here), config.h = LAME's own configMS.h copied into <prefix>\build (the source tree is
# only read), then llvm-lib: <prefix>\lib\mp3lame.lib and <prefix>\include\lame\lame.h, which ffmpeg's configure
# finds with -I<prefix>\include and -libpath:<prefix>\lib. LAME's configure and makefiles are not used.
# Source: lame-3.100.tar.gz, sha256 ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e.
import argparse, concurrent.futures, ctypes, os, re, shutil, subprocess, sys

RT = os.environ.get('RT_TOOLCHAIN', r'F:\cr\rt24-cr')          # llvm-rt 2.4 (clang-cl 23.1.1-rt2.4)
VC = os.environ.get('RT_VCTOOLS', r'D:\Program Files\vs22buildtools\VC\Tools\MSVC\14.44.35207')
SDK = os.environ.get('RT_WINSDK', r'D:\Windows Kits\10')
SDKINC = '10.0.26100.0'
TARGET = {'arm32': 'armv7-pc-windows-msvc', 'x86': 'i686-pc-windows-msvc'}
SOURCES = ['VbrTag.c', 'bitstream.c', 'encoder.c', 'fft.c', 'gain_analysis.c', 'id3tag.c', 'lame.c',
           'mpglib_interface.c', 'newmdct.c', 'presets.c', 'psymodel.c', 'quantize.c', 'quantize_pvt.c', 'reservoir.c',
           'set_get.c', 'tables.c', 'takehiro.c', 'util.c', 'vbrquantize.c', 'version.c']


def pgo_flags(pgo, src):
    """clang-cl flags for --pgo: none, gen (counting build) or use=<profdata> (+ ThinLTO, as ffmpeg-rt's use build).
    Static functions are named by their file relative to the source folder (-static-func-strip-dirname-prefix =
    the folder's separator count), so a profile fits any checkout."""
    if pgo == 'none':
        return []
    strip = ['-mllvm', '-static-func-strip-dirname-prefix=%d' % sum(c in '/\\' for c in src.rstrip('/\\') + '\\')]
    if pgo == 'gen':
        return ['-fprofile-generate'] + strip
    if pgo.startswith('use='):
        prof = pgo[4:]
        if not os.path.isfile(prof):
            sys.exit('no profile ' + prof)
        return ['-fprofile-use=' + prof, '-flto=thin', '-mllvm', '-pgso=false', '-Wno-profile-instr-unprofiled',
                '-Wno-profile-instr-out-of-date', '-Wno-backend-plugin'] + strip
    sys.exit('--pgo: none, gen or use=<profdata>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch', choices=sorted(TARGET))
    ap.add_argument('src')
    ap.add_argument('prefix')
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument('--pgo', default='none', help='none, gen (counting build) or use=<profdata>')
    a = ap.parse_args()
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal
    except Exception:
        pass
    src, pfx = os.path.abspath(a.src), os.path.abspath(a.prefix)
    if not os.path.isfile(os.path.join(src, 'include', 'lame.h')) or not os.path.isfile(os.path.join(src, 'configMS.h')):
        sys.exit(src + ' is not a LAME source tree')
    build = os.path.join(pfx, 'build')
    if os.path.exists(build):
        sys.exit(build + ' exists already (use a new prefix)')
    os.makedirs(build)
    # config.h = configMS.h, but its 8 integer typedefs (int8_t as __int8 = char, which the C runtime's stdint.h
    # declares as signed char: a redefinition error) replaced by <stdint.h>.
    lines, dropped = [], 0
    for line in open(os.path.join(src, 'configMS.h'), encoding='latin-1').read().split('\n'):
        if re.match(r'\s*typedef\s+(unsigned\s+)?__int(8|16|32|64)\s+u?int(8|16|32|64)_t;', line):
            dropped += 1
            continue
        lines.append(line)
        if line.strip().startswith('#pragma warning( disable : 4305 )'):
            lines.append('#include <stdint.h>  /* MDM RT: instead of the __intN typedefs */')
    if dropped != 8 or not any('stdint.h' in l for l in lines):
        sys.exit('configMS.h is not the expected 3.100 one (%d typedefs)' % dropped)
    open(os.path.join(build, 'config.h'), 'w', encoding='latin-1', newline='\n').write('\n'.join(lines))
    cl = os.path.join(RT, 'bin', 'clang-cl.exe')
    base = [cl, '--target=' + TARGET[a.arch], '-vctoolsdir', VC, '-winsdkdir', SDK, '-winsdkversion', SDKINC,
            '-nologo', '-MT', '-O2', '-w', '-DHAVE_CONFIG_H', '-D_CRT_SECURE_NO_WARNINGS', '-DNDEBUG',
            '-I' + build, '-I' + os.path.join(src, 'include'), '-I' + os.path.join(src, 'libmp3lame'), '-c']

    def compile_one(name):
        obj = os.path.join(build, name[:-2] + '.obj')
        r = subprocess.run(base + ['-Fo' + obj, os.path.join(src, 'libmp3lame', name)], capture_output=True)
        return name, obj, r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace')

    objs = []
    base += pgo_flags(a.pgo, src)
    with concurrent.futures.ThreadPoolExecutor(a.jobs) as ex:
        for name, obj, rc, out in ex.map(compile_one, SOURCES):
            if rc:
                sys.exit('%s failed:\n%s' % (name, out))
            objs.append(obj)
    os.makedirs(os.path.join(pfx, 'lib'), exist_ok=True)
    os.makedirs(os.path.join(pfx, 'include', 'lame'), exist_ok=True)
    lib = os.path.join(pfx, 'lib', 'mp3lame.lib')
    subprocess.run([os.path.join(RT, 'bin', 'llvm-ar.exe'), 'rcs', lib] + objs, check=True)
    shutil.copy2(os.path.join(src, 'include', 'lame.h'), os.path.join(pfx, 'include', 'lame', 'lame.h'))
    shutil.copy2(os.path.join(src, 'COPYING'), os.path.join(pfx, 'COPYING-lame.txt'))
    print('%s: %s (%d objects, %d bytes)' % (a.arch, lib, len(objs), os.path.getsize(lib)))


if __name__ == '__main__':
    main()
