# MDM RT: proves Rust PGO with this toolchain on a two-crate test before the real counting build:
#  1. cargo's -C metadata is the same with and without -Cprofile-generate (so every Rust symbol name is the same in
#     the counting build and the profile-use build, and cargo replaces artifacts instead of adding copies);
#  2. the x86 counting exe writes a .profraw where LLVM_PROFILE_FILE says, and llvm-profdata merges it;
#  3. the -Cprofile-use build finds a profile for every function (LLVM reports the ones it can't);
#  4. the ARM32 counting exe links (Rust's profiler runtime) and passes check-pe (Windows RT 8.1 imports).
# Its files go to MDMRT_PGOTEST_WORK (F:\mdm-rt\work\pgotest): target\, the configs, prof\, pgotest.profdata.
# The ARM32 counting exe it leaves there (target\thumbv7a-pc-windows-msvc\rt-thin\pgotest.exe) is the PGO kit's
# self-test (make-kit.py pgo --selftest): run-pgo.cmd checks that it writes counts on the tablet.
import glob, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get('MDMRT_PGOTEST_WORK', r'F:\mdm-rt\work\pgotest')
os.makedirs(WORK, exist_ok=True)
CARGO = r'F:\rt22\rustc\build-rt24\x86_64-pc-windows-msvc\stage1-tools-bin\cargo.exe'
RUST = r'F:\cr\rustc-rt24'
RT = r'F:\cr\rt24-cr\bin'
VC = 'D:/Program Files/vs22buildtools/VC/Tools/MSVC/14.44.35207'
SDK = 'D:/Windows Kits/10'
T = {'x86': ('i686-pc-windows-msvc', VC + '/bin/Hostx64/x86/link.exe',
             [VC + '/lib/x86', SDK + '/Lib/10.0.26100.0/um/x86', SDK + '/Lib/10.0.26100.0/ucrt/x86'], []),
     'arm32': ('thumbv7a-pc-windows-msvc', 'F:/cr/rt24-cr/bin/lld-link.exe',
               [VC + '/lib/arm', SDK + '/Lib/10.0.19041.0/um/arm', SDK + '/Lib/10.0.19041.0/ucrt/arm'],
               ['--cfg', 'windows_raw_dylib', '-C', 'target-cpu=cortex-a9', '-C', 'link-arg=/SUBSYSTEM:CONSOLE,6.02'])}
env = dict(os.environ, CARGO_HOME=r'F:\mdm-rt\cargo-home', RUSTC=os.path.join(RUST, 'bin', 'rustc.exe'),
           CARGO_TARGET_DIR=os.path.join(WORK, 'target'), CARGO_INCREMENTAL='0')
for k in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS'):
    env.pop(k, None)
fails = []


def check(ok, what):
    print(('  ok    ' if ok else '  FAIL  ') + what)
    if not ok:
        fails.append(what)


def build(arch, extra):
    t, linker, libs, more = T[arch]
    flags = ['-C', 'target-feature=+crt-static']
    for l in libs:
        flags += ['-C', 'link-arg=/LIBPATH:' + l]
    flags += more + extra
    cfg = os.path.join(WORK, 'cfg-%s.toml' % arch)
    with open(cfg, 'w', encoding='utf-8') as f:
        f.write('[target.%s]\nlinker = "%s"\nrustflags = [%s]\n' % (t, linker, ', '.join('"%s"' % x.replace('\\', '/') for x in flags)))
    # touch the two crates so cargo always runs (and prints) rustc for them: the -C metadata comparison needs it
    for f in ('src/main.rs', 'dep/src/lib.rs'):
        os.utime(os.path.join(HERE, f))
    r = subprocess.run([CARGO, 'build', '-v', '--profile', 'rt-thin', '--target', t, '--config', cfg, '-j', '4'],
                       cwd=HERE, env=env, capture_output=True, text=True, errors='replace')
    meta = dict(re.findall(r'--crate-name (\w+) .*?-C metadata=(\w+)', r.stderr))
    exe = os.path.join(WORK, 'target', t, 'rt-thin', 'pgotest.exe')
    return r.returncode, meta, r.stderr, exe


