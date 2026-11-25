# MDM RT build driver: builds Mister Download Manager's programs with cargo for Windows ARM32 (Thumb-2, ARMNT;
# Windows RT 8.1 and Windows 10 ARM32), x64, and x86 (a test build that draws like ARM32: OpenGL ES through
# ANGLE, no Direct3D 12), with llvm-rt 2.4's rustc (F:\cr\rustc-rt24, rustc 1.100.0-nightly + its std for
# thumbv7a-pc-windows-msvc), rt2.4's clang-cl / lld-link for C code and the ARM32 link, MSVC 14.44 + SDK 10.0.26100
# headers (10.0.19041 ARM32 libraries).
#
#   python -I mdm-rt\build\build.py <arm32|x64|x86> [--variant thin|fat|dev] [--fresh] [--jobs N (8)]
#                                   [--no-incremental]
#                                   [--packages app,nmhost,cli,mcp] [--no-check] [--cargo-args ...]
#                                   [--pgo gen|use=<profdata>] [--version 0.5.2.1]
#
#   variant  thin  the release: ThinLTO (lto = "thin"), opt-level "s" as upstream, 16 codegen units
#            fat   upstream's own release profile (fat LTO, 1 codegen unit; needs ~5.5 GB RAM for the app)
#            dev   cargo's release profile without LTO, for quick compile checks
#   --pgo    gen: the counting build (rustc -Cprofile-generate; out\<arch>-thin-pgogen), run on a tablet with
#            LLVM_PROFILE_FILE set (the PGO kit); use=<profdata>: the release built with the merged profile
#            (-Cprofile-use). Both with the thin variant's profile and target folder: cargo's -C metadata, so
#            every Rust symbol name, must be the same in both builds or the profile matches nothing.
#            MDM's Rust code only; the C dependencies (aws-lc, QuickJS) are not counted.
#   packages the programs upstream ships (tools/installer/build.ps1): mdm-app (misterdownloadmanager.exe),
#            mdm-nmhost (-nmhost.exe), mdm-cli (-cli.exe), mdm-mcp (-mcp.exe); default all four, in one cargo run
#            so their features unify as upstream's.
#
# Nothing is written into the source tree except, during an ARM32/x86 build, Cargo.lock: the [patch] entries
# below turn 5-8 registry packages into path packages there, so the file is saved before and put back after.
# Outputs: <out>\<arch>-<variant>\ (programs + .pdb), cargo's own files in <target>.
#
# ARM32 needs these changes to dependencies, made as patched copies in <patched> (from cargo's registry and git
# caches; scripts and .patch files in this folder and ..\patches, each copy stamped with their hash):
#   windows-sys 0.52.0 / 0.61.2, windows 0.52.0 / 0.61.3 / 0.62.2   patch-windows-arm32.py (32/64-bit split types)
#   rquickjs-sys 0.14.0                                               patch-rquickjs-sys.py (bindings for ARM32/x86)
#   crash-context 0.8.0, minidump-writer 0.13.0                       ..\patches\crates\*.patch (ARM32 CONTEXT)
#   aws-lc-sys 0.47.0                                                 ..\patches\crates\*.patch (TLS callback names)
#   glutin 0.32.3 (ARM32 + x86)                                       ..\patches\crates\*.patch (MDM_ANGLE=d3d9|d3d11)
#   egui (anefzaoui/egui d110a3c, 10 crates)                          ..\patches\egui\*.patch (eframe: no WGL on ARM32)
import argparse, glob, gzip, hashlib, io, os, re, shutil, subprocess, sys, tarfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, '..'))              # mdm-rt\ (the fork's project folder)
REPO = os.path.normpath(os.path.join(PROJECT, '..'))              # the MDM workspace

