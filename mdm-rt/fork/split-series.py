# MDM RT: makes the patch series (one patch per change, like 7-Zip RT's) from the dev tree's uncommitted changes.
#
#   python -I mdm-rt\fork\split-series.py <dev tree> <clean clone> <series dir>
#
# <dev tree>     the working copy with every change (F:\mdm-rt\src), at upstream's release commit
# <clean clone>  a scratch clone at the same commit, no changes (made fresh for each run)
# <series dir>   gets NNNN-<topic>.patch and series.txt (patch <TAB> subject <TAB> body), for fork\make-fork.sh
#
# Each hunk of `git diff` (and each new file) is given a topic by the rules below; the topics are applied to the
# clean clone in order and each patch is re-made there with `git diff`, so every patch applies on the ones before
# it. At the end the clone must be byte-identical to the dev tree (outside mdm-rt/ and target/), else it stops.
import os, re, subprocess, sys

DEV, CLEAN, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

def venetium(p, h):
    """The Venetium change (topic 0007): all of ipc's browsers.rs and capture.rs, and the app's hunks naming it
    (settings.rs' capture list, its length line included; win32.rs' uninstall-entry lookup)."""
    return (p in ('crates/ipc/src/browsers.rs', 'crates/ipc/src/capture.rs')
            or (p in ('crates/app/src/settings.rs', 'crates/app/src/win32.rs')
                and ('Venetium' in h or 'BROWSERS: [&str;' in h)))


def tablet(p, h):
    """Topic 0009: the Tegra start-up tries (renderer.rs, MDM_ANGLE), the message when nothing draws, and stderr to
    logs\\stderr.log (the app's lib.rs, once main.rs, and win32.rs)."""
    return ((p == 'crates/app/src/renderer.rs' and ('MDM_ANGLE' in h or 'message_box' in h))
            or (p in ('crates/app/src/main.rs', 'crates/app/src/lib.rs') and 'stderr_to_log' in h)
            or (p == 'crates/app/src/win32.rs'
                and ('stderr_to_log' in h or 'message_box' in h or 'set_angle_platform' in h)))


def looked(p, h):
    """Topic 0010: the video window's look-up kept for the download (videodlg.rs: its InfoSlot handed over as
    upstream's Preloaded; video.rs: the run's note that it took it)."""
    return p == 'crates/app/src/videodlg.rs' or (p == 'crates/tools/src/video.rs' and 'look-up already made' in h)


