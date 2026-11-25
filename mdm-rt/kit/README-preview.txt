MDM RT preview kit (@VERSION@, ARM32 ThinLTO build of @DATE@)

MDM RT = Mister Download Manager 0.5.2 for Windows RT 8.1 and Windows 10 ARM32 (Surface RT, Surface 2).
Steps 1-8 run it from this folder (nothing installed); step 9 tries the Setup. MDM RT keeps its list, settings
and logs in %APPDATA%\mdm-rt (its own folder, not upstream MDM's). To clean up after the test: browser-off.cmd,
uninstall MDM RT (step 9), then delete this kit and %APPDATA%\mdm-rt.

New in kit 6:
  - a video starts downloading sooner: MDM looked every video page up twice (once for the video window, once more
    when the download started), and each look-up takes a minute or more on these tablets. Now the download starts
    from the video window's look-up. Its log says "Started from the video window's look-up (no second look-up)"
    (the tip on the download's Status cell, with the touchpad pointer; collect.cmd takes it too).
  - ytdlp-time.cmd asks for the address: run it, paste the YouTube video's address, press Enter, then Enter again
    (or type a proxy first, if YouTube needs one on your network). Kit 5's script cut an address at its "=" and
    timed YouTube's home page instead of the video.

New in kit 5:
  - yt-dlp starts about 3 times faster: its zipapp had no compiled code, so Python compiled all of yt-dlp at every
    start (13.6 s on a Surface RT before any look-up); now it comes compiled
  - a video look-up may take up to 4 minutes on these tablets (was 90 s, and the limit hid yt-dlp's real error)
  - IF YOUTUBE OPENS ONLY THROUGH A PROXY on your network (kit 4's test: "connection refused" from YouTube): put the
    same proxy as Venetium's in MDM RT's Options > Proxy / Socks. MDM gives it to yt-dlp and uses it itself.
  - ytdlp-time.cmd: times yt-dlp on this tablet (start, first and second look-up), into results\ytdlp-time

New since kit 3 (in kit 4):
  - menus work with a finger (View > Theme, Downloads > Resume ...): a tap on a menu item did nothing before
  - it starts every time on a Surface RT: when ANGLE's first try finds no way to draw, it tries Direct3D 9, then
    11 (kit 3 closed by itself on about every second start); if nothing works it says so instead of vanishing
  - MDM RT's own ffmpeg (with LAME and Opus): "Audio only" MP3, Opus and FLAC work now
  - if MDM RT closes by itself: run collect.cmd right away. It now also takes MDM's crash note (crash.log,
    logs\stderr.log) and Windows' own record of the crash (which module, which address).

Inside:
  MDM RT\                    the program, its helpers (yt-dlp + Python, ffmpeg, QuickJS) and ANGLE (drawing)
  MDM-RT-Setup-@VERSION@-arm32.exe   the Setup (step 9; the same files as MDM RT\)
  run-mdm.cmd                starts MDM RT
  run-mdm-d3d9.cmd           starts it with ANGLE forced to Direct3D 9 (if the normal start draws badly)
  run-mdm-d3d11.cmd          the same with Direct3D 11
  browser-on.cmd             lets Venetium/Chrome/Edge send downloads to this copy (per user, HKCU)
  browser-off.cmd            undoes browser-on.cmd (run it before you delete the kit)
  collect.cmd                copies logs, crash reports and system info into results\

Please try, in this order, and note what happens at each step:

1. Start: run-mdm.cmd. Does the window open, dark purple? Take a screenshot.
   If it doesn't open or draws wrong: try run-mdm-d3d9.cmd, then run-mdm-d3d11.cmd, and note which works.
2. Big download: Add URL (the + button) with any big file (500 MB or more). Watch the speed.
   Pause, Resume. Then close MDM RT in the middle (File > Exit), start it again and resume: it should go on
   from where it was.
3. Video: copy a YouTube link, Add URL (or File > Download video), pick 720p and download. The first one can
   take a while (the JavaScript challenge runs in QuickJS on the tablet). Does the file play, with sound?
   Note how long it took before the download started. Then the same video as "Audio only" MP3 320: does the
   .mp3 play? (MDM RT's own ffmpeg with LAME makes it, on the tablet's CPU: note how long it takes.)
   Then close MDM RT, run ytdlp-time.cmd and paste the same video's address (it takes a few minutes).
4. Browser: at start MDM RT shows "Add Mister Download Manager to your browser" (until a browser has the
   extension). NEW in this kit: Venetium should be in that list, first, with the purple button (when Venetium
   was installed with its Setup). Screenshot it. Click Venetium's button: the extension's Chrome Web Store page
   opens in Venetium; add it there. Then run browser-on.cmd, close Venetium fully and open it again. The
   window should now show Venetium as added. Click a download link (any .zip or .exe): MDM RT should take it,
   and its row should say Venetium. Also try the extension's video button on a YouTube page.
5. Torrent: a magnet link of a legal torrent (for example the Debian or Ubuntu download page's torrent).
6. Themes: View > Theme: RT Blue, RT Green ... and Classic. View > Always dark on/off.
7. Memory: Task Manager, MDM RT's memory when idle and when downloading.
8. Close MDM RT, run collect.cmd, run browser-off.cmd.
9. Setup: run MDM-RT-Setup-@VERSION@-arm32.exe, press "Check requirements" (screenshot), keep "Let browsers
   hand downloads to MDM RT" ticked, install. Start MDM RT from the Start
   menu: same list and settings as before? Click a download link in Venetium (no browser-on.cmd needed now).
   Then uninstall it (Control Panel > Programs and Features, or Settings > Apps): the folder
   %LOCALAPPDATA%\Programs\MDM RT and the Start menu entry should be gone, and Venetium should no longer hand
   downloads to MDM RT. Run collect.cmd again before you uninstall.

Send back:
  - the results\ folder (zip it with 7-Zip RT)
  - your screenshots
  - a few words per step: worked / didn't / slow, and the device (Surface 2 Win10 15035 or Surface RT 8.1)