# -- tools (this server's paths; override with environment variables) -------------------------------------------
RT = os.environ.get('RT_TOOLCHAIN', r'F:\cr\rt24-cr')                       # llvm-rt 2.4 (clang-cl, lld-link)
RUST = os.environ.get('RT_RUST', r'F:\cr\rustc-rt24')                       # rustc 1.100.0-nightly rt2.4 + std
CARGO = os.environ.get('RT_CARGO', r'F:\rt22\rustc\build-rt24\x86_64-pc-windows-msvc\stage1-tools-bin\cargo.exe')
CARGO_HOME = os.environ.get('CARGO_HOME', r'F:\mdm-rt\cargo-home')
VC = os.environ.get('RT_VCTOOLS', r'D:\Program Files\vs22buildtools\VC\Tools\MSVC\14.44.35207')
SDK = os.environ.get('RT_WINSDK', r'D:\Windows Kits\10')
SDKINC = '10.0.26100.0'
SDKLIB = {'arm32': '10.0.19041.0', 'x64': '10.0.26100.0', 'x86': '10.0.26100.0'}  # 19041: last ARM32 libraries
OUT = os.environ.get('MDMRT_OUT', r'F:\mdm-rt\out')
TARGET_DIR = os.environ.get('MDMRT_TARGET', r'F:\mdm-rt\target')
PATCHED = os.environ.get('MDMRT_PATCHED', r'F:\mdm-rt\build\patched')
TRASH = os.environ.get('MDMRT_TRASH', r'F:\mdm-rt\trash')
DEVICE_DLLS = os.environ.get('MDMRT_DEVICE_DLLS', r'F:\7zip-rt\device-dlls\rt81')   # RT 8.1 System32 copies
NASM = os.environ.get('RT_NASM', r'F:\kodi-rt\tools\nasm')   # x86 only: aws-lc's x86 assembly (its prebuilt objects: x64)

TRIPLE = {'arm32': 'thumbv7a-pc-windows-msvc', 'x64': 'x86_64-pc-windows-msvc', 'x86': 'i686-pc-windows-msvc'}
LIBARCH = {'arm32': 'arm', 'x64': 'x64', 'x86': 'x86'}
HOST = 'x86_64-pc-windows-msvc'
PACKAGES = {'app': ('mdm-app', 'misterdownloadmanager'), 'nmhost': ('mdm-nmhost', 'misterdownloadmanager-nmhost'),
            'cli': ('mdm-cli', 'misterdownloadmanager-cli'), 'mcp': ('mdm-mcp', 'misterdownloadmanager-mcp'),
            # not shipped: upstream's local test server (generated files, speed limits, faults), for tests here
            'labserver': ('mdm-labserver', 'labserver')}

# (package, version, kind, file): kind 'script' = a script in this folder run as <script> <src> <dst>;
# 'patch' = a unified diff (paths relative to the crate) in ..\patches applied to the copy.
REGISTRY_PATCHES = {
    'arm32': [
        ('windows-sys', '0.52.0', 'script', 'patch-windows-arm32.py'),
        ('windows-sys', '0.61.2', 'script', 'patch-windows-arm32.py'),
        ('windows', '0.52.0', 'script', 'patch-windows-arm32.py'),
        ('windows', '0.61.3', 'script', 'patch-windows-arm32.py'),
        ('windows', '0.62.2', 'script', 'patch-windows-arm32.py'),
        ('rquickjs-sys', '0.14.0', 'script', 'patch-rquickjs-sys.py'),
        ('crash-context', '0.8.0', 'patch', r'crates\crash-context-0.8.0.patch'),
        ('minidump-writer', '0.13.0', 'patch', r'crates\minidump-writer-0.13.0.patch'),
        ('aws-lc-sys', '0.47.0', 'patch', r'crates\aws-lc-sys-0.47.0.patch'),
        ('glutin', '0.32.3', 'patch', r'crates\glutin-0.32.3.patch'),
        ('accesskit_windows', '0.35.2', 'patch', r'crates\accesskit_windows-0.35.2.patch'),
    ],
    'x86': [
        ('rquickjs-sys', '0.14.0', 'script', 'patch-rquickjs-sys.py'),
        ('glutin', '0.32.3', 'patch', r'crates\glutin-0.32.3.patch'),
        ('accesskit_windows', '0.35.2', 'patch', r'crates\accesskit_windows-0.35.2.patch'),
    ],
    # accesskit_windows: a UIA event/property older Windows doesn't know aborted MDM (Windows RT 8.1, a touch tablet:
    # its touch keyboard is a UIA client, so AccessKit is on); x64 too, for Windows 10 before 1703
    'x64': [
        ('accesskit_windows', '0.35.2', 'patch', r'crates\accesskit_windows-0.35.2.patch'),
    ],
}
# git dependencies patched for ARM32 (and the x86 test build): (cache name, rev, patches folder, crates in it)
GIT_PATCHES = [
    ('egui', 'd110a3c', 'egui', ['ecolor', 'emath', 'epaint', 'epaint_default_fonts', 'egui', 'egui-winit',
                                 'egui_glow', 'egui-wgpu', 'egui_extras', 'eframe']),
]


