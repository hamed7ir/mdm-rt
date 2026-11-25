# pgo/: the ARM32 release's profile

`mdm-rt-arm32.profdata` (45,477,664 bytes, sha256 `8d42c5782082bf35e36d18edcb7dc86f5636ce2978e27775d6d1802a6798bcbd`)
is the profile MDM RT 0.5.2's ARM32 release is built with:

    python -I mdm-rt\build\build.py arm32 --variant thin --pgo use=mdm-rt\pgo\mdm-rt-arm32.profdata
    python -I mdm-rt\helpers\ffmpeg\build-lame.py arm32 <lame source> <lame-use> --pgo use=<profdata>
    python -I mdm-rt\helpers\ffmpeg\build-opus.py arm32 <opus source> <opus-use> --pgo use=<profdata>
    bash mdm-rt/helpers/ffmpeg/build-ffmpeg.sh arm32 <ffmpeg source> <lame-use> <opus-use> <build> <dist-use> use=<profdata>

One merged profile serves all of them: a function is found by its name and the hash of its shape, so the records of
different programs sit side by side.

## How it was made (2026-11-24)

PGO kit 2: the counting builds of the release's source (`build.py --pgo gen`, ffmpeg, LAME and Opus `gen`,
`build-helpers.py --qjs-pgo gen`) on a Surface 2 (Tegra 4, Windows 10 ARM32 build 15035) for about 75 minutes:
https downloads (pause, resume, remove), YouTube videos at 720p and as audio only (MP3 through LAME from AAC sound,
Opus), a torrent, the windows and menus, then File > Exit. Then `llvm-profdata merge` (llvm-rt 2.4, the LLVM of
rustc-rt24 and clang-cl) of all 38 count files:

- `misterdownloadmanager.exe`: the main process (24 billion counts over 147,304 functions: networking and TLS, the
  download and torrent engines, the video tools, drawing, translations) and its crash monitor's start-up (the monitor
  needs AF_UNIX sockets, which Windows 10 15035 doesn't have)
- `ffmpeg.exe` x17 (four real jobs: MP3, Opus, two H.264 merges; the rest are yt-dlp's version checks) and
  `ffprobe.exe` x13
- `misterdownloadmanager-nmhost.exe` x4 (registering with the browsers)
- `qjs.exe` x2: version checks only. yt-dlp needed no JavaScript challenge in that session, so `qjs.exe` is built
  without PGO: a profile with no counts would mark the interpreter cold.

## Making it again

Build the kit (`kit/make-kit.py pgo`, [RECIPE.md](../RECIPE.md) "PGO (ARM32)"), run it on a tablet as its README says,
then:

    llvm-profdata merge -o mdm-rt\pgo\mdm-rt-arm32.profdata <profiles>\*.profraw

A profile fits the source it was counted on: a function changed since then goes without one (the build log names
the mismatches).
