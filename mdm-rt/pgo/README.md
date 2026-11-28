# pgo/: the ARM32 release's profiles

MDM RT 1.1's ARM32 release is built with these profiles (counts from real sessions on a Surface 2: Tegra 4,
Windows 10 ARM32 build 15035), made with `llvm-profdata merge` of llvm-rt 2.4 (the LLVM of rustc-rt24 and clang-cl):

| file | bytes | sha256 | for |
|---|---|---|---|
| `mdm-rt-arm32.profdata` | 51,133,888 | `a57141a03d60e25b5f22a253b6f56333639be3b3b6c52c6865513eb56e6e4d81` | MDM RT itself (1.1) |
| `qjs-arm32.profdata` | 355,200 | `ec09b5f050ea381db014f092d6d198d63e7f0175020d2410617d01d115efeed0` | QuickJS (`qjs.exe`, 1.1) |
| `ffmpeg-arm32.profdata` | 45,477,664 | `8d42c5782082bf35e36d18edcb7dc86f5636ce2978e27775d6d1802a6798bcbd` | ffmpeg, LAME and Opus (0.5.2's profile) |

    python -I mdm-rt\build\build.py arm32 --variant thin --version 1.1 --no-incremental --pgo use=mdm-rt\pgo\mdm-rt-arm32.profdata
    python -I mdm-rt\helpers\build-helpers.py arm32 <out> --qjs-pgo use=mdm-rt\pgo\qjs-arm32.profdata --ffmpeg <dist-use>\bin --ffmpeg-licenses <dist-use>\licenses
    python -I mdm-rt\helpers\ffmpeg\build-lame.py arm32 <lame source> <lame-use> --pgo use=mdm-rt\pgo\ffmpeg-arm32.profdata
    python -I mdm-rt\helpers\ffmpeg\build-opus.py arm32 <opus source> <opus-use> --pgo use=mdm-rt\pgo\ffmpeg-arm32.profdata
    bash mdm-rt/helpers/ffmpeg/build-ffmpeg.sh arm32 <ffmpeg source> <lame-use> <opus-use> <build> <dist-use> use=mdm-rt/pgo/ffmpeg-arm32.profdata

A function is found by its name and the hash of its shape. A profile fits the source it was counted on: a function
changed since then goes without counts (the build log names the mismatches), and one renamed is not found at all.
Rust's names carry each crate's build hash, which changes with the crate's version or source, so a profile does not
survive a move to newer upstream code: 0.5.2's profile fitted only 12 % of 1.1's functions (MDM's code moved into a
library, egui and many other crates are newer), and 1.1 got counts of its own.

## MDM RT and QuickJS (2026-11-27, PGO kit 3)

The counting build of the 1.1 source (`build.py --pgo gen`, `build-helpers.py --qjs-pgo gen`) for about 40 minutes:
https downloads (pause, resume, remove, delete with the file), YouTube videos and audio only, adding a torrent, the windows,
menus and dialogs, then File > Exit.

- `mdm-rt-arm32.profdata`: `misterdownloadmanager.exe`, the main process (10.9 billion counts over 173,182
  functions) and its crash monitor's start-up (the monitor needs AF_UNIX sockets, which Windows 10 15035 doesn't
  have). Every function of the counting build is found in it.
- `qjs-arm32.profdata`: `qjs.exe` x9, four of them YouTube's JavaScript challenges (3.6 billion counts each), the
  rest yt-dlp's checks. QuickJS's first profile: in 0.5.2's session yt-dlp needed no challenge.

## ffmpeg, LAME and Opus (2026-11-24, PGO kit 2)

0.5.2's merged profile (its file `mdm-rt-arm32.profdata` then): ffmpeg, LAME and Opus haven't changed since, so it
still fits them, and 1.1's helpers carry the same PGO build of them. PGO kit 2 ran on the same Surface 2 for about
75 minutes (downloads, YouTube at 720p and as audio only: MP3 through LAME from AAC sound, Opus, a torrent); the file
merges all 38 count files of that session (MDM RT 0.5.2's records in it are unused now): `ffmpeg.exe` x17 (four
real jobs: MP3, Opus, two H.264 merges; the rest yt-dlp's version checks), `ffprobe.exe` x13, the 0.5.2 programs.

## Making them again

Build the kit (`kit/make-kit.py pgo`, [RECIPE.md](../RECIPE.md) "PGO (ARM32)"), run it on a tablet as its README says,
then merge each program's count files (`llvm-profdata show <file>` tells them apart by their number of functions):

    llvm-profdata merge -o mdm-rt\pgo\mdm-rt-arm32.profdata <MDM RT's count files>
    llvm-profdata merge -o mdm-rt\pgo\qjs-arm32.profdata <qjs.exe's count files>
