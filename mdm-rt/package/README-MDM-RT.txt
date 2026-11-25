MDM RT @VERSION@ (@ARCH@)

MDM RT is an unofficial fork of Mister Download Manager by Ahmed Nefzaoui, built for Windows RT 8.1 and Windows 10
ARM32 (Surface RT, Surface 2) and for x64 Windows. It is not made or supported by Ahmed Nefzaoui.

  Source and releases:        https://github.com/hamed7ir/mdm-rt
  Mister Download Manager:    https://github.com/anefzaoui/misterdownloadmanager
  Help (upstream's guide):    https://misterdownloadmanager.com/help/

What is in this folder:
  misterdownloadmanager.exe          the program
  misterdownloadmanager-nmhost.exe   the browsers' native messaging host (the extension talks to it)
  misterdownloadmanager-cli.exe      the command line (misterdownloadmanager-cli get <url>)
  misterdownloadmanager-mcp.exe      the server for AI assistants (MCP)
  libEGL.dll, libGLESv2.dll,         ARM32: ANGLE (OpenGL ES on Direct3D 9/11), from Venetium
  d3dcompiler_47.dll
  helpers\                           ARM32: yt-dlp (yt-dlp.exe runs yt-dlp.pyz with Kodi RT's ARM32 Python),
                                     qjs.exe (QuickJS: YouTube's challenges), ffmpeg

The download list and settings are in %APPDATA%\mdm-rt.

License: GNU GPL, version 3 or later (LICENSE.txt). The parts it is built from and their licenses: ATTRIBUTION.txt.
ARM32: Python (helpers\python314.*) is under the PSF license, yt-dlp under the Unlicense, QuickJS-ng under the MIT
license, FFmpeg under the LGPL (helpers\licenses\), ANGLE under a BSD license (licenses\ANGLE.txt).