for arch in ('x86', 'arm32'):
    lib = glob.glob(os.path.join(RUST, 'lib', 'rustlib', T[arch][0], 'lib', 'libprofiler_builtins-*.rlib'))
    check(bool(lib), '%s: Rust profiler runtime in the sysroot' % arch)

print('== 1. -C metadata with and without -Cprofile-generate (x86)')
rc0, m0, err0, exe = build('x86', [])
rc1, m1, err1, exe = build('x86', ['-C', 'profile-generate=pgo-data'])
check(rc0 == 0 and rc1 == 0, 'both builds link (%d, %d)' % (rc0, rc1))
print('    plain   ', m0)
print('    counting', m1)
check(bool(m0) and m0 == m1, 'same -C metadata: symbol names match, artifacts replaced in place')

print('== 2. the counting exe writes its counts')
prof = os.path.join(WORK, 'prof')
shutil.rmtree(prof, ignore_errors=True)
os.makedirs(prof)
r = subprocess.run([exe, '3000000'], env=dict(env, LLVM_PROFILE_FILE=os.path.join(prof, 'count-%p.profraw')),
                   capture_output=True, text=True)
raws = glob.glob(os.path.join(prof, '*.profraw'))
check(r.returncode == 0 and len(raws) == 1, 'exit %d, %s' % (r.returncode, [os.path.basename(x) for x in raws]))
pd = os.path.join(WORK, 'pgotest.profdata')
r = subprocess.run([os.path.join(RT, 'llvm-profdata.exe'), 'merge', '-o', pd] + raws, capture_output=True, text=True)
check(r.returncode == 0 and os.path.isfile(pd), 'llvm-profdata merge %s' % r.stderr.strip()[-200:])
r = subprocess.run([os.path.join(RT, 'llvm-profdata.exe'), 'show', '--all-functions', pd], capture_output=True, text=True)
names = [l.strip().rstrip(':') for l in r.stdout.splitlines() if l.startswith('  ') and l.strip().endswith(':') and not l.strip().startswith(('Hash', 'Counters', 'Function count'))]
print('    functions in the profile:', [n for n in names if 'pgotest' in n or 'dep' in n][:6])

print('== 3. -Cprofile-use finds a profile for every function')
rc2, m2, err2, exe = build('x86', ['-C', 'profile-use=' + pd, '-C', 'llvm-args=-pgo-warn-missing-function'])
diag = [l for l in err2.splitlines() if 'Running `' not in l and 'llvm-args' not in l]
missing = [l for l in diag if 'no profile data' in l.lower()]
mismatch = [l for l in diag if 'hash mismatch' in l or 'control flow change' in l]
print('    profile-use diagnostics:', [l[:160] for l in diag if 'warning' in l.lower()][:5] or 'none')
check(rc2 == 0, 'profile-use build links')
check(m2 == m0, 'same -C metadata as the plain build')
check(not missing and not mismatch, 'no function without its profile (%d missing, %d mismatched)' % (len(missing), len(mismatch)))
for l in (missing + mismatch)[:5]:
    print('      ' + l[:200])

print('== 4. ARM32 counting build')
rc3, m3, err3, exe3 = build('arm32', ['-C', 'profile-generate=pgo-data'])
check(rc3 == 0 and os.path.isfile(exe3), 'links (%d)' % rc3)
if rc3:
    print(err3[-1500:])
else:
    r = subprocess.run([sys.executable, '-I', r'F:\mdm-rt\src\mdm-rt\tools\check-pe.py', os.path.join(RT, 'llvm-readobj.exe'),
                        r'F:\7zip-rt\device-dlls\rt81', exe3], capture_output=True, text=True)
    print('\n'.join('    ' + l for l in r.stdout.splitlines()[:12]))
    check(r.returncode == 0, 'check-pe vs Windows RT 8.1')
print('\nRESULT: %s' % ('ALL OK' if not fails else '%d FAILED: %s' % (len(fails), '; '.join(fails))))
