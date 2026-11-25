# MDM RT build recipe

MDM RT is Mister Download Manager's own Rust workspace, built with cargo. `build/build.py` sets the compiler, the
cross-compiling configuration and the patched dependencies; `helpers/build-helpers.py` makes the helpers folder;
the installer and the kits are made from those outputs. Nothing is written into the source tree (except Cargo.lock
for the length of an ARM32 build, put back afterwards).

## What you need

| what | where it was on the build server | override |
|---|---|---|
| rustc 1.100.0-nightly built on llvm-rt 2.4, with std for thumbv7a/i686/x86_64-pc-windows-msvc | `F:\cr\rustc-rt24` | `RT_RUST` |
| cargo of the same rust build (1.100.0-nightly 2026-09-16) | `F:\rt22\rustc\build-rt24\x86_64-pc-windows-msvc\stage1-tools-bin\cargo.exe` | `RT_CARGO` |
| llvm-rt 2.4 (clang-cl, lld-link, llvm-lib, llvm-readobj) | `F:\cr\rt24-cr` | `RT_TOOLCHAIN` |
| MSVC 14.44 (the last one with ARM32 libraries) | `D:\Program Files\vs22buildtools\VC\Tools\MSVC\14.44.35207` | `RT_VCTOOLS` |
| Windows SDK: 10.0.26100 headers + 10.0.19041 ARM32 libraries | `D:\Windows Kits\10` | `RT_WINSDK` |
| the crates (see below), in a cargo home of its own | `F:\mdm-rt\cargo-home` | `CARGO_HOME` |
| Python 3 for the scripts | | |
| for the helpers: Kodi RT's python-rt prefixes (ARM32 + x64, CPython 3.14.10), yt-dlp's zipapp, QuickJS-ng's amalgamation | see `helpers/build-helpers.py` | `MDMRT_*` |
| for Setup: VS 2022 Roslyn `csc.exe`, .NET Framework 4.x | | |
| for the ARM32 drawing: ANGLE from Venetium's ARM32 release (libEGL, libGLESv2, d3dcompiler_47) | `C:\handoff\release-v1.3.2` | |

The crates are fetched once (`cargo fetch` needs the network; every later command runs offline):

```
cargo -Zgit=shallow-deps -Zgitoxide=fetch fetch --locked --target thumbv7a-pc-windows-msvc --target x86_64-pc-windows-msvc
```

(626 crates, about 110 MB with shallow clones of the four git dependencies.) The cargo home's `config.toml` keeps
`[unstable] git.shallow_deps / gitoxide.fetch` on and `net.offline = true`.

## ARM32 target

`thumbv7a-pc-windows-msvc` (Thumb-2, Cortex-A9 scheduling, NEON), static CRT, PE subsystem 6.02, so the same
programs run on Windows RT 8.1 and Windows 10 ARM32. Rust's std for this target aborts on panic (no unwinding on
32-bit Arm Windows): a panic ends the program after MDM's panic hook has written its report.

What ARM32 needs that upstream doesn't (all in `build/build.py`, made as patched copies, the source tree untouched):

- `windows-sys` / `windows`: no ARM32 definitions of the types whose layout differs between 32-bit and 64-bit
  Windows; `patch-windows-arm32.py` gives ARM32 the x86 ones (both are 32-bit `!_WIN64` Windows).
- `rquickjs-sys` (QuickJS, proxy auto-config scripts): no bindings for ARM32 Windows; `patch-rquickjs-sys.py`
  derives them from its 32-bit Arm Linux ones (MSVC enums are `int`); bindgen's layout asserts check them.
