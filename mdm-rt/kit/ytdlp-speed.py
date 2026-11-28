# MDM RT kit: where a YouTube look-up's time goes on this tablet. Runs the helpers' yt-dlp as MDM does (-J, its
# JavaScript runtime QuickJS) in several variants, each twice (the first with an empty cache, as a first look-up,
# then as later ones), and stamps every line of yt-dlp's verbose log with the seconds since the run began; the
# summary gives each run's time and what it found (formats, best height). Run by ytdlp-speed.cmd with the helpers'
# own python.exe:  python.exe -I ytdlp-speed.py <helpers folder> <url> <results folder> [proxy]
import json, os, subprocess, sys, threading, time

helpers, url, results = sys.argv[1], sys.argv[2], sys.argv[3]
proxy = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
ytdlp = os.path.join(helpers, 'yt-dlp.exe')
qjs = os.path.join(helpers, 'qjs.exe')
os.makedirs(results, exist_ok=True)
base = ['-v', '-J', '--no-playlist', '--flat-playlist', '--playlist-items', '1:1', '--js-runtimes', 'quickjs:' + qjs]
if proxy:
    base += ['--proxy', proxy]
variants = [
    ('1-as-mdm', []),
    ('2-skip-translated-subs', ['--extractor-args', 'youtube:skip=translated_subs']),
    ('3-skip-webpage', ['--extractor-args', 'youtube:player_skip=webpage']),
    ('4-one-client-visionos', ['--extractor-args', 'youtube:player_client=visionos']),
    ('5-both-skips', ['--extractor-args', 'youtube:skip=translated_subs;player_skip=webpage']),
]
summary = open(os.path.join(results, 'summary.txt'), 'w', encoding='utf-8')


def say(line):
    print(line)
    summary.write(line + '\n')
    summary.flush()


say('yt-dlp speed on %s for %s%s' % (os.environ.get('COMPUTERNAME', '?'), url, ' via ' + proxy if proxy else ''))
for name, extra in variants:
    for pass_ in ('first', 'again'):
        cache = os.path.join(results, 'cache-' + name)
        log = open(os.path.join(results, '%s-%s.log' % (name, pass_)), 'w', encoding='utf-8')
        cmd = [ytdlp] + base + ['--cache-dir', cache] + extra + [url]
        t0 = time.perf_counter()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = []
        reader = threading.Thread(target=lambda: out.append(p.stdout.read()))
        reader.start()
        for raw in p.stderr:
            log.write('%7.2f  %s\n' % (time.perf_counter() - t0, raw.decode('utf-8', 'replace').rstrip()))
        p.wait()
        reader.join()
        took = time.perf_counter() - t0
        log.close()
        info = {}
        try:
            info = json.loads(out[0] or b'null') or {}
        except Exception:
            pass
        formats = info.get('formats') or []
        best = max([f.get('height') or 0 for f in formats] or [0])
        subs = len(info.get('automatic_captions') or {})
        say('%-26s %-5s %7.1f s  exit %d  formats %3d  best %4dp  auto-caption languages %3d  json %4d KB' % (
            name, pass_, took, p.returncode, len(formats), best, subs, len(out[0] or b'') // 1024))
summary.close()