def log(msg):
    print(time.strftime('%H:%M:%S ') + msg, flush=True)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def below_normal():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL


def to_trash(path):
    os.makedirs(TRASH, exist_ok=True)
    dst = os.path.join(TRASH, time.strftime('%Y%m%d-%H%M%S-') + os.path.basename(path.rstrip('\\/')))
    shutil.move(path, dst)
    log('moved to trash: %s -> %s' % (path, dst))


def link_tree(src, dst, real=()):
    """Copy src to dst as hard links (a new file for every path in `real`, which will be edited)."""
    real = {os.path.normcase(os.path.normpath(r)) for r in real}
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '.git']
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            a, b = os.path.join(root, f), os.path.join(dst, rel, f)
            r = os.path.normcase(os.path.normpath(os.path.join(rel, f)))
            if r in real:
                shutil.copy2(a, b)
                continue
            try:
                os.link(a, b)
            except OSError:
                shutil.copy2(a, b)


def lock_versions():
    """{(name, version)} of the registry packages in Cargo.lock, and {name: [git sources]}."""
    text = open(os.path.join(REPO, 'Cargo.lock'), encoding='utf-8').read()
    pk = re.findall(r'\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"\n(?:source = "([^"]+)")?', text)
    return {(n, v) for n, v, s in pk if s.startswith('registry+')}, {n: s for n, v, s in pk if s.startswith('git+')}


def registry_source(name, version):
    """The crate's files: cargo's unpacked copy, else unpacked here from its .crate in the download cache."""
    for d in glob.glob(os.path.join(CARGO_HOME, 'registry', 'src', '*', '%s-%s' % (name, version))):
        if os.path.isfile(os.path.join(d, 'Cargo.toml')):
            return d
    crates = glob.glob(os.path.join(CARGO_HOME, 'registry', 'cache', '*', '%s-%s.crate' % (name, version)))
    if not crates:
        sys.exit('%s %s is not in the cargo cache (%s): run the fetch first' % (name, version, CARGO_HOME))
    dst = os.path.join(PATCHED, '_src')
    os.makedirs(dst, exist_ok=True)
    with tarfile.open(crates[0], 'r:gz') as t:
        t.extractall(dst, filter='data')
    return os.path.join(dst, '%s-%s' % (name, version))


def patch_files(patch):
    return [m for m in re.findall(r'^\+\+\+ b/(\S+)', open(patch, encoding='utf-8').read(), re.M)]


def apply_patch(patch, cwd):
    subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '-p1', '--whitespace=nowarn', patch], cwd=cwd,
                   check=True)


