# mdm-rt/: the MDM RT project folder

MDM RT is an unofficial fork of [Mister Download Manager](https://github.com/anefzaoui/misterdownloadmanager) by Ahmed
Nefzaoui for Windows RT 8.1 (Surface RT, Tegra 3) and Windows 10 ARM32 (Surface 2, Tegra 4), built with
[llvm-rt](https://github.com/hamed7ir)'s Rust and clang for ARM32 Thumb-2, and also for x64. It is not made or
supported by Ahmed Nefzaoui; it keeps Mister Download Manager's license (GNU GPL v3 or later) and all its notices.

The branch is Mister Download Manager's release commit (tag `v0.5.2`), one commit per change, and this folder. The
release tags follow upstream's (`0.5.2`; a fix release would be `0.5.2.1`).

## The changes (one commit each)
| commit | what |
|---|---|
| build for 32-bit arm windows | no Direct3D 12 renderer on ARM32 (OpenGL ES through ANGLE draws), subsystem 6.02, 32-bit fixes, Windows 10's DPI functions looked up at run time (Windows RT 8.1 has none) |
| helpers: use the ones bundled beside the program | yt-dlp, ffmpeg and QuickJS from `<program folder>\helpers`, no x86/x64 helper downloads on ARM32, QuickJS as yt-dlp's JavaScript runtime |
| mdm rt identity | own name, data folder (`%APPDATA%\mdm-rt`), registry names, repository (problem reports, update check), fork notice in About; version = upstream's, a fix release is built as `0.5.2.1` (`build.py --version`), the exe's version info names MDM RT |
| rt themes | 7-Zip RT's dark look as eight built-in themes, Kodi RT's purple the default, Setup's colour handed over once |
| purple icon | the program icon in Kodi RT's purple (`branding/make-icons.py`) |
| menus: a tap chooses an item | on a touch screen egui ends the pointer in the frame the finger lifts: a menu item now takes the release's place, and a tap on a submenu entry opens it |
| tablets: start-up tries, a message, crash traces | when ANGLE's default display finds nothing to draw with (Surface RT), Direct3D 9, then 11; a message when nothing draws; Rust's abort and panic text in `logs\stderr.log` (no crash monitor before Windows 10 1803) |
| videos: the download starts from the video window's look-up | the window's `yt-dlp -J` answer goes with the download (for two hours): one yt-dlp run less per video |
| update check | MDM RT's releases (`MDM-RT-Setup-<version>-<arm32\|x64>.exe`), checked against the SHA-256 digests GitHub lists; Update now runs the Setup silently and starts MDM RT again |
| venetium | found by its program and its uninstall entry, first in "Add Mister Download Manager to your browser", its downloads named Venetium (its client-hints brand), in Options' capture list |

## This folder
| path | what |
|---|---|
| `build/build.py` | the build: cargo with llvm-rt's rustc, ARM32 / x64 / x86 test build, ThinLTO, PGO (`--pgo gen\|use=`); generates the cargo configuration and the patched dependencies |
| `pgo/` | the profile the ARM32 release is built with (MDM RT and its ffmpeg, LAME and Opus; from a Surface 2 run), how it was made |
| `build/patch-*.py`, `patches/` | what ARM32 needs from the dependencies (windows-sys/windows layouts, QuickJS bindings, aws-lc, crash reports, eframe without WGL, egui_glow's vertex arrays on OpenGL ES 2.0, glutin's ANGLE Direct3D 9/11 choice, AccessKit's UI Automation events on older Windows) |
| `helpers/` | the helpers folder: yt-dlp launcher (`pylauncher/`), embedded Python (`make-python-embed.py`), QuickJS runner (`qjs/`), MDM RT's own ffmpeg (`ffmpeg/`: LAME and libopus, then a static ffmpeg + ffprobe), `build-helpers.py` |
| `kit/` | the device test kits (`make-kit.py`, scripts, READMEs) |
| `branding/` | the RT themes (`make-themes.py`), icons, the README poster |
| `fork/` | `split-series.py` (the patch series from the dev tree), `make-fork.sh` (the fork branch), the repository README |
| `tools/` | `check-pe.py` (ARMNT, subsystem 6.02, every import present on Windows RT 8.1), screenshots |

How to build it: [RECIPE.md](RECIPE.md).
