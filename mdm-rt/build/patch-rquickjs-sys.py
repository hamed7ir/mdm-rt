# MDM RT: rquickjs-sys (QuickJS, used by mdm-engine for proxy auto-config scripts) ships pre-generated bindgen
# bindings per target and none for thumbv7a-pc-windows-msvc (or i686-pc-windows-msvc). This makes a copy of the
# crate with those files,
# derived from its armv7-unknown-linux-gnueabihf bindings:
#   - 32-bit Arm on Linux (AAPCS, hard float) and on Windows have the same type sizes (int/long/size_t/pointers
#     32 bits) and the same 8-byte alignment of 64-bit members, so every struct layout is the same; the bindings'
#     own size/alignment/offset asserts check this when the crate compiles.
#   - the one OS difference is C enums: MSVC makes every enum `int`, GCC makes one with no negative values
#     `unsigned int`. The x86_64 Linux and Windows bindings of the same version differ exactly there (and in
#     size_t, which is 32 bits on both 32-bit OSes): JSTypedArrayEnum, JSPromiseHookType, JSCFunctionEnum and the
#     atom enum become c_int.
# Usage: python -I patch-rquickjs-sys.py <crate source dir> <output dir>
import os, re, shutil, sys

ENUMS = ('JSTypedArrayEnum', 'JSPromiseHookType', 'JSCFunctionEnum')


def main(src, dst):
    if os.path.exists(dst):
        sys.exit('output exists: ' + dst)
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            a, b = os.path.join(root, f), os.path.join(dst, rel, f)
            try:
                os.link(a, b)
            except OSError:
                shutil.copy2(a, b)
    bdir = os.path.join(dst, 'src', 'bindings')
    t = open(os.path.join(bdir, 'armv7-unknown-linux-gnueabihf.rs'), encoding='utf-8', newline='').read()
    n = 0
    for e in ENUMS:
        t, k = re.subn(r'^(pub type %s = ::core::ffi::)c_uint;' % e, r'\1c_int;', t, flags=re.M)
        n += k
    # the atom enum: the anonymous enum whose first constant is __JS_ATOM_NULL
    m = re.search(r'^pub const __JS_ATOM_NULL: (_bindgen_ty_\d+) = 0;', t, re.M)
    if not m:
        sys.exit('no atom enum in the armv7 bindings')
    t, k = re.subn(r'^(pub type %s = ::core::ffi::)c_uint;' % m.group(1), r'\1c_int;', t, flags=re.M)
    n += k
    if n != 4:
        sys.exit('expected 4 enum typedefs, changed %d: the bindings changed, check this script' % n)
    head = ('/* MDM RT: made by mdm-rt/build/patch-rquickjs-sys.py from armv7-unknown-linux-gnueabihf.rs '
            '(MSVC enums are int) */\n')
    # The same file serves i686-pc-windows-msvc (MDM RT's x86 test build): 32-bit MSVC on x86 also aligns 64-bit
    # struct members to 8 bytes (unlike i686 Linux), so the layouts match; the asserts check it there too.
    for target in ('thumbv7a-pc-windows-msvc', 'i686-pc-windows-msvc'):
        open(os.path.join(bdir, target + '.rs'), 'w', encoding='utf-8', newline='').write(head + t)
    print('rquickjs-sys: thumbv7a/i686-pc-windows-msvc bindings written (%d enum typedefs made int)' % n)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