# (topic id, subject, body, rule). A rule gets (path, hunk text) and says yes or no; the first topic saying yes
# takes the hunk. Paths are git's (forward slashes).
TOPICS = [
    ('0001-arm32-build', 'build for 32-bit arm windows (windows rt 8.1, windows 10 arm32)',
     'thumbv7a-pc-windows-msvc: no direct3d 12 renderer (wgpu) on arm32 (windows rt has no d3d12 and its tegra/'
     'adreno chips stop at feature level 9_x; opengl es through angle draws there, the default where wgpu isn\'t '
     'built), subsystem 6.02 for arm32 programs, and windows 10\'s per-monitor dpi functions (getdpiforwindow, '
     'adjustwindowrectexfordpi, getsystemmetricsfordpi, getdpiforsystem) looked up at run time with windows 8.1 '
     'fallbacks (a program importing them does not start on rt 8.1). --cfg mdm_rt_angle draws the same way on '
     'x86/x64, as a test build of the arm32 path.',
     lambda p, h: (p in ('crates/app/Cargo.toml', 'crates/app/src/renderer.rs', 'Cargo.toml') and not tablet(p, h))
     or (p == 'crates/app/build.rs' and 'rt_version' not in h)
     or (p == 'crates/app/src/win32.rs' and re.search(r'dpi10|32-bit Windows|packed\(1\)|SetWindowLongPtrW|'
                                                       r'SWP_NOZORDER, SetWindowPos', h))),
    ('0002-bundled-helpers', 'helpers: use the ones bundled beside the program; no x86/x64 downloads on arm32',
     'mdm rt\'s arm32 setup installs yt-dlp (a launcher running yt-dlp\'s own zipapp with kodi rt\'s arm32 '
     'python), ffmpeg and quickjs in <program folder>\\helpers. the tools crate finds them after the person\'s '
     'chosen program and mdm\'s own installs, never downloads helper builds that do not run on 32-bit arm windows, '
     'and counts the quickjs beside the bundled yt-dlp as its javascript runtime, as upstream counts one beside its '
     'own yt-dlp (youtube needs one). a video look-up may take 4 minutes there instead of 90 s (a surface rt\'s '
     'first youtube look-up).',
     lambda p, h: p.startswith('crates/tools/') and p != 'crates/tools/src/update.rs' and not looked(p, h)),
    ('0003-mdm-rt-identity', 'mdm rt identity: its own name, data folder, registry names and repository',
     'mdm rt runs beside an upstream mister download manager: its own data folder (%appdata%\\mdm-rt: list, '
     'settings, command channel), window title, startup entry, .torrent and magnet progids and default apps name, '
     'the running mutex, credential manager names and installer key (hkcu\\software\\mdm rt). problem reports, crash reports and the update check go to '
     'github.com/hamed7ir/mdm-rt. about says what mdm rt is (not translated, as 7-zip rt\'s notice). its version '
     'is mdm rt\'s own release number (1.1: MDM_RT_VERSION, build.py --version), and the '
     'exe\'s version info names mdm rt.',
     lambda p, h: (p in ('crates/app/src/main.rs', 'crates/app/src/lib.rs', 'crates/app/src/help.rs',
                         'crates/app/src/secrets.rs', 'crates/ipc/src/lib.rs', 'crates/crash/src/github.rs')
                   and 'digest:' not in h
                   and not tablet(p, h))
     or (p == 'crates/app/src/win32.rs' and re.search(r'"MDM RT"|MDMRT\.|MDM%20RT|Software\\MDM RT"', h)
         and 'take_install_theme' not in h)
     or (p == 'crates/app/build.rs' and 'rt_version' in h)),
    ('0004-rt-themes', 'rt themes: 7-zip rt\'s dark look, kodi rt\'s purple the default',
     'eight built-in themes made from 7-zip rt\'s dark theme (kodi rt\'s purple palette and 7-zip rt\'s other '
     'accent colours, mdm-rt/branding/make-themes.py), first in view > theme. a new install starts dark in rt '
     'purple; setup\'s colour choice is handed over once (hkcu\\software\\mdm rt\\installtheme), as upstream\'s '
     'installer hands over its language.',
     lambda p, h: (p in ('crates/app/src/palette.rs', 'crates/app/src/app.rs', 'crates/app/src/settings.rs')
                   and not venetium(p, h) and not looked(p, h))
     or p.startswith('crates/app/assets/themes/rt-')
     or (p == 'crates/app/src/win32.rs' and 'take_install_theme' in h)),
    ('0005-purple-icon', 'purple icon: mister download manager\'s icon in kodi rt\'s purple',
     'the app icon (window, taskbar, notification area, about, the exe) recoloured by mdm-rt/branding/make-icons.py: '
     'the green arrow, hat band and pixel trail in kodi rt\'s purple, the globe a deeper violet, black and white kept, '
     'as 7-zip rt\'s icon is purple.',
     lambda p, h: p.startswith('crates/app/assets/icons/app/')),
    ('0006-update-check', 'update check: mdm rt\'s releases, checked against github\'s sha-256 digests',
     'help > check for updates and update now use github.com/hamed7ir/mdm-rt: an installed copy is the one with '
     'mdm rt\'s uninstall.exe beside it, its release file is MDM-RT-Setup-<version>-<arm32|x64>.exe, and as mdm rt\'s '
     'releases carry no signature by upstream\'s key, the checksum list must match the sha-256 github shows for it '
     'and the setup both its line there and its own github digest (as 7-zip rt checks its updates). the setup is run '
     'with --silent <folder> --keep --relaunch.',
     lambda p, h: p in ('crates/tools/src/update.rs', 'crates/app/src/update.rs')
     or (p == 'crates/app/src/help.rs' and 'digest:' in h)),
    ('0007-venetium', 'venetium: found, offered the extension first, and named in captured downloads',
     'venetium (github.com/hamed7ir/venetium) is the chromium of windows rt 8.1 and windows 10 arm32. mdm finds it '
     'by its program (venetium.exe) and by its uninstall entry (its setup registers nothing else), lists it first in '
     '"add mister download manager to your browser" (the chrome web store, as for chrome), names the downloads it '
     'hands over "venetium" (it sends that client-hints brand) and lists it in options\' capture list. its native '
     'messaging key is chromium\'s, which mdm already registers.',
     venetium),
    ('0008-touch-menus', 'touch screens: a tap chooses a menu item, press-and-hold opens the context menu',
     'on a touch screen egui ends the pointer in the same frame the finger lifts (pointergone), and a menu item is '
     'chosen on the release under the pointer, so no menu item could be chosen by touch: on the windows rt tablets '
     'view > theme or downloads > resume did nothing. an item now takes the release\'s place (egui\'s interact_pos, '
     'the touch\'s place), and a tap on a submenu\'s entry opens it. a mouse works as before. press-and-hold (the '
     'download list\'s menu, every right-click menu) is egui\'s secondary click for a touch held still, timed with '
     'the click\'s limit, which mdm lifts so that a held mouse button stays a click: while the pointer is a finger '
     'or a pen, egui\'s 0.8 s apply again, with a finger\'s leeway (10 points instead of 6).',
     lambda p, h: p in ('crates/app/src/chrome.rs', 'crates/app/src/theme.rs')),
    ('0009-tablet-start', 'tablets: start-up tries on tegra, a message when nothing draws, and crash traces',
     'on a surface rt (tegra 3) angle\'s default display found no window config on about every second start, and mdm '
     'was gone without a word: opengl es is the only way to draw there, so it is tried again with angle told '
     'direct3d 9, then 11 (mdm_angle), and if nothing draws a message says so. what rust prints when it aborts (a '
     'failed allocation, a panic\'s message) goes to logs\\stderr.log: windows rt 8.1 and windows 10 before 1803 '
     'can\'t run the crash monitor (minidumper needs af_unix sockets).',
     tablet),
    ('0010-video-look-up-once', 'videos: the download starts from the video window\'s look-up',
     'mdm looked a video page up twice: for the video window (yt-dlp -J: its qualities) and again when the download '
     'started, and on a surface rt each yt-dlp look-up takes a minute or more. the window now keeps yt-dlp\'s answer '
     'and hands it to the download as upstream\'s preloaded look-up (made for the browser\'s quality menu), which '
     'takes it for a download started now within ten minutes when the page offers the quality chosen; the run\'s '
     'log says so. a part of a video, the video a page declares, an address edited after the look-up, a download '
     'started later and a later try look the page up again.',
     looked),
]


