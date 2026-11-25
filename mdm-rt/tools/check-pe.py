# MDM RT: release checks for the ARM32 programs (from 7-Zip RT's tools/check-pe.py, which came from kodi-rt's
# scripts/check-imports.py). For every image:
#   - machine is ARMNT (0x1C4)
#   - PE subsystem version 6.02 (runs on Windows RT 8.0/8.1 and Windows 10 ARM32)
#   - static CRT: no vcruntime*/msvcp*/ucrtbase/api-ms-win-crt imports
#   - every imported function (normal and delay-load) is exported by the DEVICE's copy of that DLL (Surface RT,
#     Windows RT 8.1 System32), so nothing needs a Windows 10 API.
#   - API-set imports (Rust's std uses api-ms-win-core-synch-l1-2-0 for WaitOnAddress) are resolved through the
#     device's own apisetschema.dll (schema v4 on 8.1): the set must exist on RT 8.1 by that exact name, and its
#     host DLL must export every imported function. 7-Zip RT refused API sets outright; Venetium (device-proven on
#     8.1) delay-loads the same synch set, so resolving them is the right test.
#   - a DLL that is one of the checked images (a bundled helper's own DLLs: ffmpeg's avcodec-NN.dll) is checked
#     against that image's exports instead.
# Usage: python -I check-pe.py [--subsystem 6.00] <llvm-readobj.exe> <device dll dir> <image> ...
#   --subsystem 6.00: accept that version too (third-party builds device-verified at 6.00: python-rt, ffmpeg-rt).
# Exit 0 = all pass.
import os, re, struct, subprocess, sys

args = sys.argv[1:]
subsystems = {'6.02'}
if args[:1] == ['--subsystem']:
    subsystems.add(args[1])
    args = args[2:]
readobj, devdir, images = args[0], args[1], args[2:]
dev = {f.lower(): os.path.join(devdir, f) for f in os.listdir(devdir)}
dev.update({os.path.basename(i).lower(): i for i in images})   # the checked images' own DLLs
cache = {}


def apiset_schema():
    """{'ms-win-core-synch-l1-2-0': 'kernelbase.dll', ...} from the device's apisetschema.dll (v4, 8.1)."""
    path = dev.get('apisetschema.dll')
    if path is None:
        return {}
    data = open(path, 'rb').read()
    out = subprocess.run([readobj, '--sections', path], capture_output=True, text=True).stdout
    m = re.search(r'Name: \.apiset .*?RawDataSize: (\d+)\s+PointerToRawData: (0x[0-9A-Fa-f]+)', out, re.S)
    if not m:
        return {}
    size, off = int(m.group(1)), int(m.group(2), 16)
    s = data[off:off + size]
    version, _, _, count = struct.unpack_from('<IIII', s, 0)
    if version != 4:
        sys.exit('apisetschema.dll: schema version %d, this script reads version 4 (Windows 8.1)' % version)
    text = lambda o, n: s[o:o + n].decode('utf-16-le')
    schema = {}
    for i in range(count):
        _, no, nl, _, _, do = struct.unpack_from('<IIIIII', s, 16 + i * 24)
        _, vc = struct.unpack_from('<II', s, do)
        hosts = []
        for j in range(vc):
            _, _, _, vo, vl = struct.unpack_from('<IIIII', s, do + 8 + j * 20)
            hosts.append(text(vo, vl))
        schema[text(no, nl).lower()] = [h for h in hosts if h]
    return schema


SCHEMA = apiset_schema()


def exports(dll):
    key = dll.lower()
    if key not in cache:
        p = dev.get(key)
        if p is None:
            cache[key] = None
        else:
            out = subprocess.run([readobj, '--coff-exports', p], capture_output=True, text=True).stdout
            cache[key] = (set(re.findall(r'^\s*Name: (\S+)', out, re.M)) |
                          {'#' + o for o in re.findall(r'^\s*Ordinal: (\d+)', out, re.M)})
    return cache[key]


rc = 0
for img in images:
    hdr = subprocess.run([readobj, '--file-headers', img], capture_output=True, text=True).stdout
    def field(name):
        m = re.search(r'^\s*' + name + r': (.*)$', hdr, re.M)
        return m.group(1).strip() if m else '?'
    machine = field('Machine')
    subsys = field('MajorSubsystemVersion') + '.' + field('MinorSubsystemVersion').zfill(2)
    problems = []
    if 'ARMNT' not in machine:
        problems.append('machine ' + machine)
    if subsys not in subsystems:
        problems.append('subsystem version ' + subsys + ' (want ' + ' or '.join(sorted(subsystems)) + ')')
    out = subprocess.run([readobj, '--coff-imports', img], capture_output=True, text=True).stdout
    cur, imports, prev = None, {}, ''
    for line in out.splitlines():
        m = re.match(r'^\s*Name: (\S+)$', line)
        if m and 'Import {' in prev:           # "Import {" and "DelayImport {"
            cur = m.group(1)
            imports.setdefault(cur, [])
        m2 = re.match(r'^\s*Symbol: (\S*) \((\d+)\)', line)
        if m2 and cur:
            imports[cur].append(m2.group(1) if m2.group(1) else '#' + m2.group(2))
        prev = line
    lines = []
    for dll, syms in imports.items():
        d = dll.lower()
        if re.match(r'^(vcruntime|msvcp|ucrtbase|api-ms-win-crt|concrt)', d):
            problems.append('dynamic CRT import ' + dll)
            continue
        shown = dll
        if re.match(r'^(api|ext)-ms-', d):
            base = d[:-4] if d.endswith('.dll') else d
            hosts = SCHEMA.get(base[4:]) or SCHEMA.get(base)
            if not hosts:
                problems.append('API set ' + dll + ' does not exist on RT 8.1')
                continue
            dll, shown = hosts[0], '%s -> %s' % (dll, hosts[0])
        ex = exports(dll)
        if ex is None:
            problems.append(dll + ' is not in the device DLL folder')
            continue
        missing = [s for s in syms if s not in ex]
        lines.append('   %-14s %3d functions%s' % (shown, len(syms), ('; MISSING on RT 8.1: ' + ', '.join(missing)) if missing else ''))
        if missing:
            problems.append(dll + ': ' + ', '.join(missing))
    print('%s %s  [%s, subsystem %s]' % ('FAIL' if problems else 'ok  ', img, machine.split()[0], subsys))
    for l in lines:
        print(l)
    for p in problems:
        print('   PROBLEM: ' + p)
    if problems:
        rc = 1
sys.exit(rc)
