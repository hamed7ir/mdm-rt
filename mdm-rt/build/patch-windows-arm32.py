# MDM RT: make Microsoft's windows / windows-sys crates build for 32-bit Arm (thumbv7a-pc-windows-msvc).
#
# windows-rs has no ARM32 metadata. Where a type's layout differs between 32-bit and 64-bit Windows (almost always
# `#include <pshpack1.h>` or a different field order under `!_WIN64` in the SDK headers), the crates carry two
# definitions: `#[cfg(target_arch = "x86")]` and `#[cfg(any(target_arch = "aarch64", target_arch = "arm64ec",
# target_arch = "x86_64"))]`. On ARM32 neither applies, so the type is missing (WSADATA, NOTIFYICONDATAW,
# SHELLEXECUTEINFOW, ...). ARM32 is a 32-bit `!_WIN64` target with the same headers, packing and type sizes as
# x86, so its layout is the x86 one. This script adds `target_arch = "arm"` to exactly those x86 definitions:
# items that have an x86 variant AND one variant shared by all 64-bit CPUs. Items whose 64-bit side is split per
# CPU (CONTEXT, unwind and XSAVE structures) are CPU-specific and stay x86-only, as are items that exist only for
# x86 (the old 32-bit DbgHelp names).
#
# Usage: python -I patch-windows-arm32.py <crate source dir> <output dir>
# The output is a copy: unchanged files are hard links (or copies), changed files are written new. Prints the
# number of items made available on ARM32.
import os, re, shutil, sys

X86 = '#[cfg(target_arch = "x86")]'
ARM = '#[cfg(any(target_arch = "x86", target_arch = "arm"))]'
ALL64 = {'#[cfg(any(target_arch = "aarch64", target_arch = "arm64ec", target_arch = "x86_64"))]',
         '#[cfg(any(target_arch = "aarch64", target_arch = "x86_64"))]'}
NAME = [re.compile(p) for p in (
    r'\bfn\s+(\w+)',                                   # windows_link::link!(... fn Name(...)), pub fn, unsafe fn
    r'\bimpl(?:<[^>]*>)?\s+[\w:<>, ]+?\s+for\s+(\w+)',  # impl Trait for Name
    r'\bimpl(?:<[^>]*>)?\s+(\w+)',                     # impl Name
    r'\b(?:struct|union|enum|type|const|static|mod|trait)\s+(\w+)',
    r'\buse\s+[\w:]*?(\w+)\s*;',
)]


def item_name(line):
    for rx in NAME:
        m = rx.search(line)
        if m:
            return m.group(1)
    return None


def scan(lines):
    """[(index of a target_arch cfg line, its text, item name)]"""
    out = []
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith('#[cfg(') and 'target_arch' in s:
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('#['):
                j += 1
            if j < len(lines):
                out.append((i, s, item_name(lines[j])))
    return out


def patch_text(text):
    lines = text.split('\n')
    found = scan(lines)
    kinds = {}
    for _, cfg, name in found:
        if name is None:
            continue
        k = 'x86' if cfg == X86 else 'all64' if cfg in ALL64 else ('cpu64' if ('x86_64' in cfg or 'aarch64' in cfg) else 'other')
        kinds.setdefault(name, set()).add(k)
    n = 0
    for i, cfg, name in found:
        if cfg == X86 and name and kinds[name] >= {'x86', 'all64'} and 'cpu64' not in kinds[name]:
            lines[i] = lines[i].replace(X86, ARM)
            n += 1
    return '\n'.join(lines), n


def main(src, dst):
    if os.path.exists(dst):
        sys.exit('output exists: ' + dst)
    total = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        os.makedirs(os.path.join(dst, rel), exist_ok=True)
        for f in files:
            a, b = os.path.join(root, f), os.path.join(dst, rel, f)
            if f.endswith('.rs'):
                t = open(a, encoding='utf-8', newline='').read()
                if X86 in t:
                    t2, n = patch_text(t)
                    if n:
                        open(b, 'w', encoding='utf-8', newline='').write(t2)
                        total += n
                        continue
            try:
                os.link(a, b)
            except OSError:
                shutil.copy2(a, b)
    print('%s: %d items now also for ARM32' % (os.path.basename(src.rstrip('/\\')), total))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
