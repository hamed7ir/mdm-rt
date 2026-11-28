#!/bin/sh
# MDM RT helpers: MDM's own ffmpeg.exe + ffprobe.exe for 32-bit Arm Windows (and an x86 build of the same
# configuration, to test it on a PC). Static (two programs, no DLLs), static C runtime, LGPL (no --enable-gpl).
#
#   D:/MSYS2/usr/bin/bash.exe build-ffmpeg.sh <arm32|x86> <ffmpeg-9.0.2 source> <lame prefix> <opus prefix> \
#                                             <build dir> <dist dir> [plain|gen|use=<profdata>]
#
# Run with MSYS2's bash (ffmpeg's configure and GNU make; Git Bash has no make). <lame prefix> and <opus prefix>
# are build-lame.py's and build-opus.py's output (built with the same --pgo as this build's variant).
# Variant: plain (default); gen = the counting build for the PGO kit (-fprofile-generate; LLVM_PROFILE_FILE picks
# where the counts go); use=<profdata> = the release built with the merged profile (-fprofile-use, ThinLTO), as
# ffmpeg-rt's instr/use. Static functions are named by their file relative to the source folder
# (-static-func-strip-dirname-prefix), so a profile fits any checkout. <build dir> must not exist; it gets the compiler wrappers, configure's output and the objects (and its
# own tmp\: nothing is written outside the two folders). <dist dir> gets bin\ffmpeg.exe and bin\ffprobe.exe.
#
# The cross-compile setup is Kodi RT's ffmpeg-rt one (F:\kodi-rt\release\ffmpeg-rt: scripts/configure.sh,
# cross/*): llvm-rt 2.4's clang-cl and lld-link, MSVC 14.44, SDK headers 10.0.26100 + ARM32 libraries 10.0.19041,
# ARM asm through clang, NEON + Thumb. What MDM needs is different from Kodi's player build:
#   - yt-dlp's merges (--merge-output-format mp4), fix-ups and HLS: every demuxer, parser and bitstream filter,
#     the mp4/mov/m4a/matroska/webm/mpegts muxers; stream copy, so no video encoders and no swscale;
#   - "Audio only" MP3 / FLAC / Opus (yt-dlp -x --audio-format): the audio decoders, LAME (libmp3lame), FLAC and
#     AAC encoders, swresample; Opus from YouTube is copied into .opus (the ogg/opus muxer);
#   - subtitles (--convert-subs srt, --embed-subs): WebVTT/SubRip/ASS/mov_text;
#   - inputs yt-dlp hands to ffmpeg (MDM allows file,crypto,data,http,https,tls,tcp,httpproxy): network on,
#     TLS through Windows' own schannel (no OpenSSL to ship or update).
set -eu
ARCH=${1:?arm32 or x86}; SRC=${2:?ffmpeg source}; LAME=${3:?lame prefix}; OPUS=${4:?opus prefix}
B=${5:?build dir}; DIST=${6:?dist dir}; VARIANT=${7:-plain}
: "${RT:=F:/cr/rt24-cr/bin}"
: "${VCTOOLS:=D:/Program Files/vs22buildtools/VC/Tools/MSVC/14.44.35207}"
: "${WINSDK:=D:/Windows Kits/10}"
: "${WINSDKINC:=10.0.26100.0}"
: "${JOBS:=8}"
export PATH="/usr/bin:/bin:$PATH"
case "$ARCH" in
  arm32) TRIPLE=armv7-pc-windows-msvc; MACHINE=arm; LIBARCH=arm; LIBSDK=10.0.19041.0; RCTARGET=arm; PRTARCH=arm ;;
  x86)   TRIPLE=i686-pc-windows-msvc;  MACHINE=x86; LIBARCH=x86; LIBSDK=10.0.26100.0; RCTARGET=i686; PRTARCH=i386 ;;
  *) echo "arch: arm32 or x86"; exit 1 ;;