def make_patched(key, src, dst, how, files):
    """dst = src changed by `how`; skipped when dst carries the stamp of the same inputs."""
    stamp = hashlib.sha256((key + '\n' + '\n'.join(sha256_file(f) for f in files)).encode()).hexdigest()
    sf = os.path.join(dst, '.mdmrt-stamp')
    if os.path.isfile(sf) and open(sf).read().strip() == stamp:
        return
    if os.path.exists(dst):
        to_trash(dst)
    how(src, dst)
    open(sf, 'w').write(stamp + '\n')
    log('patched copy made: ' + dst)


def prepare_patches(arch):
    """The [patch.crates-io] lines for this arch, making the patched copies first."""
    regs, gits = lock_versions()
    lines = []
    for name, version, kind, f in REGISTRY_PATCHES[arch]:
        if (name, version) not in regs:
            sys.exit('Cargo.lock has no %s %s any more: update REGISTRY_PATCHES (and check the patch)' % (name, version))
        src = registry_source(name, version)
        dst = os.path.join(PATCHED, '%s-%s' % (name, version))
        if kind == 'script':
            script = os.path.join(HERE, f)
            make_patched(f, src, dst, lambda s, d, script=script: subprocess.run(
                [sys.executable, '-I', script, s, d], check=True), [script])
        else:
            patch = os.path.join(PROJECT, 'patches', f)
            def how(s, d, patch=patch):
                link_tree(s, d, real=patch_files(patch))
                apply_patch(patch, d)
            make_patched(f, src, dst, how, [patch])
        alias = '%s-%s' % (name, version.replace('.', '_'))
        lines.append('%s = { package = "%s", path = "%s" }' % (alias, name, dst.replace('\\', '/')))
    if arch in ('arm32', 'x86'):
        for cache, rev, pdir, crates in GIT_PATCHES:
            co = [d for d in glob.glob(os.path.join(CARGO_HOME, 'git', 'checkouts', cache + '-*', rev))]
            if len(co) != 1:
                sys.exit('git checkout %s %s not found (or not one) in %s' % (cache, rev, CARGO_HOME))
            patches = sorted(glob.glob(os.path.join(PROJECT, 'patches', pdir, '*.patch')))
            dst = os.path.join(PATCHED, '%s-%s' % (cache, rev))
            def how(s, d, patches=patches):
                link_tree(s, d, real=[f for p in patches for f in patch_files(p)])
                for p in patches:
                    apply_patch(p, d)
            make_patched(cache + rev, co[0], dst, how, patches)
            for c in crates:
                lines.append('%s = { path = "%s" }' % (c, os.path.join(dst, 'crates', c).replace('\\', '/')))
    return lines


def toml_list(items):
    return '[' + ', '.join('"%s"' % i.replace('\\', '/') for i in items) + ']'


