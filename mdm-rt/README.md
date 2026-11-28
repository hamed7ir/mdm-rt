# mdm-rt/: the MDM RT project folder

MDM RT is an unofficial fork of [Mister Download Manager](https://github.com/anefzaoui/misterdownloadmanager) by Ahmed
Nefzaoui for Windows RT 8.1 (Surface RT, Tegra 3) and Windows 10 ARM32 (Surface 2, Tegra 4), built with
[llvm-rt](https://github.com/hamed7ir)'s Rust and clang for ARM32 Thumb-2, and also for x64. It is not made or
supported by Ahmed Nefzaoui; it keeps Mister Download Manager's license (GNU GPL v3 or later) and all its notices.

The branch is Mister Download Manager's code it is built on (for 1.1 its main at 1f241ae4, 2026-11-26), one commit
per change, and this folder. The
release numbers are MDM RT's own since `v1.1` (1.1 is built on upstream's main of 2026-11-26, whose version is
still 0.5.2; MDM RT 0.5.2 was upstream's 0.5.2).

## The changes (one commit each)
| commit | what |
|---|---|
| build for 32-bit arm windows | no Direct3D 12 renderer on ARM32 (OpenGL ES through ANGLE draws, the default without wgpu), subsystem 6.02, Windows 10's DPI functions looked up at run time (Windows RT 8.1 has none) |
| helpers: use the ones bundled beside the program | yt-dlp, ffmpeg and QuickJS from `<program folder>\helpers`, no x86/x64 helper downloads on ARM32, the QuickJS beside the bundled yt-dlp as its JavaScript runtime, 4 minutes for a look-up on ARM32 |
| mdm rt identity | own name, data folder (`%APPDATA%\mdm-rt`), registry names, repository (problem reports, update check), fork notice in About, Default apps names, the running mutex; its own release number (`build.py --version 1.1`), the exe's version info names MDM RT |
| rt themes | 7-Zip RT's dark look as eight built-in themes, Kodi RT's purple the default, Setup's colour handed over once |
| purple icon | the program icon in Kodi RT's purple (`branding/make-icons.py`) |
| touch screens: a tap chooses a menu item, press-and-hold opens the context menu | on a touch screen egui ends the pointer in the frame the finger lifts: a menu item now takes the release's place, and a tap on a submenu entry opens it; a finger held still for 0.8 s opens the context menu (the download list's, every right-click menu), while a held mouse button stays a click |
| tablets: start-up tries, a message, crash traces | when ANGLE's default display finds nothing to draw with (Surface RT), Direct3D 9, then 11; a message when nothing draws; Rust's abort and panic text in `logs\stderr.log` (no crash monitor before Windows 10 1803) |
| videos: the download starts from the video window's look-up | the window's `yt-dlp -J` answer goes with a download started within ten minutes (upstream's preloaded look-up): one yt-dlp run less per video |
| update check | MDM RT's releases (`MDM-RT-Setup-<version>-<arm32\|x64>.exe`), checked against the SHA-256 digests GitHub lists; Update now runs the Setup silently and starts MDM RT again |
| venetium | found by its program and its uninstall entry, first in "Add Mister Download Manager to your browser", its downloads named Venetium (its client-hints brand), in Options' capture list |

## This folder
| path | what |
|---|---|
| `build/build.py` | the build: cargo with llvm-rt's rustc, ARM32 / x64 / x86 test build, ThinLTO, PGO (`--pgo gen\|use=`); generates the cargo configuration and the patched dependencies |
| `pgo/` | the profiles the ARM32 release is built with (MDM RT, QuickJS, and ffmpeg/LAME/Opus; from Surface 2 runs), how they were made |
| `build/patch-*.py`, `patches/` | what ARM32 needs from the dependencies (windows-sys/windows layouts, QuickJS bindings, aws-lc, crash reports, eframe without WGL, egui_glow's vertex arrays on OpenGL ES 2.0, glutin's ANGLE Direct3D 9/11 choice, AccessKit's UI Automation events on older Windows) |
| `helpers/` | the helpers folder: yt-dlp launcher (`pylauncher/`), embedded Python (`make-python-embed.py`), QuickJS runner (`qjs/`), MDM RT's own ffmpeg (`ffmpeg/`: LAME and libopus, then a static ffmpeg + ffprobe), `build-helpers.py` |
| `kit/` | the device test kits (`make-kit.py`, scripts, READMEs) |
| `branding/` | the RT themes (`make-themes.py`), icons, the README poster |
| `fork/` | `split-series.py` (the patch series from the dev tree), `make-fork.sh` (the fork branch), the repository README |
| `tools/` | `check-pe.py` (ARMNT, subsystem 6.02, every import present on Windows RT 8.1), `pgo-fit.py` (how much of a profile fits a new counting build), screenshots |

How to build it: [RECIPE.md](RECIPE.md).
