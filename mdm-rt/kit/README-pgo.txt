MDM RT PGO kit (@VERSION@, counting build of @DATE@)

This is a COUNTING build of MDM RT, its ffmpeg and QuickJS: while you use it, it counts which code runs how often, and
when it closes it writes those counts into profiles\. From them I build the release with PGO (the compiler then
lays out and optimises the hot code for the tablets), as Venetium and Kodi RT were built. It runs slower than a
normal build: that's expected. It uses your normal MDM RT list and settings (%APPDATA%\mdm-rt).

Why again for 1.1: the counts from 0.5.2's run fit only 12 % of 1.1's functions (MDM's code moved into a library
and egui and many other parts are newer, so their names changed), so 1.1 needs counts of its own. The same steps
as last time; press-and-hold on the list (kit 8's fix) is worth a try too.

Inside:
  MDM RT\              the counting build, its helpers (counting ffmpeg/ffprobe and QuickJS, normal yt-dlp/Python), ANGLE
  run-pgo.cmd          starts it with the counts going to profiles\
  collect-pgo.cmd      after you exit: lists the counts, copies the logs next to them

Do it on the Surface 2 (Windows 10 ARM32): one tablet is enough. (The counting build also links Windows'
transaction DLL, ktmw32.dll, which the release doesn't need; Windows 10 has it. On the Surface RT it would start only
if C:\Windows\System32\ktmw32.dll exists there.)

0. If MDM RT is running (also check the notification area), close it: File > Exit. Otherwise run-pgo.cmd only
   hands over to the running copy and nothing is counted.
1. Run run-pgo.cmd.
2. Downloads, 5-10 minutes in all:
   - 2 or 3 big files over https (for example a Venetium release zip from GitHub, a Debian armhf ISO from
     cdimage.debian.org). Let each run at least 2 minutes; finishing them is better.
   - Pause one and resume it. Delete one finished download from the list.
   - A few small files (any .zip or .pdf links).
3. Videos (yt-dlp, QuickJS and ffmpeg):
   - a YouTube video at 720p (the first one takes a few minutes before it starts: YouTube's challenge runs in the
     counting QuickJS, with a fresh cache made for this kit, so that it gets counted);
   - the same video as "Audio only" MP3 320, then as "Audio only" Opus;
   - a video from another site (Vimeo, X or Instagram) as "Audio only" MP3 and as Opus: their sound is AAC, so
     this is the part that counts LAME and libopus best.
4. A legal torrent (a Debian or Ubuntu magnet link) for a minute or two.
5. The window: open Options and click through every tab, Help > About, View > Theme (switch two or three times),
   scroll the download list up and down, resize and maximise the window.
6. Leave it idle for a minute.
7. File > Exit. Not the X button: that only hides MDM RT in the notification area, and the counts are written
   only when it really exits. Wait until misterdownloadmanager.exe is gone from Task Manager.
8. Run collect-pgo.cmd. There should be several count-*.profraw files; the biggest (several MB) is MDM RT's.
   If there is none, MDM RT didn't exit normally: tell me what happened.

Send back: the profiles folder (zip it with 7-Zip RT), and which tablet it was.
After that you can delete this kit.