def write_config(arch, path, patch_lines, pgo_flags=()):
    t = TRIPLE[arch]
    rt = RT.replace('\\', '/')
    libs = [os.path.join(VC, 'lib', LIBARCH[arch]),
            os.path.join(SDK, 'Lib', SDKLIB[arch], 'um', LIBARCH[arch]),
            os.path.join(SDK, 'Lib', SDKLIB[arch], 'ucrt', LIBARCH[arch])]
    flags = list(pgo_flags) + ['-C', 'target-feature=+crt-static',
             # the build machine's paths out of the programs (as upstream's build.ps1 does)
             '--remap-path-prefix=%s=cargo' % CARGO_HOME, '--remap-path-prefix=%s=mdm' % REPO]
    for l in libs:
        flags += ['-C', 'link-arg=/LIBPATH:' + l]
    if arch == 'arm32':
        # windows-sys's raw-dylib imports (windows-targets has no ARM32 import libraries); Cortex-A9 scheduling
        # (Tegra 3; Tegra 4's A15 runs it too); console programs at subsystem 6.02 (app: build.rs says WINDOWS,6.02)
        flags += ['--cfg', 'windows_raw_dylib', '-C', 'target-cpu=cortex-a9',
                  '-C', 'link-arg=/SUBSYSTEM:CONSOLE,6.02']
        linker = rt + '/bin/lld-link.exe'
    else:
        linker = os.path.join(VC, 'bin', 'Hostx64', 'x64' if arch == 'x64' else 'x86', 'link.exe')
    if arch == 'x86':
        flags += ['--cfg', 'mdm_rt_angle']          # draw like ARM32: no wgpu, EGL (ANGLE) only
    host_linker = os.path.join(VC, 'bin', 'Hostx64', 'x64', 'link.exe')
    cfg = ['# generated by mdm-rt/build/build.py; do not edit', '']
    cfg += ['[target.%s]' % t, 'linker = "%s"' % linker.replace('\\', '/'), 'rustflags = ' + toml_list(flags), '']
    if t != HOST:
        cfg += ['[target.%s]' % HOST, 'linker = "%s"' % host_linker.replace('\\', '/'), '']
    env_t = t.replace('-', '_')
    cfg += ['[env]',
            'CC_%s = "%s/bin/clang-cl.exe"' % (env_t, rt),
            'CXX_%s = "%s/bin/clang-cl.exe"' % (env_t, rt),
            'AR_%s = "%s/bin/llvm-lib.exe"' % (env_t, rt)]
    if arch == 'arm32':
        # aws-lc has no ARM32 Windows assembly and its target.h doesn't turn the assembly off there
        # (AWS_LC_SYS_NO_ASM is refused in optimised builds): portable C.
        cfg += ['CFLAGS_%s = "-DOPENSSL_NO_ASM"' % env_t]
    cfg += ['',
            '[profile.rt-thin]', 'inherits = "release"', 'lto = "thin"', 'codegen-units = 16', '',
            '[profile.rt-dev]', 'inherits = "release"', 'lto = false', 'codegen-units = 16', '']
    if patch_lines:
        cfg += ['[patch.crates-io]'] + patch_lines + ['']
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(cfg))


