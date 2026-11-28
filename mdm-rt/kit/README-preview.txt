MDM RT preview kit (@VERSION@, ARM32 ThinLTO build of @DATE@)

MDM RT = Mister Download Manager for Windows RT 8.1 and Windows 10 ARM32 (Surface RT, Surface 2).
Steps 1-8 run it from this folder (nothing installed); step 9 tries the Setup. MDM RT keeps its list, settings
and logs in %APPDATA%\mdm-rt (its own folder, not upstream MDM's). To clean up after the test: browser-off.cmd,
uninstall MDM RT (step 9), then delete this kit and %APPDATA%\mdm-rt.

New in kit 8 (MDM RT 1.1, the fix for kit 7's one problem):
  - press-and-hold opens the context menu: hold a finger still on a download in the list for about a second and
    its menu opens (the same as a right-click); let go, then tap an item. Upstream keeps a held mouse button a
    click (as Windows does), and that had switched egui's press-and-hold off for fingers too. Please try it on
    the download list, on a category on the left, and on the list's empty space.
  - the Setup's uninstall also removes the empty .torrent key it used to leave behind.

New in kit 7 (the coming MDM RT 1.1):
  - built on upstream's newest code (523 changes since 0.5.2): splitting videos by chapters, Zip preview (only some
    files from a ZIP on a server), Stop and keep for endless streams, site rules, the Link grabber for folders, FTP
    and "Index of" pages, the browser add-on's "download all images", many fixes.
  - the browser-like connection is in too (BoringSSL, built for ARM32 the way adb-rt and Venetium build it): when a
    site's bot check refuses MDM, the download tries once more with a connection made like a browser's. Its log
    then says so. Nothing to set.
  - the certificate error on the Surface 2 (Windows 10 15035: "CERTIFICATE_VERIFY_FAILED" on YouTube) is fixed:
    yt-dlp now also trusts Mozilla's list of root certificates, which MDM RT brings (Windows 15035's own list is
    too old). On the Surface 2: does a YouTube video look up and download now, without a proxy trick?
  - PLEASE RUN ytdlp-speed.cmd on the Surface RT (and on the Surface 2 if you can): it looks a YouTube video up in
    5 different ways, twice each, and times every step (10-20 minutes). From that I pick what makes YouTube faster
    on the tablets. Paste the address when it asks, Enter, Enter. Send results\ytdlp-speed.
  - the download started from the video window says "Started from the look-up already made (no second look-up)"
    in its log (now upstream's way of handing the look-up over).

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
