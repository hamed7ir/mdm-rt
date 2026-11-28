# MDM RT: how much of an old PGO profile fits a new build? Compares the functions of a counting (-Cprofile-generate)
# Windows program (its .lprfn names and .lprfd records: name MD5 + control-flow hash) with an indexed .profdata
# (llvm-profdata show --all-functions --counts). A function's counts are used only when its name AND hash match.
#   python -I pgo-fit.py <counting exe> <old .profdata> [llvm-profdata.exe]
import collections
import hashlib
import struct
import subprocess
import sys
import zlib

exe, prof = sys.argv[1], sys.argv[2]
profdata = sys.argv[3] if len(sys.argv) > 3 else r'F:\cr\rt24-cr\bin\llvm-profdata.exe'


def sections(path):
    b = open(path, 'rb').read()
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    assert b[pe:pe + 4] == b'PE\0\0'
    nsec = struct.unpack_from('<H', b, pe + 6)[0]
    opt = struct.unpack_from('<H', b, pe + 20)[0]
    out = {}
    for i in range(nsec):
        o = pe + 24 + opt + 40 * i
        name = b[o:o + 8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, va, rsize, raw = struct.unpack_from('<IIII', b, o + 8)
        out[name] = b[raw:raw + min(vsize, rsize)]
    return out


def uleb(b, i):
    v = s = 0
    while True:
        c = b[i]
        i += 1
        v |= (c & 0x7f) << s
        s += 7
        if c < 0x80:
            return v, i


def names(blob):
    out, i = [], 0
    while i < len(blob):
        if blob[i] == 0:                     # padding between object files' contributions (a length is never 0)
            i += 1
            continue
        ulen, i = uleb(blob, i)
        clen, i = uleb(blob, i)
        if clen:
            data = zlib.decompress(blob[i:i + clen])
            i += clen
        else:
            data = blob[i:i + ulen]
            i += ulen
        out += data.split(b'\x01')
    return [n.decode('utf-8', 'replace') for n in out if n]


def md5low(name):
    return struct.unpack('<Q', hashlib.md5(name.encode('utf-8')).digest()[:8])[0]


sec = sections(exe)
print('sections:', ', '.join(k for k in sec if k.startswith('.lprf')))
new_names = names(sec['.lprfn'])
by_ref = {md5low(n): n for n in new_names}
# The records (u64 name MD5, u64 control-flow hash, 4 x u32 pointers, u32 counters, ...: 48 bytes on 32-bit) are
# in .lprfd, or merged into .data by the linker: found by their name MD5s, 8-byte aligned.
d = sec.get('.lprfd') or sec['.data']
recs, bad, last, strides = {}, 0, None, collections.Counter()
for o in range(0, len(d) - 47, 8):
    ref = struct.unpack_from('<Q', d, o)[0]
    if ref in by_ref:
        recs[ref] = (struct.unpack_from('<Q', d, o + 8)[0], struct.unpack_from('<I', d, o + 32)[0])
        if last is not None:
            strides[o - last] += 1
        last = o
print('record strides (48 expected):', strides.most_common(3))
print('new build: %d names, %d records (%d records without a name: layout check)' % (len(new_names), len(recs), bad))

old = {}
cur = None
txt = subprocess.run([profdata, 'show', '--all-functions', '--counts', prof], capture_output=True, text=True,
                     encoding='utf-8', errors='replace').stdout
for line in txt.splitlines():
    if line.startswith('  ') and not line.startswith('    ') and line.endswith(':'):
        cur = line[2:-1]
        old[cur] = [None, 0]
    elif cur and line.startswith('    Hash: '):
        old[cur][0] = int(line.split(':', 1)[1], 16)
    elif cur and line.startswith('    Block counts: ['):
        old[cur][1] = sum(int(x) for x in line.split('[', 1)[1].rstrip(']').split(',') if x.strip())
total = sum(w for _, w in old.values())
state = collections.Counter()
weight = collections.Counter()
for name, (h, w) in old.items():
    r = recs.get(md5low(name))
    s = 'gone (name not in the new build)' if r is None else ('fits' if r[0] == h else 'changed (hash differs)')
    state[s] += 1
    weight[s] += w
print('old profile: %d functions, total count %d' % (len(old), total))
for s in ('fits', 'changed (hash differs)', 'gone (name not in the new build)'):
    print('  %-34s %7d functions  %6.2f %% of the counted work' % (s, state[s], 100.0 * weight[s] / max(total, 1)))
fit_new = sum(1 for ref, (h, _) in recs.items() if by_ref.get(ref) in old and old[by_ref[ref]][0] == h)
print('new build: %d of %d functions get counts from the old profile (%.1f %%)' % (fit_new, len(recs),
                                                                                   100.0 * fit_new / max(len(recs), 1)))


def crate(n):
    s = n.split(';')[-1]
    return s[:90]


print('the old profile\'s 15 busiest functions:')
for name, (h, w) in sorted(old.items(), key=lambda kv: -kv[1][1])[:15]:
    r = recs.get(md5low(name))
    s = 'gone' if r is None else ('fits' if r[0] == h else 'changed')
    print('  %-7s %5.2f %%  %s' % (s, 100.0 * w / total, crate(name)))