def build_env(arch):
    env = dict(os.environ)
    vci = os.path.join(VC, 'include')
    sdki = os.path.join(SDK, 'Include', SDKINC)
    env['INCLUDE'] = ';'.join([vci] + [os.path.join(sdki, d) for d in ('ucrt', 'um', 'shared', 'winrt', 'cppwinrt')])
    # LIB = the host's libraries (build scripts link with MSVC's link.exe); the ARM32/x86 links get theirs with
    # /LIBPATH, which comes first.
    env['LIB'] = ';'.join([os.path.join(VC, 'lib', 'x64'), os.path.join(SDK, 'Lib', SDKINC, 'um', 'x64'),
                           os.path.join(SDK, 'Lib', SDKINC, 'ucrt', 'x64')])
    env['CARGO_HOME'] = CARGO_HOME
    env['RUSTC'] = os.path.join(RUST, 'bin', 'rustc.exe')
    env['RUSTDOC'] = os.path.join(RUST, 'bin', 'rustdoc.exe')
    env['CARGO_TARGET_DIR'] = TARGET_DIR
    env['CARGO_INCREMENTAL'] = '0'
    if arch == 'x86':
        env['PATH'] = NASM + os.pathsep + env.get('PATH', '')
    for k in ('RUSTFLAGS', 'CARGO_ENCODED_RUSTFLAGS', 'CARGO_BUILD_RUSTFLAGS'):   # they would replace the config's
        env.pop(k, None)
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('arch', choices=sorted(TRIPLE))
    ap.add_argument('--variant', default='thin', choices=('thin', 'fat', 'dev'))
    ap.add_argument('--packages', default='app,nmhost,cli,mcp')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--no-incremental', action='store_true',
                    help='rustc without its incremental cache (thin/dev use it; fat and --pgo never do)')
    ap.add_argument('--fresh', action='store_true', help='move this arch+variant target folder to trash first')
    ap.add_argument('--no-check', action='store_true')
    ap.add_argument('--pgo', default='none', help='gen (counting build) or use=<profdata> (thin variant only)')
    ap.add_argument('--version', help='a fix release of the same upstream version (0.5.2.1): MDM_RT_VERSION for '
                                      'the app (window title, About, update check, exe version info)')
    ap.add_argument('--cargo-args', nargs=argparse.REMAINDER, default=[])
    a = ap.parse_args()
    below_normal()
    arch, t = a.arch, TRIPLE[a.arch]
    profile = {'thin': 'rt-thin', 'fat': 'release', 'dev': 'rt-dev'}[a.variant]
    pk = [PACKAGES[p] for p in a.packages.split(',')]
    os.makedirs(OUT, exist_ok=True)
    cfgpath = os.path.join(OUT, 'cargo-%s.toml' % arch)
    pgo = []
    if a.pgo != 'none':
        if a.variant != 'thin':
            sys.exit('--pgo needs --variant thin')
        if a.pgo == 'gen':
            pgo = ['-C', 'profile-generate=pgo-data']   # the folder if LLVM_PROFILE_FILE is not set (relative)
        elif a.pgo.startswith('use='):
            prof = os.path.abspath(a.pgo[4:])
            if not os.path.isfile(prof):
                sys.exit('no profile ' + prof)
            pgo = ['-C', 'profile-use=' + prof]
        else:
            sys.exit('--pgo: gen or use=<profdata>')
        log('PGO: ' + ' '.join(pgo))
    write_config(arch, cfgpath, prepare_patches(arch), pgo)
    tdir = os.path.join(TARGET_DIR, t, profile)
    if a.fresh and os.path.isdir(tdir):
        to_trash(tdir)
    cmd = [CARGO, 'build', '--config', cfgpath, '--profile', profile, '--target', t, '-j', str(a.jobs)]
    for p, _ in pk:
        cmd += ['-p', p]
    cmd += a.cargo_args
    lock = os.path.join(REPO, 'Cargo.lock')
    saved = open(lock, 'rb').read()
    log('cargo build %s %s (%s)' % (arch, a.variant, ', '.join(p for p, _ in pk)))
    t0 = time.time()
    try:
        env = build_env(arch)
        # rustc's incremental cache for quick rebuilds of a changed crate (dev, thin); not with fat LTO, and not
        # with PGO (a profile must meet code compiled from scratch, as counted)
        incremental = a.variant != 'fat' and a.pgo == 'none' and not a.no_incremental
        env['CARGO_INCREMENTAL'] = '1' if incremental else '0'
        env.pop('MDM_RT_VERSION', None)
        if a.version:
            env['MDM_RT_VERSION'] = a.version
            log('MDM_RT_VERSION=' + a.version)
        r = subprocess.run(cmd, cwd=REPO, env=env)
    finally:
        if open(lock, 'rb').read() != saved:
            open(lock, 'wb').write(saved)
            log('Cargo.lock put back')
    log('cargo exit %d after %.0f s' % (r.returncode, time.time() - t0))
    if r.returncode:
        sys.exit(r.returncode)
    dst = os.path.join(OUT, '%s-%s%s' % (arch, a.variant, '-pgogen' if a.pgo == 'gen' else ''))
    os.makedirs(dst, exist_ok=True)
    exes = []
    for _, exe in pk:
        for ext in ('.exe', '.pdb'):
            s = os.path.join(tdir, exe + ext)
            if os.path.isfile(s):
                shutil.copy2(s, os.path.join(dst, exe + ext))
        exes.append(os.path.join(dst, exe + '.exe'))
        log('%-38s %10d bytes' % (exe + '.exe', os.path.getsize(exes[-1])))
    if arch == 'arm32' and not a.no_check:
        rc = subprocess.run([sys.executable, '-I', os.path.join(PROJECT, 'tools', 'check-pe.py'),
                             os.path.join(RT, 'bin', 'llvm-readobj.exe'), DEVICE_DLLS] + exes).returncode
        if rc:
            sys.exit('check-pe failed')
    log('done: ' + dst)


if __name__ == '__main__':
    main()