- `aws-lc-sys` (rustls' crypto): portable C (`-DOPENSSL_NO_ASM`, it has no ARM32 Windows assembly), and its
  thread-exit TLS callback named without x86's leading underscore (`patches/crates/aws-lc-sys-0.47.0.patch`).
- `crash-context`, `minidump-writer` (crash reports): ARM32's `CONTEXT` and thread-callback layouts
  (`patches/crates/*.patch`).
- `eframe` (anefzaoui/egui): no WGL on ARM32 (Windows RT has no opengl32.dll): it draws through EGL, i.e.
  OpenGL ES on ANGLE (Venetium's libEGL/libGLESv2: Direct3D 11, else Direct3D 9 - the Tegras' feature level 9_1
  is too low for ANGLE's Direct3D 11 renderer) (`patches/egui/0001-eframe-egl-only-on-arm32.patch`).
- `egui_glow`: ANGLE's OpenGL ES 2.0 context (Direct3D 9) hands out ES 3's glGenVertexArrays, which fails there:
  vertex arrays emulated on ES 2.0 (`patches/egui/0002-egui_glow-emulated-vao-on-gles2.patch`).
- `glutin`: `MDM_ANGLE=d3d9` or `d3d11` picks ANGLE's renderer (EGL_PLATFORM_ANGLE_TYPE_ANGLE), for a device
  where the default draws badly (`patches/crates/glutin-0.32.3.patch`; the kit's run-mdm-d3d9/d3d11.cmd). MDM RT
  itself tries d3d9, then d3d11, when ANGLE's default finds no window config (it never does on a Tegra 3).
- `accesskit_windows` (ARM32, x86 and x64): raising a UI Automation event or property change that Windows doesn't
  know (Windows RT 8.1, Windows 10 before 1703: "Unknown propertyId") is ignored instead of unwrapped. On a touch
  tablet the touch keyboard is a UIA client, so AccessKit is on, and the unwrap's panic ended MDM on the Surface RT
  (`patches/crates/accesskit_windows-0.35.2.patch`).
- `--cfg windows_raw_dylib` (windows-targets has no ARM32 import libraries).

MDM's own changes for ARM32 are commits in the fork (see the fork's history): no Direct3D 12 renderer (wgpu) on
ARM32, subsystem 6.02, 32-bit fixes, Windows 10's DPI functions looked up at run time, the bundled helpers.

## Build

```
python -I mdm-rt\build\build.py <arm32|x64|x86> [--variant thin|fat|dev] [--packages app,nmhost,cli,mcp]
```

- `thin` (the release): ThinLTO, opt-level "s" as upstream, 16 codegen units. `fat`: upstream's own release
  profile (fat LTO; the app's link needs about 5.5 GB of RAM). `dev`: no LTO, for quick checks.
- output: `F:\mdm-rt\out\<arch>-<variant>\` (`MDMRT_OUT`), cargo's files in `F:\mdm-rt\target` (`MDMRT_TARGET`).
- 8 jobs (`--jobs`), below-normal priority; rustc's incremental cache for `thin` and `dev` (not `fat`, not
  `--pgo`; `--no-incremental` for a build from scratch, as the final release should be).
- ARM32 builds end with `tools/check-pe.py`: ARMNT, subsystem 6.02, static CRT, and every import (API sets
  resolved through the device's own `apisetschema.dll`) exported by a Surface RT's Windows RT 8.1 DLLs.
- `x86` is a test build: 32-bit x86 that draws as ARM32 does (`--cfg mdm_rt_angle`: no wgpu, EGL only), to run the
  ARM32 drawing path on an x86/x64 PC with Venetium x86's ANGLE.

## Helpers (ARM32)

```
python -I mdm-rt\helpers\ffmpeg\build-lame.py arm32 <lame-3.100 source> <lame prefix>
python -I mdm-rt\helpers\ffmpeg\build-opus.py arm32 <F:\cr\src\third_party\opus\src> <opus prefix>
D:\MSYS2\usr\bin\bash.exe mdm-rt/helpers/ffmpeg/build-ffmpeg.sh arm32 <ffmpeg-9.0.2 source> <lame prefix> <opus prefix> <build dir> <dist dir>
set MDMRT_FFMPEG_VERSION=9.0.2-mdm-rt
python -I mdm-rt\helpers\build-helpers.py arm32 <out dir> --ffmpeg <dist dir>\bin --ffmpeg-licenses <dist dir>\licenses
```

- `ffmpeg.exe` + `ffprobe.exe`: MDM RT's own static build of FFmpeg 9.0.2 with LAME 3.100 and libopus (Chromium's
  Opus, the one Venetium builds; LGPL + BSD, no GPL parts), `helpers/ffmpeg/`. Kodi RT's ffmpeg-rt cross-compile setup (llvm-rt clang-cl, ARM asm with NEON + Thumb), but what
  yt-dlp asks of it for MDM: stream-copy merges into mp4/mkv (every demuxer, parser and bitstream filter), HLS,
  "Audio only" MP3 (LAME) / FLAC / Opus, subtitles (WebVTT, SubRip, mov_text), network with Windows' own TLS
  (schannel). The x86 build of the same configuration is the test build (`work\run-fftest.py`: merges, conversions,
  subtitles, HLS over HTTP, yt-dlp end to end).

- `yt-dlp.exe`: `helpers/pylauncher/pylauncher.c`, runs `yt-dlp.pyz` (yt-dlp's own zipapp release file) with the
  embedded Python beside it, in the same process.
- the embedded Python: `helpers/make-python-embed.py` from python-rt's ARM32 prefix (python314.dll with its modules
  built in, the standard library byte-compiled into python314.zip, python314._pth).
- `qjs.exe`: `helpers/qjs/qjs.c` over QuickJS-ng's amalgamation: the JavaScript runtime yt-dlp needs for YouTube
  (`--js-runtimes quickjs:...`, which MDM RT passes when nothing else is found).
- `versions.json`: what MDM shows for each helper.
- MDM finds them in `<program folder>\helpers\` (`mdm_tools::bundled`) and doesn't download x86/x64 helpers there.

## Notes

- **Panics on ARM32**: rustc-rt24's std for thumbv7a-pc-windows-msvc is built with panic=abort (no unwinding on
  Windows ARM32), so `catch_unwind` catches nothing there. Upstream uses it in three places: archive extraction
  (a decoder that panics on a damaged archive becomes "the decoder failed"), the system file-icon lookup, and the
  video job runner. On ARM32 such a panic closes MDM RT (the crash monitor still makes its report) instead of
  showing an error. x64 unwinds as upstream.
- **zlib**: every gzip/deflate user in MDM (extraction of .gz/.tar.gz, ZIP, torrent blocklists) already runs on
  `zlib-rs`, the Rust port of zlib-ng: zip's `deflate` feature turns on `flate2/zlib-rs`, and with it flate2 uses
  zlib-rs instead of miniz_oxide (`flate2/src/ffi/mod.rs`). flate2's own docs say it outperforms the C
  implementations, and it needs no C cross-compile for ARM32, so nothing was changed.

## PGO (ARM32)

The release is built with a profile from a real tablet, as Venetium and Kodi RT are: a counting build runs once on
a Surface, then the release is compiled with its counts. One profile covers MDM RT's Rust code, its ffmpeg (FFmpeg,
LAME, libopus) and the helpers' qjs.exe (QuickJS-ng, which yt-dlp runs for YouTube's challenges: about 22% faster
with a profile in a test on x64). The C code linked into MDM itself (aws-lc, rquickjs's QuickJS) is not counted: a
C counting runtime in the same program would clash with Rust's. Records of different programs live side by side in
the one merged profile (each function is found by its name and its shape's hash).

1. Counting builds:
   ```
   python -I mdm-rt\tools\pgotest\run-pgotest.py      (proves Rust PGO here; leaves the kit's self-test exe)
   python -I mdm-rt\build\build.py arm32 --variant thin --pgo gen                     -> out\arm32-thin-pgogen
   python -I mdm-rt\helpers\ffmpeg\build-lame.py arm32 <lame source> <lame-gen> --pgo gen
   python -I mdm-rt\helpers\ffmpeg\build-opus.py arm32 <opus source> <opus-gen> --pgo gen
   bash mdm-rt/helpers/ffmpeg/build-ffmpeg.sh arm32 <ffmpeg source> <lame-gen> <opus-gen> <build> <dist-gen> gen
   python -I mdm-rt\helpers\build-helpers.py arm32 <helpers-gen> --qjs-pgo gen --ffmpeg <dist-gen>\bin --ffmpeg-licenses <dist-gen>\licenses
   python -I mdm-rt\kit\make-kit.py pgo out\arm32-thin-pgogen <helpers-gen> <angle> <kit name> --selftest <pgotest.exe>
   ```
   `--pgo gen` keeps the thin variant's cargo profile and target folder on purpose: cargo's `-C metadata`, so every
   Rust symbol name, is the same with and without `-Cprofile-generate` (`run-pgotest.py` checks it), so the
   profile's names match the release build's.
2. The training run: the kit's README (`kit/README-pgo.txt`): run-pgo.cmd sets LLVM_PROFILE_FILE to the kit's
   profiles folder (the ffmpeg and qjs that yt-dlp starts inherit it) and yt-dlp's cache to a fresh folder there
   (XDG_CACHE_HOME: YouTube's challenge then runs in the counting qjs), self-tests check that the test program, qjs
   and ffmpeg write counts, then 10-15 minutes of downloads, videos, MP3/Opus conversions, a torrent and the windows,
   and File > Exit.
3. Merge: `llvm-profdata merge -o mdm-rt\pgo\mdm-rt-arm32.profdata <profiles>\*.profraw` (rt2.4's llvm-profdata:
   the same LLVM as rustc-rt24 and clang-cl).
4. Release: `build.py arm32 --variant thin --pgo use=<profdata>`, `build-lame.py`/`build-opus.py --pgo use=<profdata>`,
   `build-ffmpeg.sh ... use=<profdata>` (ThinLTO, lld at 4 threads), `build-helpers.py ... --qjs-pgo use=<profdata>`.
   Functions changed since the counting build just go without a profile. The helpers' ARM32 C code is compiled for
   `armv7-pc-windows-msvc` (the same Thumb-2 code as `thumbv7a`; with that spelling clang finds its
   `clang_rt.profile-arm.lib`).

## Release

Tag = MDM's version (`0.5.2`; a fix: `0.5.2.1`). Assets: `MDM-RT-Setup-<ver>-arm32.exe`, `MDM-RT-Setup-<ver>-x64.exe`
and `SHA256SUMS.txt`.