def git(cwd, *args, check=True, capture=True):
    r = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.quotepath=false'] + list(args), cwd=cwd,
                       capture_output=capture, check=False)
    if check and r.returncode:
        sys.exit('git %s failed in %s:\n%s' % (' '.join(args), cwd, r.stderr.decode('utf-8', 'replace')))
    return r.stdout


def split(diff):
    """[(path, header, [hunk, ...])] from a unified diff (bytes, decoded as UTF-8 surrogateescape)."""
    files = []
    for part in re.split(r'(?m)^(?=diff --git )', diff):
        if not part.startswith('diff --git '):
            continue
        m = re.match(r'diff --git a/(\S+) b/(\S+)', part)
        path = m.group(2)
        i = part.find('\n@@')
        header, body = (part, '') if i < 0 else (part[:i + 1], part[i + 1:])
        hunks = re.split(r'(?m)^(?=@@ )', body)
        files.append((path, header, [h for h in hunks if h.startswith('@@ ')]))
    return files


def main():
    if git(CLEAN, 'status', '--porcelain').strip():
        sys.exit(CLEAN + ' has changes: it must be a fresh clone')
    head_dev, head_clean = git(DEV, 'rev-parse', 'HEAD').strip(), git(CLEAN, 'rev-parse', 'HEAD').strip()
    if head_dev != head_clean:
        sys.exit('the two trees are at different commits')
    # new files of the dev tree (outside mdm-rt/), shown as additions: intent-to-add in a throwaway index
    env_index = os.path.join(DEV, '.git', 'mdmrt-split-index')
    env = dict(os.environ, GIT_INDEX_FILE=env_index)
    subprocess.run(['git', 'read-tree', 'HEAD'], cwd=DEV, env=env, check=True)
    new = [l for l in git(DEV, 'ls-files', '--others', '--exclude-standard').decode().splitlines()
           if not l.startswith('mdm-rt/')]
    if new:
        subprocess.run(['git', 'add', '-N', '--'] + new, cwd=DEV, env=env, check=True)
    diff = subprocess.run(['git', '-c', 'core.autocrlf=false', 'diff', '-U3', '--binary', '--', '.',
                           ':(exclude)mdm-rt', ':(exclude)Cargo.lock'], cwd=DEV, env=env, capture_output=True,
                          check=True).stdout.decode('utf-8', 'surrogateescape')
    os.remove(env_index)
    files = split(diff)
    per_topic = {t[0]: [] for t in TOPICS}
    for path, header, hunks in files:
        groups = {}
        for h in (hunks or ['']):
            for tid, _, _, rule in TOPICS:
                if rule(path, h):
                    groups.setdefault(tid, []).append(h)
                    break
            else:
                sys.exit('no topic for a hunk of %s:\n%s' % (path, h[:400]))
        for tid, hs in groups.items():
            per_topic[tid].append(header + ''.join(hs))
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for tid, subject, body, _ in TOPICS:
        if not per_topic[tid]:
            continue
        tmp = os.path.join(OUT, tid + '.raw')
        open(tmp, 'w', encoding='utf-8', errors='surrogateescape', newline='').write(''.join(per_topic[tid]))
        git(CLEAN, 'apply', '--index', '--whitespace=nowarn', tmp)
        os.remove(tmp)
        patch = git(CLEAN, 'diff', '--cached', '--binary', 'HEAD')
        # the patch of this step only: against the index before it (the previous steps are committed below)
        open(os.path.join(OUT, tid + '.patch'), 'wb').write(patch)
        git(CLEAN, '-c', 'user.name=series', '-c', 'user.email=series@localhost', 'commit', '-q', '-m', tid)
        rows.append('%s.patch\t%s\t%s' % (tid, subject, body))
        print('%-24s %6d lines' % (tid, patch.count(b'\n')))
    open(os.path.join(OUT, 'series.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(rows) + '\n')
    # the upstream commit the series applies to (make-fork.sh's default BASE)
    open(os.path.join(OUT, 'base.txt'), 'w', encoding='utf-8', newline='\n').write(head_dev.decode() + '\n')
    # the clone must now equal the dev tree: the same files (tracked + the new ones), byte for byte
    clean_files = set(git(CLEAN, 'ls-files').decode('utf-8').splitlines())
    dev_files = set(git(DEV, 'ls-files').decode('utf-8').splitlines()) | set(new)
    bad = sorted(clean_files ^ dev_files)
    for f in sorted(dev_files & clean_files):
        if f == 'Cargo.lock':
            continue
        if open(os.path.join(DEV, f), 'rb').read() != open(os.path.join(CLEAN, f), 'rb').read():
            bad.append(f)
    if bad:
        sys.exit('the series does not reproduce the dev tree:\n' + '\n'.join(bad[:40]))
    print('series OK: %d patches in %s, the clone equals the dev tree' % (len(rows), OUT))


if __name__ == '__main__':
    main()