esac
w() { cygpath -m "$1"; }
[ -f "$SRC/configure" ] || { echo "no ffmpeg source at $SRC"; exit 1; }
[ "$(cat "$SRC/VERSION")" = "9.0.2" ] || { echo "this recipe is for FFmpeg 9.0.2 (its BUILD.txt names that source)"; exit 1; }
[ -f "$LAME/lib/mp3lame.lib" ] && [ -f "$LAME/include/lame/lame.h" ] || { echo "no LAME at $LAME (build-lame.py)"; exit 1; }
[ -f "$OPUS/lib/opus.lib" ] && [ -f "$OPUS/include/opus/opus.h" ] || { echo "no Opus at $OPUS (build-opus.py)"; exit 1; }
# an existing <build dir> is built on (incremental: configure runs again only when its inputs changed, see below)
mkdir -p "$B/tmp"
SRC=$(cd "$SRC" && pwd); LAME=$(cd "$LAME" && pwd); B=$(cd "$B" && pwd); DIST=$(cygpath -u "$DIST")
OPUS=$(cd "$OPUS" && pwd)
BW=$(w "$B"); LAMEW=$(w "$LAME"); OPUSW=$(w "$OPUS"); OPUSVER=$(cat "$OPUS/VERSION")
STRIP=$(printf '%s/' "$(w "$SRC")" | tr -cd '/' | wc -c | tr -d ' ')
EXTRA=""; LTOLINK=""; PGONOTE="no PGO"
case "$VARIANT" in
  plain) ;;
  gen)
    PRT=$(ls "$RT"/../lib/clang/*/lib/windows/clang_rt.profile-$PRTARCH.lib 2>/dev/null | head -1)
    [ -n "$PRT" ] || { echo "no clang_rt.profile-$PRTARCH.lib under $RT/../lib/clang"; exit 1; }
    EXTRA="-fprofile-generate -mllvm -static-func-strip-dirname-prefix=$STRIP"
    LTOLINK="-libpath:$(w "$(dirname "$PRT")")"
    PGONOTE="PGO counting build (-fprofile-generate): for the PGO kit only" ;;
  use=*)
    PROF=${VARIANT#use=}
    [ -f "$PROF" ] || { echo "no profile $PROF"; exit 1; }
    PROFW=$(w "$(cd "$(dirname "$PROF")" && pwd)/$(basename "$PROF")")
    EXTRA="-fprofile-use=$PROFW -flto=thin -mllvm -pgso=false -mllvm -static-func-strip-dirname-prefix=$STRIP -Wno-profile-instr-unprofiled -Wno-profile-instr-out-of-date -Wno-backend-plugin"
    LTOLINK="-opt:lldltojobs=4"
    PGONOTE="PGO: -fprofile-use with $(basename "$PROF") (sha256 $(sha256sum "$PROF" | cut -c1-64)), ThinLTO" ;;
  *) echo "variant: plain, gen or use=<profdata>"; exit 1 ;;
esac

# compiler/linker response files (Windows paths: clang-cl and lld-link read them) and wrappers
printf '%s\n' "--target=$TRIPLE" "-vctoolsdir \"$VCTOOLS\"" "-winsdkdir \"$WINSDK\"" "-winsdkversion $WINSDKINC" > "$B/msvc.rsp"
printf '%s\n' "-machine:$MACHINE" "-libpath:\"$VCTOOLS/lib/$LIBARCH\"" "-libpath:\"$WINSDK/Lib/$LIBSDK/ucrt/$LIBARCH\"" \
  "-libpath:\"$WINSDK/Lib/$LIBSDK/um/$LIBARCH\"" > "$B/link.rsp"
printf '%s\n' "--target=x86_64-pc-windows-msvc" "-vctoolsdir \"$VCTOOLS\"" "-winsdkdir \"$WINSDK\"" "-winsdkversion $WINSDKINC" > "$B/x64-msvc.rsp"
printf '%s\n' "-machine:x64" "-libpath:\"$VCTOOLS/lib/x64\"" "-libpath:\"$WINSDK/Lib/$WINSDKINC/ucrt/x64\"" \
  "-libpath:\"$WINSDK/Lib/$WINSDKINC/um/x64\"" > "$B/x64-link.rsp"
printf '#!/bin/sh\nexec "%s/clang-cl.exe" "@%s/msvc.rsp" -MT %s "$@"\n' "$RT" "$BW" "$EXTRA" > "$B/cc.sh"
printf '#!/bin/sh\nexec "%s/clang-cl.exe" "@%s/x64-msvc.rsp" -MT "$@"\n' "$RT" "$BW" > "$B/hostcc.sh"
printf '#!/bin/sh\nexec "%s/clang.exe" --target=%s "$@"\n' "$RT" "$TRIPLE" > "$B/as.sh"
S="$WINSDK/Include/$WINSDKINC"
printf '#!/bin/sh\nexec "%s/llvm-windres.exe" --target=%s --preprocessor-arg=--target=%s "--preprocessor-arg=-I%s/include" "--preprocessor-arg=-I%s/ucrt" "--preprocessor-arg=-I%s/um" "--preprocessor-arg=-I%s/shared" "$@"\n' \
  "$RT" "$RCTARGET" "$TRIPLE" "$VCTOOLS" "$S" "$S" "$S" > "$B/windres.sh"   # llvm-windres: arm / i686
# ffmpeg's configure finds libopus only through pkg-config (none here): a stand-in that knows "opus" alone
cat > "$B/pkg-config.sh" <<EOF
#!/bin/sh
mode=exists; pkgs=
for a in "\$@"; do
  case "\$a" in
    --version) echo 0.29.2; exit 0 ;;
    --cflags) mode=cflags ;;
    --libs) mode=libs ;;
    --modversion) mode=modversion ;;
    -*) ;;
    *) pkgs="\$pkgs \$a" ;;
  esac
done
for p in \$pkgs; do case "\$p" in opus|">="|"<="|"="|[0-9]*) ;; *) exit 1 ;; esac; done
[ -n "\$pkgs" ] || exit 1
case "\$mode" in
  cflags) echo "-I$OPUSW/include/opus" ;;
  libs) echo "-L$OPUSW/lib -lopus" ;;
  modversion) echo "$OPUSVER" ;;
esac
exit 0
EOF
chmod +x "$B"/*.sh

case "$ARCH" in
  arm32) TARGET="--arch=arm --as=$B/as.sh --enable-asm --enable-neon --enable-thumb"
         SUBSYS="-subsystem:console,6.02" ;;     # Windows 8's version, as MDM RT's own programs
  x86)   TARGET="--arch=x86 --cpu=i686 --disable-asm"   # the test build: no NASM needed
         SUBSYS="" ;;
esac
DEC="aac,aac_latm,opus,vorbis,mp3,mp3float,mp2,mp2float,flac,alac,ac3,eac3,wmav1,wmav2"
DEC="$DEC,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_f32le,pcm_f64le,pcm_u8,pcm_alaw,pcm_mulaw"
DEC="$DEC,h264,hevc,vp8,vp9,av1,mpeg4,h263,mjpeg"          # stream parameters for copies (nothing is re-encoded)
# FFmpeg's own component names (configure silently ignores unknown ones: mov_text is "movtext", there is no "hls"
# protocol - the hls demuxer reads playlists over http); checked against allcodecs.c/allformats.c/protocols.c
DEC="$DEC,webvtt,subrip,srt,ass,ssa,movtext,text"
ENC="libmp3lame,libopus,flac,aac,pcm_s16le,movtext,subrip,srt,webvtt,ass,ssa,wrapped_avframe"
MUX="mp4,mov,ipod,matroska,matroska_audio,webm,mp3,adts,flac,ogg,opus,wav,srt,webvtt,ass,mpegts,null"
PROTO="file,pipe,crypto,data,http,https,tls,tcp,httpproxy,ftp,concat"
FILT="aresample,aformat,anull,null,format,copy,acopy,trim,atrim,setpts,asetpts"

cd "$B"
# configure's temporary files: relative (tmp/ffconf.*), as ffmpeg-rt does - an absolute MSYS path glued to -Fo is
# not converted for clang-cl
export TMPDIR=tmp TMP="$BW/tmp" TEMP="$BW/tmp"
export NM="$RT/llvm-nm.exe"
# Incremental: configure (minutes on Windows) only when what it is given changed; make then rebuilds only the files
# whose sources or headers changed (a changed configuration rewrites config.h, so nearly everything).
SIG="$ARCH|$SRC|$LAME|$OPUS|$DIST|$VARIANT|$EXTRA|$LTOLINK|$TARGET|$SUBSYS|$DEC|$ENC|$MUX|$PROTO|$FILT|$RT|$VCTOOLS|$WINSDK"
if [ -f "$B/ffbuild/config.mak" ] && [ -f "$B/configure.sig" ] && [ "$(cat "$B/configure.sig")" = "$SIG" ]; then
  echo "configure: inputs unchanged, kept"
else
rm -f "$B/configure.sig"
"$SRC/configure" \
  --prefix="$DIST" \
  --enable-cross-compile --target-os=win32 $TARGET \
  --cc="$B/cc.sh" --cxx="$B/cc.sh" --windres="$B/windres.sh" \
  --ld="$RT/lld-link.exe" --ar="$RT/llvm-ar.exe" --nm="$RT/llvm-nm.exe" \
  --ranlib="$RT/llvm-ranlib.exe" --strip="$RT/llvm-strip.exe" \
  --host-cc="$B/hostcc.sh" --host-ld="$RT/lld-link.exe" --host-ldflags="@$BW/x64-link.rsp" \
  --enable-static --disable-shared --enable-w32threads --disable-debug \
  --disable-everything --disable-doc --disable-avdevice --disable-swscale --disable-autodetect \
  --enable-network --enable-schannel --enable-libmp3lame --enable-libopus --pkg-config="$B/pkg-config.sh" \
  --disable-programs --enable-ffmpeg --enable-ffprobe \
  --enable-protocol="$PROTO" --enable-demuxers --enable-parsers --enable-bsfs \
  --enable-decoder="$DEC" --enable-encoder="$ENC" --enable-muxer="$MUX" --enable-filter="$FILT" \
  --enable-swresample --extra-version=mdm-rt \
  --extra-cflags="-I$LAMEW/include -DWIN32_LEAN_AND_MEAN" \
  --extra-ldflags="@$BW/link.rsp -libpath:$LAMEW/lib $SUBSYS $LTOLINK" \
  > "$B/configure.out" 2>&1 || { tail -30 "$B/configure.out"; tail -40 ffbuild/config.log; echo "CONFIGURE FAILED"; exit 1; }
printf '%s' "$SIG" > "$B/configure.sig"
grep -E "^(External libraries|Enabled protocols|Enabled encoders|Enabled muxers)" -A6 "$B/configure.out" | head -40 || true
fi
make -j"$JOBS" > "$B/make.out" 2>&1 || { tail -40 "$B/make.out"; echo "MAKE FAILED"; exit 1; }
make install > "$B/install.out" 2>&1 || { tail -20 "$B/install.out"; echo "INSTALL FAILED"; exit 1; }

# the licence texts and what this build is (helpers\licenses\ffmpeg\ in MDM RT's Setup)
L="$DIST/licenses"; mkdir -p "$L"
cp "$SRC/COPYING.LGPLv2.1" "$L/COPYING.LGPLv2.1.txt"
cp "$SRC/LICENSE.md" "$L/LICENSE-ffmpeg.md"
cp "$LAME/COPYING-lame.txt" "$L/COPYING-lame.txt"
cp "$OPUS/COPYING-opus.txt" "$L/COPYING-opus.txt"
{
  echo "FFmpeg $(cat "$SRC/VERSION") with LAME 3.100 (libmp3lame, LGPL) and libopus $OPUSVER (BSD), built for MDM RT"
  echo "($ARCH) by mdm-rt/helpers/ffmpeg/ build-lame.py, build-opus.py and build-ffmpeg.sh (github.com/hamed7ir/mdm-rt)."
  echo "License: GNU LGPL 2.1 or later (no GPL parts). $PGONOTE."
  echo "Sources: https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz"
  echo "         sha256 8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e"
  echo "         https://sourceforge.net/projects/lame/files/lame/3.100/lame-3.100.tar.gz"
  echo "         sha256 ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"
  echo "         https://gitlab.xiph.org/xiph/opus revision 55513e81d8f606bd75d0ff773d2144e5f2a732f5 (Chromium's"
  echo "         third_party/opus)"
  echo
  echo "configure:"
  sed -n 's/^#define FFMPEG_CONFIGURATION "\(.*\)"$/\1/p' "$B/config.h"
} > "$L/BUILD.txt"
ls -l "$DIST/bin" "$L"
