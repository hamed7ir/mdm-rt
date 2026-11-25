// =============================================================================
//  MDM RT installer (Setup.cs) - adapted from 7-Zip RT's (hamed7ir/7zip-rt 7zip-rt\installer\Setup.cs), itself from
//  Venetium's installer (hamed7ir/venetium installer\Setup.cs) and hamed7ir/DroidFinestra's AnyCPU/MSIL installer.
//
//  AnyCPU MSIL on .NET Framework 4.0 (Client Profile assemblies only), so ONE exe runs on Windows RT 8.1 (its in-box
//  .NET 4.5.1), on Windows 10 ARM32 and on x86/x64 Windows. Per user: %LocalAppData%\Programs\MDM RT, no admin.
//  The payload is embedded as gzip resources ("payload/<file>.gz") listed with SHA-256 in payload.list.
//
//  What it sets up, all under HKEY_CURRENT_USER:
//   * the browsers' native messaging host, so the Mister Download Manager extension (Chrome Web Store, Edge Add-ons,
//     Firefox) hands downloads to MDM RT: misterdownloadmanager-nmhost.exe --register writes its manifests beside
//     it and HKCU\Software\{Chromium (Venetium reads this first), Google\Chrome, Microsoft\Edge, BraveSoftware\
//     Brave-Browser, Mozilla}\NativeMessagingHosts\com.misterdownloadmanager.host. These are registry keys, not COM
//     classes, so they work with Explorer and the browser elevated too (UAC off, built-in Administrator).
//   * Start menu shortcut, optional desktop shortcut, optional startup entry (HKCU Run "MDM RT", "/startup": MDM RT
//     then waits in the notification area, as its Options > "Launch on startup" does), the uninstall entry,
//     HKCU\Software\MDM RT\Path.
//   * the colour: an RT theme for MDM RT's first start (HKCU\Software\MDM RT\InstallTheme, which MDM RT takes once,
//     as upstream's installer hands over its language).
//  An existing install (the uninstall entry's folder) is found and offered as an update with its current choices.
//  Uninstall removes all of that again; the download list and settings (%APPDATA%\mdm-rt) stay.
//
//  Kept from Venetium's and 7-Zip RT's hardened installer: verify the whole package before touching the folder, write
//  each file as .new and swap, delete only files Setup owns, refuse system/personal folders (SafeTarget), files-in-use
//  check, self-deleting uninstall.exe, close guard while installing, requirements check that never blocks installing.
//
//  Modes:
//    (no args)              install wizard (an update when MDM RT is installed already)
//    --update               the same
//    --check [file]         requirements report only
//    --silent [dir] [--no-browser] [--desktop] [--startup] [--colour <name>]   install without UI (colour: purple,
//                           blue, teal, green, orange, red, pink, gray; default: keep). exit 0 ok, 4 in use, 5 bad folder, 1 error
//             [--keep]      the choices the copy in [dir] has (browser host, startup entry, desktop shortcut, its theme)
//             [--relaunch]  MDM RT's Update now: wait up to a minute for MDM RT to close, then start it again (/updated)
//    --uninstall <dir> [--silent]   remove it (files, shortcuts, browser host, startup entry, uninstall entry)
//    (run as uninstall.exe) confirm, then uninstall its own folder
// =============================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace MdmRtSetup
{
    internal static class Program
    {
        internal const string AppName = "MDM RT";
        internal const string InstallFolderName = "MDM RT";
        internal const string UninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\MDM RT";
        internal const string AppKey = @"Software\MDM RT";
        internal const string ShortcutDesc = "MDM RT - Mister Download Manager for Windows RT and ARM32 Windows";
        internal const string Publisher = "Hamed Ghorbani";
        internal const string ExeName = "misterdownloadmanager.exe";
        internal const string HostExe = "misterdownloadmanager-nmhost.exe";
        internal static readonly string[] ProcessNames =   // Process.GetProcessesByName: MDM RT and its helpers
            { "misterdownloadmanager", "misterdownloadmanager-nmhost", "misterdownloadmanager-cli", "misterdownloadmanager-mcp",
              "yt-dlp", "ffmpeg", "ffprobe", "qjs", "python" };

        [STAThread]
        private static int Main(string[] args)
        {
            bool quiet = Array.Exists(args, a => Eq(a, "--silent"));
            try
            {
                string a0 = args.Length >= 1 ? args[0] : "";
                if (Eq(a0, "--uninstall"))
                {
                    string dir = args.Length >= 2 && !args[1].StartsWith("--") ? args[1].Trim().Trim('"') : Path.GetDirectoryName(Application.ExecutablePath);
                    if (quiet)
                    {
                        if (InUse.Check(dir) != null) return 4;
                        if (!SafeTarget.IsInstalledCopy(dir)) return 5;
                        return Uninstaller.Run(dir) ? 0 : 1;
                    }
                    Application.EnableVisualStyles();
                    Application.SetCompatibleTextRenderingDefault(false);
                    return UninstallWithUi(dir, false);
                }
                if (Eq(a0, "--check"))
                {
                    var rep = Requirements.Check(null);
                    string text = Requirements.Format(rep);
                    if (args.Length >= 2) File.WriteAllText(args[1], text, Encoding.UTF8);
                    else MessageBox.Show(text, AppName + " " + Info.AppVersion + " (" + Info.Flavor + ") - requirements");
                    return Requirements.ExitCode(rep);
                }
                if (Eq(a0, "--silent"))
                {
                    string dir = DefaultDir();
                    var opt = new Options { Browser = true, Desktop = false, Startup = false, Colour = -1 };
                    bool keep = false, relaunch = false;
                    for (int i = 1; i < args.Length; i++)
                    {
                        if (Eq(args[i], "--no-browser")) opt.Browser = false;
                        else if (Eq(args[i], "--desktop")) opt.Desktop = true;
                        else if (Eq(args[i], "--startup")) opt.Startup = true;
                        else if (Eq(args[i], "--keep")) keep = true;          // the choices the installed copy has
                        else if (Eq(args[i], "--relaunch")) relaunch = true;  // MDM RT's Update now: wait, then start it
                        else if ((Eq(args[i], "--colour") || Eq(args[i], "--color")) && i + 1 < args.Length)
                        {
                            opt.Colour = Colours.Parse(args[++i]);
                            if (opt.Colour < 0) return 2;
                        }
                        else if (args[i].StartsWith("-") || args[i].StartsWith("/")) return 2;
                        else dir = args[i].Trim().Trim('"');
                    }
                    if (SafeTarget.Problem(dir) != null) return 5;
                    if (keep && SafeTarget.IsInstalledCopy(dir))
                    {
                        opt.Browser = Uninstaller.Inside(Browser.Registered(), dir);
                        opt.Startup = Startup.IsOurs(dir);
                        opt.Desktop = File.Exists(Existing.DesktopLink()) && Uninstaller.Inside(Shortcut.TargetOf(Existing.DesktopLink()), dir);
                        opt.Colour = -1;
                    }
                    // MDM RT closes itself after starting this: give it (and its helpers) a minute to be gone
                    for (int w = 0; relaunch && w < 120 && InUse.Check(dir) != null; w++) Thread.Sleep(500);
                    if (InUse.Check(dir) != null) return 4;
                    Installer.Install(dir, opt, null);
                    if (relaunch)
                        try { Process.Start(new ProcessStartInfo(Path.Combine(dir, ExeName), "/updated") { WorkingDirectory = dir }); } catch { }
                    return 0;
                }

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                if (Eq(Path.GetFileNameWithoutExtension(Application.ExecutablePath), "uninstall"))
                    return UninstallWithUi(Path.GetDirectoryName(Application.ExecutablePath), true);
                if (a0.Length > 0 && !Eq(a0, "--update")) return 2;
                Application.Run(new InstallForm());
                return 0;
            }
            catch (Exception ex)
            {
                if (quiet) { try { Console.Error.WriteLine(ex.ToString()); } catch { } return 1; }
                try { MessageBox.Show(ex.ToString(), AppName + " Setup - error", MessageBoxButtons.OK, MessageBoxIcon.Error); } catch { }
                return 1;
            }
        }

        private static int UninstallWithUi(string dir, bool confirm)
        {
            if (confirm && MessageBox.Show("Remove " + AppName + " from this computer?\n\nIts files, Start menu shortcuts, browser integration and startup entry are removed. " +
                    "Your download list and settings (%APPDATA%\\mdm-rt) and your downloaded files stay.",
                    "Uninstall " + AppName, MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return 0;
            string busy;
            while ((busy = InUse.Check(dir)) != null)
                if (MessageBox.Show(busy + "\n\nClose all its windows (and the MDM RT icon in the notification area), then press Retry.", "Uninstall " + AppName,
                    MessageBoxButtons.RetryCancel, MessageBoxIcon.Warning) != DialogResult.Retry) return 4;
            if (!SafeTarget.IsInstalledCopy(dir))
            {
                MessageBox.Show(dir + "\n\ndoesn't look like an installed " + AppName + " (no " + ExeName + " and uninstall.exe in it), so nothing was removed.",
                    "Uninstall " + AppName, MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return 5;
            }
            Uninstaller.Run(dir);
            return 0;
        }

        internal static bool Eq(string a, string b) { return string.Equals(a, b, StringComparison.OrdinalIgnoreCase); }

        internal static string DefaultDir()
        {
            string p = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return Path.Combine(Path.Combine(p, "Programs"), InstallFolderName);
        }

        internal static string StartMenuFolder()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), AppName);
        }
    }

    internal sealed class Options
    {
        public bool Browser, Desktop, Startup;
        public int Colour = -1;   // a preset of Colours; -1 = keep MDM RT's own choice (RT Purple on a first start)
    }

    /// <summary>The RT themes' colours: 7-Zip RT's accent presets, in the same order (DarkTheme.cpp k_AccentPresets),
    /// which MDM RT has as built-in themes rt-purple ... rt-gray (mdm-rt\branding\make-themes.py).</summary>
    internal static class Colours
    {
        internal static readonly string[] Names = { "Purple (Kodi RT)", "Blue", "Teal", "Green", "Orange", "Red", "Pink", "Gray" };
        internal static readonly int[] Rgb = { 0xa24bff, 0x3d8bff, 0x22c7b8, 0x3ccf6e, 0xff8a2b, 0xff4d5e, 0xff5fb7, 0x9aa0a6 };

        internal static Color ColorOf(int rgb) { return Color.FromArgb((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255); }

        /// <summary>The MDM RT theme id of a preset: "rt-purple", "rt-blue", ...</summary>
        internal static string ThemeId(int colour) { return "rt-" + Names[colour].Split(' ')[0].ToLowerInvariant(); }

        /// <summary>The theme MDM RT takes at its next start (once: it deletes the value).</summary>
        internal static void Save(int colour)
        {
            using (var k = Registry.CurrentUser.CreateSubKey(Program.AppKey)) k.SetValue("InstallTheme", ThemeId(colour));
        }

        /// <summary>A preset by number (0-7) or by the first word of its name ("blue"; "grey" too), else -1.</summary>
        internal static int Parse(string s)
        {
            s = (s ?? "").Trim().ToLowerInvariant();
            int n;
            if (int.TryParse(s, out n)) return n >= 0 && n < Names.Length ? n : -1;
            if (s == "grey") s = "gray";
            if (s.StartsWith("rt-")) s = s.Substring(3);
            for (int i = 0; i < Names.Length; i++)
                if (Names[i].Split(' ')[0].ToLowerInvariant() == s) return i;
            return -1;
        }

        internal static void ToHsl(int rgb, out double h, out double s, out double l)
        {
            double r = ((rgb >> 16) & 255) / 255.0, g = ((rgb >> 8) & 255) / 255.0, b = (rgb & 255) / 255.0;
            double mx = Math.Max(r, Math.Max(g, b)), mn = Math.Min(r, Math.Min(g, b)), d = mx - mn;
            l = (mx + mn) / 2;
            if (d < 1e-9) { h = 0; s = 0; return; }
            s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
            if (mx - r < 1e-9) h = 60 * ((g - b) / d) + (g < b ? 360 : 0);
            else if (mx - g < 1e-9) h = 60 * ((b - r) / d) + 120;
            else h = 60 * ((r - g) / d) + 240;
        }

        internal static int FromHsl(double h, double s, double l)
        {
            s = Math.Max(0, Math.Min(1, s)); l = Math.Max(0, Math.Min(1, l));
            double c = (1 - Math.Abs(2 * l - 1)) * s, hp = h / 60;
            while (hp >= 6) hp -= 6;
            while (hp < 0) hp += 6;
            double t = hp;
            while (t >= 2) t -= 2;
            double x = c * (1 - Math.Abs(t - 1)), r = 0, g = 0, b = 0;
            switch ((int)hp)
            {
                case 0: r = c; g = x; break;
                case 1: r = x; g = c; break;
                case 2: g = c; b = x; break;
                case 3: g = x; b = c; break;
                case 4: r = x; b = c; break;
                default: r = c; b = x; break;
            }
            double m = l - c / 2;
            return ((int)(Math.Max(0, Math.Min(1, r + m)) * 255 + 0.5) << 16) |
                   ((int)(Math.Max(0, Math.Min(1, g + m)) * 255 + 0.5) << 8) |
                    (int)(Math.Max(0, Math.Min(1, b + m)) * 255 + 0.5);
        }

        /// <summary>A copy of a picture in a preset colour, as 7-Zip RT tints its pictures: purple shades (hue 225-315,
        /// saturation 0.2 and more) take the colour's hue; greys, white and other colours stay.</summary>
        internal static Bitmap Tint(Image src, int colour)
        {
            var bmp = new Bitmap(src);
            if (colour <= 0) return bmp;
            double ah, asat, al;
            ToHsl(Rgb[colour], out ah, out asat, out al);
            for (int y = 0; y < bmp.Height; y++)
                for (int x = 0; x < bmp.Width; x++)
                {
                    Color p = bmp.GetPixel(x, y);
                    if (p.A == 0) continue;
                    double h, s, l;
                    ToHsl((p.R << 16) | (p.G << 8) | p.B, out h, out s, out l);
                    if (s < 0.2 || h < 225 || h > 315) continue;
                    int c = FromHsl(ah, s * asat, l);
                    bmp.SetPixel(x, y, Color.FromArgb(p.A, (c >> 16) & 255, (c >> 8) & 255, c & 255));
                }
            return bmp;
        }
    }

    /// <summary>The MDM RT this user has installed already (the uninstall entry's folder), for an update.</summary>
    internal static class Existing
    {
        internal static string Dir()
        {
            try
            {
                using (var k = Registry.CurrentUser.OpenSubKey(Program.UninstallKey))
                {
                    string loc = k != null ? k.GetValue("InstallLocation") as string : null;
                    if (!string.IsNullOrEmpty(loc) && SafeTarget.IsInstalledCopy(loc)) return loc.TrimEnd('\\');
                }
            }
            catch { }
            return null;
        }

        internal static string Version()
        {
            try { using (var k = Registry.CurrentUser.OpenSubKey(Program.UninstallKey)) return k != null ? k.GetValue("DisplayVersion") as string : null; }
            catch { return null; }
        }

        internal static string DesktopLink()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), Program.AppName + ".lnk");
        }
    }

    // -- payload: embedded gzip resources + payload.list (sha256 <TAB> size <TAB> relative name) -----------------
    internal sealed class PayloadFile
    {
        public string Name, Sha256;
        public long Size;
    }

    internal static class Payload
    {
        internal static List<PayloadFile> List()
        {
            var list = new List<PayloadFile>();
            using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.list"))
            {
                if (s == null) throw new InvalidDataException("This Setup has no payload.list - it was not built by build-installer.ps1.");
                using (var r = new StreamReader(s, Encoding.UTF8))
                {
                    string line;
                    while ((line = r.ReadLine()) != null)
                    {
                        var f = line.Split('\t');
                        if (f.Length != 3) continue;
                        list.Add(new PayloadFile { Sha256 = f[0], Size = long.Parse(f[1]), Name = f[2] });
                    }
                }
            }
            return list;
        }

        internal static Stream Open(PayloadFile f)
        {
            var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload/" + f.Name.Replace('\\', '/') + ".gz");
            if (s == null) throw new InvalidDataException("Payload resource missing: " + f.Name);
            return new GZipStream(s, CompressionMode.Decompress);
        }

        internal static byte[] ReadAll(PayloadFile f)
        {
            using (var s = Open(f))
            using (var m = new MemoryStream())
            {
                Copy(s, m);
                return m.ToArray();
            }
        }

        internal static void Copy(Stream from, Stream to)
        {
            var buf = new byte[81920];
            int n;
            while ((n = from.Read(buf, 0, buf.Length)) > 0) to.Write(buf, 0, n);
        }

        internal static string Hex(byte[] h)
        {
            var sb = new StringBuilder(h.Length * 2);
            foreach (var b in h) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }
    }

    // -- requirements (from Venetium's installer) -------------------------------------------------------------
    internal enum Level { Ok, Warn, Missing, Blocked }

    internal sealed class Req
    {
        public Level Level;
        public string Text, Fix, Url;
    }

    internal static class Requirements
    {
        internal const ushort X86 = 0x14c, X64 = 0x8664, ArmNt = 0x1c4, Arm = 0x1c0, Arm64 = 0xaa64;

        [StructLayout(LayoutKind.Sequential)]
        private struct OSVERSIONINFOEX
        {
            public int dwOSVersionInfoSize, dwMajorVersion, dwMinorVersion, dwBuildNumber, dwPlatformId;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string szCSDVersion;
            public ushort wServicePackMajor, wServicePackMinor, wSuiteMask;
            public byte wProductType, wReserved;
        }
        [DllImport("ntdll.dll")] private static extern int RtlGetVersion(ref OSVERSIONINFOEX v);

        internal static Version OsVersion()
        {
            try
            {
                var v = new OSVERSIONINFOEX { dwOSVersionInfoSize = Marshal.SizeOf(typeof(OSVERSIONINFOEX)) };
                if (RtlGetVersion(ref v) == 0) return new Version(v.dwMajorVersion, v.dwMinorVersion, v.dwBuildNumber);
            }
            catch { }
            return Environment.OSVersion.Version;
        }

        internal static string OsArch()
        {
            return (Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432")
                    ?? Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE") ?? "").ToUpperInvariant();
        }

        internal static string MachineName(ushort m)
        {
            switch (m)
            {
                case X86: return "x86";
                case X64: return "x64";
                case ArmNt: case Arm: return "ARM32";
                case Arm64: return "ARM64";
                default: return "machine 0x" + m.ToString("X");
            }
        }

        private static string OsArchName(string a)
        {
            switch (a) { case "AMD64": return "x64"; case "X86": return "x86"; case "ARM": return "ARM32"; case "ARM64": return "ARM64"; default: return a; }
        }

        internal static string CannotRun(ushort m, string os, Version ver)
        {
            switch (m)
            {
                case X86: return os == "ARM" ? "ARM32 Windows cannot run x86 programs" : null;
                case X64:
                    if (os == "AMD64") return null;
                    if (os == "ARM64") return ver.Build >= 22000 ? null : "Windows 10 on ARM64 cannot run x64 programs (Windows 11 can)";
                    return OsArchName(os) + " Windows cannot run x64 programs";
                case ArmNt: case Arm:
                    if (os == "ARM") return null;
                    if (os == "ARM64") return ver.Build >= 26100 ? "Windows 11 24H2 and later no longer run 32-bit ARM programs" : null;
                    return OsArchName(os) + " Windows cannot run ARM32 programs";
                case Arm64: return os == "ARM64" ? null : OsArchName(os) + " Windows cannot run ARM64 programs";
                default: return "unknown machine type 0x" + m.ToString("X");
            }
        }

        internal static string SystemDirFor(ushort m, string os)
        {
            string win = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
            string native = Path.Combine(win, Environment.Is64BitOperatingSystem && !Environment.Is64BitProcess ? "Sysnative" : "System32");
            switch (m)
            {
                case X86: return os == "X86" ? native : Path.Combine(win, "SysWOW64");
                case ArmNt: case Arm: return os == "ARM" ? native : Path.Combine(win, "SysArm32");
                default: return native;
            }
        }

        internal static bool ParsePe(byte[] b, out ushort machine, out List<string> imports)
        {
            machine = 0; imports = new List<string>();
            try
            {
                if (b.Length < 0x40 || b[0] != 'M' || b[1] != 'Z') return false;
                int pe = BitConverter.ToInt32(b, 0x3C);
                if (pe < 0 || pe + 24 > b.Length || b[pe] != 'P' || b[pe + 1] != 'E' || b[pe + 2] != 0 || b[pe + 3] != 0) return false;
                machine = BitConverter.ToUInt16(b, pe + 4);
                int nsec = BitConverter.ToUInt16(b, pe + 6);
                int optSize = BitConverter.ToUInt16(b, pe + 20);
                int opt = pe + 24;
                bool plus = BitConverter.ToUInt16(b, opt) == 0x20b;
                int numDirs = BitConverter.ToInt32(b, opt + (plus ? 108 : 92));
                if (numDirs < 2) return true;
                uint impRva = BitConverter.ToUInt32(b, opt + (plus ? 112 : 96) + 8);
                if (impRva == 0) return true;
                int secs = opt + optSize;
                Func<uint, int> off = rva =>
                {
                    for (int i = 0; i < nsec; i++)
                    {
                        int s = secs + 40 * i;
                        uint vs = BitConverter.ToUInt32(b, s + 8), va = BitConverter.ToUInt32(b, s + 12);
                        uint raw = BitConverter.ToUInt32(b, s + 16), ptr = BitConverter.ToUInt32(b, s + 20);
                        uint size = Math.Max(vs, raw);
                        if (rva >= va && rva < va + size) return (int)(rva - va + ptr);
                    }
                    return -1;
                };
                for (int d = off(impRva); d >= 0 && d + 20 <= b.Length && imports.Count < 1024; d += 20)
                {
                    uint nameRva = BitConverter.ToUInt32(b, d + 12), first = BitConverter.ToUInt32(b, d + 16);
                    if (nameRva == 0 && first == 0) break;
                    int n = off(nameRva);
                    if (n < 0) break;
                    int e = n;
                    while (e < b.Length && b[e] != 0) e++;
                    imports.Add(Encoding.ASCII.GetString(b, n, e - n));
                }
                return true;
            }
            catch { return true; }
        }

        internal static List<Req> Check(Func<string, bool> exists)
        {
            if (exists == null) exists = File.Exists;
            var reqs = new List<Req>();
            string os = OsArch();
            Version ver = OsVersion();
            reqs.Add(new Req { Level = Level.Ok, Text = "Windows " + ver + " on " + OsArchName(os) + "; this package: " + Info.Flavor });
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var files = Payload.List();
            foreach (var f in files) names.Add(Path.GetFileName(f.Name));
            var blocked = new List<string>();
            var missing = new SortedDictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
            foreach (var f in files)
            {
                string ext = Path.GetExtension(f.Name).ToLowerInvariant();
                if (ext != ".exe" && ext != ".dll") continue;
                ushort m; List<string> imps;
                if (!ParsePe(Payload.ReadAll(f), out m, out imps)) continue;
                if (imps.Count == 1 && Program.Eq(imps[0], "mscoree.dll")) continue;   // MSIL
                string why = CannotRun(m, os, ver);
                if (why != null) { blocked.Add(Path.GetFileName(f.Name) + " (" + MachineName(m) + "): " + why); continue; }
                foreach (var dll in imps)
                {
                    if (names.Contains(dll)) continue;
                    if (dll.StartsWith("api-ms-", StringComparison.OrdinalIgnoreCase) || dll.StartsWith("ext-ms-", StringComparison.OrdinalIgnoreCase)) continue;
                    if (exists(Path.Combine(SystemDirFor(m, os), dll))) continue;
                    List<string> users;
                    if (!missing.TryGetValue(dll, out users)) missing[dll] = users = new List<string>();
                    if (!users.Contains(Path.GetFileName(f.Name))) users.Add(Path.GetFileName(f.Name));
                }
            }
            if (blocked.Count > 0)
                reqs.Add(new Req
                {
                    Level = Level.Blocked,
                    Text = "This package's programs cannot run on this PC:\n    " + string.Join("\n    ", blocked.ToArray()),
                    Fix = "Use the MDM RT package for this PC's processor."
                });
            foreach (var kv in missing)
                reqs.Add(new Req { Level = Level.Missing, Text = "Windows component " + kv.Key + " is missing - needed by " + string.Join(", ", kv.Value.ToArray()), Fix = "This Windows edition lacks it; the program that needs it will not start" });
            if (blocked.Count == 0 && missing.Count == 0)
                reqs.Add(new Req { Level = Level.Ok, Text = "Windows components the programs use: all present (static C runtime, no redistributable needed)" });
            if (names.Contains("libGLESv2.dll"))
            {
                string sys = SystemDirFor(ArmNt, os);
                bool d3d9 = exists(Path.Combine(sys, "d3d9.dll")), d3d11 = exists(Path.Combine(sys, "d3d11.dll"));
                reqs.Add(d3d9 || d3d11
                    ? new Req { Level = Level.Ok, Text = "Drawing: OpenGL ES through ANGLE on Direct3D " + (d3d11 ? "11" : "") + (d3d9 && d3d11 ? " / " : "") + (d3d9 ? "9" : "") + " (the graphics chip's driver)" }
                    : new Req { Level = Level.Missing, Text = "Neither Direct3D 9 nor Direct3D 11 is installed: MDM RT's window cannot be drawn" });
            }
            if (names.Contains(@"helpers\yt-dlp.exe") || names.Contains("yt-dlp.exe"))
                reqs.Add(new Req { Level = Level.Ok, Text = "Video helpers: yt-dlp (with its own Python), QuickJS and ffmpeg come with this package" });
            reqs.Add(new Req { Level = Level.Ok, Text = "Browser integration: registered for this user (Venetium, Chrome, Edge, Brave, Firefox); no admin rights needed" });
            return reqs;
        }

        internal static int ExitCode(List<Req> reqs)
        {
            int code = 0;
            foreach (var r in reqs)
            {
                if (r.Level == Level.Blocked) return 2;
                if (r.Level == Level.Missing || r.Level == Level.Warn) code = 3;
            }
            return code;
        }

        internal static string Tag(Level l)
        {
            switch (l) { case Level.Ok: return "[ OK ]"; case Level.Warn: return "[WARN]"; case Level.Missing: return "[MISSING]"; default: return "[CANNOT RUN]"; }
        }

        internal static string Format(List<Req> reqs)
        {
            var sb = new StringBuilder();
            foreach (var r in reqs)
            {
                sb.Append(Tag(r.Level)).Append(' ').Append(r.Text.Replace("\n", "\r\n")).Append("\r\n");
                if (r.Fix != null) sb.Append("      -> ").Append(r.Fix).Append("\r\n");
                if (r.Url != null) sb.Append("      ").Append(r.Url).Append("\r\n");
            }
            return sb.ToString();
        }
    }

    // -- files in use: MDM RT or its helpers running from the install folder -----------------------------------
    internal static class InUse
    {
        [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr OpenProcess(int access, bool inherit, int pid);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool QueryFullProcessImageName(IntPtr h, int flags, StringBuilder name, ref int size);
        [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr h);
        private const int PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;

        private static string ImagePath(Process p)
        {
            IntPtr h = IntPtr.Zero;
            try
            {
                h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, p.Id);
                if (h == IntPtr.Zero) return null;
                var sb = new StringBuilder(1024); int n = sb.Capacity;
                return QueryFullProcessImageName(h, 0, sb, ref n) ? sb.ToString() : null;
            }
            catch { return null; }
            finally { if (h != IntPtr.Zero) CloseHandle(h); }
        }

        /// <summary>Null when nothing of MDM RT runs from <paramref name="dir"/>, else a sentence saying what does.
        /// They are the user's to close; nothing is ever killed.</summary>
        internal static string Check(string dir)
        {
            if (!Directory.Exists(dir)) return null;
            string full;
            try { full = Path.GetFullPath(dir).TrimEnd('\\') + "\\"; } catch { return null; }
            foreach (var name in new[] { Program.ExeName, Program.HostExe })
            {
                string exe = Path.Combine(full, name);
                if (!File.Exists(exe)) continue;
                try { using (new FileStream(exe, FileMode.Open, FileAccess.ReadWrite, FileShare.Read)) { } }
                catch (IOException ex) when (!(ex is FileNotFoundException) && !(ex is DirectoryNotFoundException))
                { return Program.AppName + " (" + name + ") is running from " + dir + "."; }
                catch { }
            }
            foreach (var pn in Program.ProcessNames)
                foreach (var p in Process.GetProcessesByName(pn))
                {
                    try
                    {
                        if (p.Id == Process.GetCurrentProcess().Id) continue;
                        string img = ImagePath(p);
                        if (img != null && img.StartsWith(full, StringComparison.OrdinalIgnoreCase))
                            return Program.AppName + " (" + Path.GetFileName(img) + ") is running from " + dir + ".";
                    }
                    finally { p.Dispose(); }
                }
            return null;
        }
    }

    /// <summary>Where Setup may write and what it may delete (Venetium's folder guard, CS-Ray review finding #1/#2).</summary>
    internal static class SafeTarget
    {
        internal static string Problem(string dir)
        {
            string full;
            try { full = Path.GetFullPath((dir ?? "").Trim()).TrimEnd('\\'); }
            catch (Exception ex) { return "Not a usable folder: " + ex.Message; }
            if (full.Length == 0) return "Choose an install folder.";
            if (full.IndexOfAny(new[] { '%', '^', '&' }) >= 0) return "The folder name can't contain %, ^ or &.";   // the clean-up command is cmd
            string root = (Path.GetPathRoot(full) ?? "").TrimEnd('\\');
            if (root.Length == 0 || root.Equals(full, StringComparison.OrdinalIgnoreCase)) return "Choose a folder for " + Program.AppName + ", not a whole drive.";
            foreach (var f in Protected())
                if (f.Equals(full, StringComparison.OrdinalIgnoreCase))
                    return full + " is a system or personal folder. Choose a folder of its own, e.g. " + Path.Combine(full, Program.InstallFolderName) + ".";
            if (!Directory.Exists(full) || IsEmpty(full) || IsInstalledCopy(full)) return null;
            return full + " already holds other files. Choose an empty folder, or the folder " + Program.AppName + " is installed in.";
        }

        internal static bool IsInstalledCopy(string dir)
        {
            try { return File.Exists(Path.Combine(dir, "uninstall.exe")) && File.Exists(Path.Combine(dir, Program.ExeName)); }
            catch { return false; }
        }

        private static bool IsEmpty(string dir)
        {
            try { using (var e = Directory.EnumerateFileSystemEntries(dir).GetEnumerator()) return !e.MoveNext(); }
            catch { return false; }
        }

        private static IEnumerable<string> Protected()
        {
            var sf = new[]
            {
                Environment.SpecialFolder.Windows, Environment.SpecialFolder.System, Environment.SpecialFolder.ProgramFiles,
                Environment.SpecialFolder.ProgramFilesX86, Environment.SpecialFolder.UserProfile, Environment.SpecialFolder.DesktopDirectory,
                Environment.SpecialFolder.MyDocuments, Environment.SpecialFolder.MyMusic, Environment.SpecialFolder.MyPictures,
                Environment.SpecialFolder.MyVideos, Environment.SpecialFolder.ApplicationData, Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolder.CommonApplicationData, Environment.SpecialFolder.Programs, Environment.SpecialFolder.StartMenu,
                Environment.SpecialFolder.Startup, Environment.SpecialFolder.Favorites,
            };
            var list = new List<string>();
            foreach (var f in sf)
            {
                try { string p = Environment.GetFolderPath(f); if (!string.IsNullOrEmpty(p)) list.Add(Path.GetFullPath(p).TrimEnd('\\')); } catch { }
            }
            try
            {
                string profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                if (!string.IsNullOrEmpty(profile)) list.Add(Path.Combine(profile, "Downloads"));
                string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if (!string.IsNullOrEmpty(local)) list.Add(Path.Combine(local, "Programs"));
            }
            catch { }
            return list;
        }
    }

    // -- registry helpers (HKCU only) -------------------------------------------------------------------------
    internal static class Reg
    {
        internal static string Get(string key, string name)
        {
            try { using (var k = Registry.CurrentUser.OpenSubKey(key)) return k != null ? k.GetValue(name) as string : null; }
            catch { return null; }
        }

        internal static void DeleteValue(string key, string name)
        {
            try { using (var k = Registry.CurrentUser.OpenSubKey(key, true)) if (k != null) k.DeleteValue(name, false); }
            catch { }
        }

        internal static void DeleteTree(string key)
        {
            try { Registry.CurrentUser.DeleteSubKeyTree(key, false); } catch { }
        }
    }

    /// <summary>The browsers' native messaging host (misterdownloadmanager-nmhost.exe writes and removes it).</summary>
    internal static class Browser
    {
        internal const string HostName = "com.misterdownloadmanager.host";
        private static readonly string[] Keys =
        {
            @"Software\Chromium\NativeMessagingHosts", @"Software\Google\Chrome\NativeMessagingHosts",
            @"Software\Microsoft\Edge\NativeMessagingHosts", @"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
            @"Software\Mozilla\NativeMessagingHosts",
        };

        /// <summary>The manifest the browsers find for the host (Chromium's key first, as Venetium reads it).</summary>
        internal static string Registered()
        {
            foreach (var k in Keys)
            {
                string v = Reg.Get(k + "\\" + HostName, "");
                if (!string.IsNullOrEmpty(v)) return v;
            }
            return null;
        }

        /// <summary>Runs the host program with --register / --unregister; true when it said so (exit code 0).</summary>
        internal static bool Run(string dir, string arg)
        {
            string exe = Path.Combine(dir, Program.HostExe);
            if (!File.Exists(exe)) return false;
            try
            {
                var psi = new ProcessStartInfo(exe, arg) { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = dir };
                using (var p = Process.Start(psi))
                {
                    if (!p.WaitForExit(60000)) return false;
                    return p.ExitCode == 0;
                }
            }
            catch { return false; }
        }

        /// <summary>Removes the registration when it is this folder's (another copy, or upstream MDM, keeps its own).</summary>
        internal static void UnregisterIfOurs(string dir)
        {
            if (!Uninstaller.Inside(Registered(), dir)) return;
            if (Run(dir, "--unregister")) return;
            foreach (var k in Keys)   // the host program is missing: its keys by hand, only those naming this folder
                if (Uninstaller.Inside(Reg.Get(k + "\\" + HostName, ""), dir)) Reg.DeleteTree(k + "\\" + HostName);
            foreach (var f in new[] { HostName + ".json", HostName + ".firefox.json" })
                try { File.Delete(Path.Combine(dir, f)); } catch { }
        }
    }

    /// <summary>The startup entry (HKCU Run "MDM RT"), the same value MDM RT's Options > "Launch on startup" writes.</summary>
    internal static class Startup
    {
        private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string Value = "MDM RT";

        internal static void Set(string exe)
        {
            using (var k = Registry.CurrentUser.CreateSubKey(RunKey)) k.SetValue(Value, "\"" + exe + "\" /startup");
        }

        internal static bool IsOurs(string dir)
        {
            string v = Reg.Get(RunKey, Value);
            if (string.IsNullOrEmpty(v)) return false;
            string exe = v.StartsWith("\"") ? v.Substring(1, Math.Max(0, v.IndexOf('"', 1) - 1)) : v.Split(' ')[0];
            return Uninstaller.Inside(exe, dir);
        }

        internal static void RemoveIfOurs(string dir) { if (IsOurs(dir)) Reg.DeleteValue(RunKey, Value); }
    }

    /// <summary>What MDM RT itself may have registered from its Options: .torrent files (ProgID MDMRT.Torrent) and
    /// magnet links. Uninstall removes them when they open this folder's program.</summary>
    internal static class MdmAssoc
    {
        internal static void RemoveIfOurs(string dir)
        {
            const string progId = @"Software\Classes\MDMRT.Torrent";
            if (Uninstaller.Inside(CommandExe(Reg.Get(progId + @"\shell\open\command", "")), dir) || Reg.Get(progId + @"\shell\open\command", "") == null)
            {
                Reg.DeleteTree(progId);
                if (Program.Eq(Reg.Get(@"Software\Classes\.torrent", ""), "MDMRT.Torrent"))
                    try { using (var k = Registry.CurrentUser.OpenSubKey(@"Software\Classes\.torrent", true)) if (k != null) k.DeleteValue("", false); } catch { }
            }
            if (Uninstaller.Inside(CommandExe(Reg.Get(@"Software\Classes\magnet\shell\open\command", "")), dir))
                Reg.DeleteTree(@"Software\Classes\magnet");
        }

        private static string CommandExe(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return null;
            cmd = cmd.Trim();
            if (cmd.StartsWith("\"")) { int e = cmd.IndexOf('"', 1); return e > 1 ? cmd.Substring(1, e - 1) : null; }
            return cmd.Split(' ')[0];
        }
    }

    internal static class Locked
    {
        private const string RunOnce = @"Software\Microsoft\Windows\CurrentVersion\RunOnce";
        private const string ValueName = "MDM RT clean-up";

        /// <summary>Deletes <paramref name="path"/>; when it is in use, renames it to *.rtold beside it and asks
        /// Windows to delete it at the next sign-in. False when it could neither be deleted nor renamed.</summary>
        internal static bool DeleteOrRetire(string path)
        {
            if (!File.Exists(path)) return true;
            try { File.Delete(path); return true; }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            try
            {
                string old = path + "." + DateTime.UtcNow.Ticks.ToString("x") + ".rtold";
                File.Move(path, old);
                ScheduleCleanup(Path.GetDirectoryName(path));
                return true;
            }
            catch { return false; }
        }

        internal static void ScheduleCleanup(string dir)
        {
            try
            {
                using (var k = Registry.CurrentUser.CreateSubKey(RunOnce))
                    k.SetValue(ValueName, "cmd.exe /c del /f /q \"" + Path.Combine(dir, "*.rtold") + "\" & rmdir \"" + dir + "\"");
            }
            catch { }
        }

        /// <summary>Old *.rtold files of an earlier upgrade that can go now.</summary>
        internal static void CleanOld(string dir)
        {
            try { foreach (var f in Directory.GetFiles(dir, "*.rtold", SearchOption.AllDirectories)) try { File.Delete(f); } catch { } } catch { }
        }
    }

    internal static class Installer
    {
        internal static void Install(string targetDir, Options opt, Action<string> progress)
        {
            Report(progress, "Preparing...");
            string refused = SafeTarget.Problem(targetDir);
            if (refused != null) throw new InvalidOperationException(refused);
            targetDir = Path.GetFullPath(targetDir.Trim()).TrimEnd('\\');
            var files = Payload.List();
            if (!files.Exists(f => Program.Eq(f.Name, Program.ExeName))) throw new InvalidDataException("This Setup carries no " + Program.ExeName + ".");

            // PASS 1 - verify the whole package before touching the folder
            Report(progress, "Checking the package...");
            using (var sha = SHA256.Create())
                foreach (var f in files)
                {
                    byte[] h;
                    using (var src = Payload.Open(f)) h = sha.ComputeHash(src);
                    if (!string.Equals(Payload.Hex(h), f.Sha256, StringComparison.OrdinalIgnoreCase))
                        throw new InvalidDataException(f.Name + " in this Setup is damaged (SHA-256 " + Payload.Hex(h) + ", expected " + f.Sha256 + "). Download Setup again.");
                }

            // PASS 2 - each file as <name>.new, verified, then swapped in. A file in use is renamed to *.rtold and
            // removed at the next sign-in.
            Directory.CreateDirectory(targetDir);
            Locked.CleanOld(targetDir);
            int i = 0;
            using (var sha = SHA256.Create())
                foreach (var f in files)
                {
                    Report(progress, "Installing " + (++i) + " of " + files.Count + ": " + f.Name);
                    string dest = Path.Combine(targetDir, f.Name);
                    string d = Path.GetDirectoryName(dest);
                    if (!string.IsNullOrEmpty(d)) Directory.CreateDirectory(d);
                    string tmp = dest + ".new";
                    try
                    {
                        byte[] h;
                        using (var src = Payload.Open(f))
                        using (var os = new FileStream(tmp, FileMode.Create, FileAccess.Write, FileShare.None))
                        using (var cs = new CryptoStream(os, sha, CryptoStreamMode.Write))
                        {
                            Payload.Copy(src, cs);
                            cs.FlushFinalBlock();
                            h = sha.Hash;
                        }
                        sha.Initialize();
                        if (!string.Equals(Payload.Hex(h), f.Sha256, StringComparison.OrdinalIgnoreCase))
                            throw new InvalidDataException(f.Name + " did not extract intact (SHA-256 " + Payload.Hex(h) + ", expected " + f.Sha256 + ").");
                        if (!Locked.DeleteOrRetire(dest))
                            throw new IOException(dest + " is in use and cannot be replaced. Close the program that uses it, then try again.");
                        File.Move(tmp, dest);
                    }
                    catch
                    {
                        try { if (File.Exists(tmp)) File.Delete(tmp); } catch { }
                        throw;
                    }
                }

            string exe = Path.Combine(targetDir, Program.ExeName);
            string uninst = Path.Combine(targetDir, "uninstall.exe");
            if (opt.Colour >= 0) Colours.Save(opt.Colour);

            Report(progress, "Creating shortcuts...");
            File.Copy(Application.ExecutablePath, uninst, true);
            string menu = Program.StartMenuFolder();
            Directory.CreateDirectory(menu);
            Shortcut.Create(Path.Combine(menu, Program.AppName + ".lnk"), exe, null, targetDir, exe, 0, Program.ShortcutDesc);
            string desktopLnk = Existing.DesktopLink();
            if (opt.Desktop) Shortcut.Create(desktopLnk, exe, null, targetDir, exe, 0, Program.ShortcutDesc);
            else Uninstaller.RemoveShortcutIfOurs(desktopLnk, targetDir);   // an update without the desktop shortcut

            Report(progress, "Registering...");
            using (var k = Registry.CurrentUser.CreateSubKey(Program.AppKey)) k.SetValue("Path", targetDir + "\\");
            if (opt.Browser)
            {
                Report(progress, "Registering the browser host...");
                if (!Browser.Run(targetDir, "--register"))
                    throw new InvalidOperationException("The browser host (" + Program.HostExe + " --register) did not register. MDM RT is installed; run Setup again to retry.");
            }
            else Browser.UnregisterIfOurs(targetDir);
            if (opt.Startup) Startup.Set(exe);
            else Startup.RemoveIfOurs(targetDir);
            RegisterUninstall(targetDir, exe, uninst);
            Report(progress, "Done.");
        }

        private static void RegisterUninstall(string dir, string displayIcon, string uninst)
        {
            try
            {
                using (var k = Registry.CurrentUser.CreateSubKey(Program.UninstallKey))
                {
                    if (k == null) return;
                    k.SetValue("DisplayName", Program.AppName);
                    k.SetValue("DisplayVersion", Info.AppVersion);
                    k.SetValue("Publisher", Program.Publisher);
                    k.SetValue("Comments", "unofficial fork of Mister Download Manager by Ahmed Nefzaoui; " + Info.Flavor + " package");
                    k.SetValue("URLInfoAbout", "https://github.com/hamed7ir/mdm-rt");
                    k.SetValue("DisplayIcon", displayIcon);
                    k.SetValue("InstallLocation", dir);
                    k.SetValue("UninstallString", "\"" + uninst + "\" --uninstall \"" + dir + "\"");
                    k.SetValue("QuietUninstallString", "\"" + uninst + "\" --uninstall \"" + dir + "\" --silent");
                    k.SetValue("NoModify", 1, RegistryValueKind.DWord);
                    k.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                    try { k.SetValue("EstimatedSize", (int)DirSizeKB(dir), RegistryValueKind.DWord); } catch { }
                }
            }
            catch { }
        }

        private static long DirSizeKB(string dir)
        {
            long total = 0;
            foreach (var f in Directory.GetFiles(dir, "*", SearchOption.AllDirectories))
                try { total += new FileInfo(f).Length; } catch { }
            return total / 1024;
        }

        private static void Report(Action<string> p, string s) { if (p != null) p(s); }
    }

    /// <summary>The files Setup owns in an install folder: the payload's, uninstall.exe, and *.new / *.rtold leftovers.</summary>
    internal static class Owned
    {
        internal static void RemoveAll(string dir, List<PayloadFile> files)
        {
            foreach (var f in files)
            {
                Locked.DeleteOrRetire(Path.Combine(dir, f.Name));
                Del(Path.Combine(dir, f.Name + ".new"));
            }
            Locked.CleanOld(dir);
            RemoveEmptySubdirs(dir, files);
        }

        private static void RemoveEmptySubdirs(string dir, List<PayloadFile> files)
        {
            string root;
            try { root = Path.GetFullPath(dir).TrimEnd('\\'); } catch { return; }
            var subs = new List<string>();
            foreach (var f in files)
            {
                string d;
                try { d = Path.GetFullPath(Path.GetDirectoryName(Path.Combine(root, f.Name))).TrimEnd('\\'); } catch { continue; }
                while (!string.IsNullOrEmpty(d) && !d.Equals(root, StringComparison.OrdinalIgnoreCase) &&
                       d.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase))
                {
                    if (!subs.Exists(s => s.Equals(d, StringComparison.OrdinalIgnoreCase))) subs.Add(d);
                    try { d = Path.GetDirectoryName(d).TrimEnd('\\'); } catch { break; }
                }
            }
            subs.Sort((a, b) => b.Length.CompareTo(a.Length));
            foreach (var sub in subs) { try { Directory.Delete(sub, false); } catch { } }
        }

        private static void Del(string f) { try { if (File.Exists(f)) File.Delete(f); } catch { } }
    }

    internal static class Uninstaller
    {
        internal static bool Run(string dir)
        {
            if (!SafeTarget.IsInstalledCopy(dir)) return false;
            // only what points INTO this folder: another copy of MDM RT, or upstream MDM, may own the same names
            Browser.UnregisterIfOurs(dir);
            Startup.RemoveIfOurs(dir);
            MdmAssoc.RemoveIfOurs(dir);
            string menu = Program.StartMenuFolder();
            RemoveShortcutIfOurs(Path.Combine(menu, Program.AppName + ".lnk"), dir);
            try { Directory.Delete(menu, false); } catch { }   // only if empty now
            RemoveShortcutIfOurs(Existing.DesktopLink(), dir);
            string path = Reg.Get(Program.AppKey, "Path");
            if (path == null || Inside(path, dir))
                Reg.DeleteTree(Program.AppKey);   // Path, an unused InstallTheme / InstallLanguage
            RemoveUninstallKeyIfOurs(dir);
            Owned.RemoveAll(dir, Payload.List());
            SelfDeleteDir(dir);
            return true;
        }

        internal static bool Inside(string path, string dir)
        {
            if (string.IsNullOrEmpty(path) || string.IsNullOrEmpty(dir)) return false;
            try
            {
                string d = Path.GetFullPath(dir).TrimEnd('\\');
                string p = Path.GetFullPath(path.Trim().Trim('"')).TrimEnd('\\');
                return p.Equals(d, StringComparison.OrdinalIgnoreCase) || p.StartsWith(d + "\\", StringComparison.OrdinalIgnoreCase);
            }
            catch { return false; }
        }

        internal static void RemoveShortcutIfOurs(string lnk, string dir)
        {
            try { if (File.Exists(lnk) && Inside(Shortcut.TargetOf(lnk), dir)) File.Delete(lnk); } catch { }
        }

        private static void RemoveUninstallKeyIfOurs(string dir)
        {
            try
            {
                string loc;
                using (var k = Registry.CurrentUser.OpenSubKey(Program.UninstallKey))
                    loc = k != null ? k.GetValue("InstallLocation") as string : null;
                if (Inside(loc, dir) && Inside(dir, loc)) Registry.CurrentUser.DeleteSubKeyTree(Program.UninstallKey);
            }
            catch { }
        }

        private static void SelfDeleteDir(string dir)
        {
            try
            {
                // uninstall.exe may run from inside the folder: a detached cmd tries once a second, for up to 15 s, to
                // delete it (it is locked until this process has ended), then removes the folder only if it is empty
                // now (rmdir without /s). Its working folder is System32, never the folder.
                string u = Path.Combine(dir, "uninstall.exe");
                var psi = new ProcessStartInfo("cmd.exe",
                    "/c for /l %i in (1,1,15) do (ping 127.0.0.1 -n 2 >nul & del /f /q \"" + u + "\" 2>nul & " +
                    "if not exist \"" + u + "\" (rmdir \"" + dir + "\" 2>nul & exit /b 0))");
                psi.WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System);
                psi.CreateNoWindow = true; psi.UseShellExecute = false; psi.WindowStyle = ProcessWindowStyle.Hidden;
                Process.Start(psi);
            }
            catch { }
        }
    }

    /// <summary>Creates and reads .lnk files through the shell's IShellLink COM object (works on the RT desktop).</summary>
    internal static class Shortcut
    {
        internal static void Create(string lnkPath, string target, string args, string workDir, string iconPath, int iconIndex, string desc)
        {
            try
            {
                var link = (IShellLinkW)new CShellLink();
                link.SetPath(target);
                if (!string.IsNullOrEmpty(args)) link.SetArguments(args);
                if (!string.IsNullOrEmpty(workDir)) link.SetWorkingDirectory(workDir);
                if (!string.IsNullOrEmpty(iconPath)) link.SetIconLocation(iconPath, iconIndex);
                if (!string.IsNullOrEmpty(desc)) link.SetDescription(desc);
                ((IPersistFile)link).Save(lnkPath, true);
            }
            catch { }
        }

        internal static string TargetOf(string lnkPath)
        {
            try
            {
                var link = (IShellLinkW)new CShellLink();
                ((IPersistFile)link).Load(lnkPath, 0);
                var sb = new StringBuilder(1024);
                link.GetPath(sb, sb.Capacity, IntPtr.Zero, 0);
                return sb.Length > 0 ? sb.ToString() : null;
            }
            catch { return null; }
        }

        [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
        private class CShellLink { }

        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
        private interface IShellLinkW
        {
            void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, int fFlags);
            void GetIDList(out IntPtr ppidl);
            void SetIDList(IntPtr pidl);
            void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cch);
            void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
            void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cch);
            void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
            void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cch);
            void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
            void GetHotkey(out short pwHotkey);
            void SetHotkey(short wHotkey);
            void GetShowCmd(out int piShowCmd);
            void SetShowCmd(int iShowCmd);
            void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cch, out int piIcon);
            void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
            void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, int dwReserved);
            void Resolve(IntPtr hwnd, int fFlags);
            void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
        }

        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("0000010b-0000-0000-C000-000000000046")]
        private interface IPersistFile
        {
            void GetClassID(out Guid pClassID);
            [PreserveSig] int IsDirty();
            void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, int dwMode);
            void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
            void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
            void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string ppszFileName);
        }
    }

    /// <summary>The install wizard, dark with Kodi RT purple like the program. "Check requirements" only informs.</summary>
    internal sealed class InstallForm : Form
    {
        private readonly TextBox _path, _reqs;
        private readonly CheckBox _browser, _startup, _desktop;
        private readonly Button _install, _cancel, _browse, _check;
        private readonly Label _status;
        private readonly ProgressBar _bar;
        private readonly ComboBox _colour;
        private readonly PictureBox _preview;
        private readonly Image _logo;      // the program icon, 48 px, purple: the preview shows it in the colour
        private readonly bool _update;
        private static readonly Color Back = Color.FromArgb(0x1a, 0x0b, 0x33);
        private static readonly Color Field = Color.FromArgb(0x2a, 0x11, 0x50);
        private static readonly Color Accent = Color.FromArgb(0x6b, 0x3a, 0xa8);
        private static readonly Color Text1 = Color.FromArgb(0xee, 0xe6, 0xfa);
        private static readonly Color Dim = Color.FromArgb(0x9d, 0x8b, 0xb8);
        private bool _busy;

        private Button MakeButton(string text, int left, int top, int width)
        {
            var b = new Button { Left = left, Top = top, Width = width, Height = 28, Text = text, FlatStyle = FlatStyle.Flat, BackColor = Field, ForeColor = Text1 };
            b.FlatAppearance.BorderColor = Accent;
            return b;
        }

        public InstallForm()
        {
            // an update: MDM RT is installed already (the uninstall entry's folder) - keep its folder and choices
            string existing = Existing.Dir();
            string oldVersion = existing != null ? Existing.Version() : null;
            _update = existing != null;

            Text = Program.AppName + " " + Info.AppVersion + " (" + Info.Flavor + ") Setup";
            try { using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("setup.icon.ico")) if (s != null) Icon = new Icon(s); } catch { }
            try { using (var s = Assembly.GetExecutingAssembly().GetManifestResourceStream("setup.icon.ico")) if (s != null) _logo = new Icon(s, 48, 48).ToBitmap(); } catch { }
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(560, 516);
            BackColor = Back; ForeColor = Text1;
            Font = new Font("Segoe UI", 9f);

            var header = new Panel { Dock = DockStyle.Top, Height = 64, BackColor = Accent };
            string head = existing != null ? "Update " + Program.AppName + " to " + Info.AppVersion : "Install " + Program.AppName + " " + Info.AppVersion;
            var title = new Label { Dock = DockStyle.Fill, ForeColor = Color.White, Font = new Font("Segoe UI", 14f, FontStyle.Bold), TextAlign = ContentAlignment.MiddleLeft, Padding = new Padding(18, 0, 0, 0), Text = head };
            header.Controls.Add(title);
            string subText = existing != null
                ? "installed: " + (oldVersion ?? "an earlier version") + " - same folder and choices as before, your list and settings stay"
                : "unofficial fork of Mister Download Manager by Ahmed Nefzaoui - per user, no admin needed";
            var sub = new Label { Left = 18, Top = 72, Width = 524, Height = 18, ForeColor = Dim, Text = subText };

            var lbl = new Label { Left = 18, Top = 98, Width = 524, Height = 18, Text = "Install location:" };
            _path = new TextBox { Left = 18, Top = 118, Width = 430, Text = existing ?? Program.DefaultDir(), BackColor = Field, ForeColor = Text1, BorderStyle = BorderStyle.FixedSingle };
            _browse = MakeButton("Browse...", 458, 115, 84);
            _browse.Click += (s, e) => { using (var d = new FolderBrowserDialog()) { try { d.SelectedPath = _path.Text; } catch { } if (d.ShowDialog(this) == DialogResult.OK) _path.Text = Path.Combine(d.SelectedPath, Program.InstallFolderName); } };
            bool browserOn = existing == null || Uninstaller.Inside(Browser.Registered(), existing);
            bool startupOn = existing != null && Startup.IsOurs(existing);
            bool desktopOn = existing != null && File.Exists(Existing.DesktopLink()) && Uninstaller.Inside(Shortcut.TargetOf(Existing.DesktopLink()), existing);
            _browser = new CheckBox { Left = 18, Top = 152, Width = 524, Text = "Let browsers hand downloads to MDM RT (Venetium, Chrome, Edge, Brave, Firefox)", Checked = browserOn };
            _startup = new CheckBox { Left = 18, Top = 176, Width = 524, Text = "Start MDM RT with Windows (it waits in the notification area)", Checked = startupOn };
            _desktop = new CheckBox { Left = 18, Top = 200, Width = 524, Text = "Create a desktop shortcut", Checked = desktopOn };

            // the colour: one of MDM RT's RT themes, for its next start
            var cl = new Label { Left = 18, Top = 238, Width = 60, Height = 18, Text = "Colour:" };
            _colour = new ComboBox { Left = 80, Top = 234, Width = 210, DropDownStyle = ComboBoxStyle.DropDownList, DrawMode = DrawMode.OwnerDrawFixed, ItemHeight = 18, BackColor = Field, ForeColor = Text1, FlatStyle = FlatStyle.Flat };
            if (_update) _colour.Items.Add("Keep my theme");
            foreach (var n in Colours.Names) _colour.Items.Add(n);
            _colour.SelectedIndex = 0;
            _colour.DrawItem += DrawColourItem;
            _colour.SelectedIndexChanged += (s, e) => UpdatePreview();
            _preview = new PictureBox { Left = 306, Top = 222, Width = 48, Height = 48, SizeMode = PictureBoxSizeMode.CenterImage };
            var cn = new Label { Left = 362, Top = 222, Width = 182, Height = 54, ForeColor = Dim, Text = "the RT theme MDM RT starts with (View > Theme changes it later)" };

            var rl = new Label { Left = 18, Top = 280, Width = 524, Height = 18, Text = "Requirements (optional check - installing does not depend on it):" };
            _reqs = new TextBox { Left = 18, Top = 300, Width = 524, Height = 120, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = Field, ForeColor = Text1, BorderStyle = BorderStyle.FixedSingle, Font = new Font("Consolas", 8.5f),
                                  Text = "Press \"Check requirements\" to see whether this PC can run " + Program.AppName + "." };
            _status = new Label { Left = 18, Top = 428, Width = 524, Height = 18, ForeColor = Dim, Text = "" };
            _bar = new ProgressBar { Left = 18, Top = 448, Width = 524, Height = 14, Style = ProgressBarStyle.Marquee, Visible = false, MarqueeAnimationSpeed = 30 };
            _check = MakeButton("Check requirements", 18, 474, 150);
            _install = MakeButton(existing != null ? "Update" : "Install", 380, 474, 84);
            _cancel = MakeButton("Cancel", 468, 474, 74);
            _check.Click += (s, e) => RunCheck();
            _install.Click += OnInstall;
            _cancel.Click += (s, e) => Close();

            Controls.Add(header); Controls.Add(sub);
            Controls.Add(lbl); Controls.Add(_path); Controls.Add(_browse);
            Controls.Add(_browser); Controls.Add(_startup); Controls.Add(_desktop);
            Controls.Add(cl); Controls.Add(_colour); Controls.Add(_preview); Controls.Add(cn);
            Controls.Add(rl); Controls.Add(_reqs);
            Controls.Add(_status); Controls.Add(_bar); Controls.Add(_check); Controls.Add(_install); Controls.Add(_cancel);
            AcceptButton = _install; CancelButton = _cancel;
            FormClosing += (s, e) => { if (_busy && e.CloseReason == CloseReason.UserClosing) e.Cancel = true; };
            UpdatePreview();
        }

        /// <summary>The preset an item stands for; -1 for "Keep my theme" (an update).</summary>
        private int PresetOfItem(int item)
        {
            return _update ? item - 1 : item;
        }

        private void DrawColourItem(object sender, DrawItemEventArgs e)
        {
            if (e.Index < 0) return;
            bool selected = (e.State & DrawItemState.Selected) != 0 && (e.State & DrawItemState.ComboBoxEdit) == 0;
            using (var bg = new SolidBrush(selected ? Accent : Field)) e.Graphics.FillRectangle(bg, e.Bounds);
            int preset = PresetOfItem(e.Index);
            var sw = new Rectangle(e.Bounds.Left + 4, e.Bounds.Top + 3, 22, e.Bounds.Height - 6);
            if (preset >= 0) using (var b = new SolidBrush(Colours.ColorOf(Colours.Rgb[preset]))) e.Graphics.FillRectangle(b, sw);
            TextRenderer.DrawText(e.Graphics, _colour.Items[e.Index].ToString(), Font, new Point(sw.Right + 8, e.Bounds.Top + 1), Text1);
        }

        private void UpdatePreview()
        {
            if (_logo == null) return;
            var old = _preview.Image;
            _preview.Image = Colours.Tint(_logo, Math.Max(0, PresetOfItem(_colour.SelectedIndex)));
            if (old != null) old.Dispose();
        }

        private void RunCheck()
        {
            _status.Text = "Checking requirements...";
            _check.Enabled = false;
            _bar.Visible = true;
            var t = new Thread(() =>
            {
                List<Req> rep = null; Exception err = null;
                try { rep = Requirements.Check(null); } catch (Exception ex) { err = ex; }
                try
                {
                    BeginInvoke((Action)(() =>
                    {
                        if (!_busy) { _bar.Visible = false; _check.Enabled = true; }
                        if (err != null) { _reqs.Text = "The check failed: " + err.Message; _status.Text = ""; return; }
                        _reqs.Text = Requirements.Format(rep);
                        int code = Requirements.ExitCode(rep);
                        _status.Text = code == 0 ? "Everything needed is present."
                                     : code == 2 ? "This package's programs cannot run on this PC - see above. Installing is still allowed."
                                     : "Something is missing - see above. Installing is still allowed.";
                    }));
                }
                catch { }
            }) { IsBackground = true };
            t.Start();
        }

        private void OnInstall(object sender, EventArgs e)
        {
            string dir = (_path.Text ?? "").Trim();
            if (string.IsNullOrEmpty(dir)) { MessageBox.Show(this, "Choose an install location."); return; }
            string refused = SafeTarget.Problem(dir);
            if (refused != null) { MessageBox.Show(this, refused, "Setup", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
            string busy;
            while ((busy = InUse.Check(dir)) != null)
                if (MessageBox.Show(this, busy + "\n\nClose all its windows (and the MDM RT icon in the notification area), then press Retry.", "Setup", MessageBoxButtons.RetryCancel, MessageBoxIcon.Warning) != DialogResult.Retry) return;
            var opt = new Options { Browser = _browser.Checked, Startup = _startup.Checked, Desktop = _desktop.Checked, Colour = PresetOfItem(_colour.SelectedIndex) };
            SetBusy(true);
            var t = new Thread(() =>
            {
                Exception err = null;
                try { Installer.Install(dir, opt, msg => { try { BeginInvoke((Action)(() => _status.Text = msg)); } catch { } }); }
                catch (Exception ex) { err = ex; }
                try { BeginInvoke((Action)(() => Finished(dir, err, opt))); } catch { }
            }) { IsBackground = true };
            t.Start();
        }

        private void Finished(string dir, Exception err, Options opt)
        {
            SetBusy(false);
            if (err != null)
            {
                MessageBox.Show(this, "Install failed:\n\n" + err.Message, "Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }
            string hint = opt.Browser ? "\n\nTo catch downloads in Venetium or Chrome: install \"Mister Download Manager\" from the Chrome Web Store, then restart the browser." : "";
            if (MessageBox.Show(this, Program.AppName + " was installed." + hint + "\n\nOpen MDM RT now?", "Setup",
                MessageBoxButtons.YesNo, MessageBoxIcon.Information) == DialogResult.Yes)
                try { Process.Start(Path.Combine(dir, Program.ExeName)); } catch { }
            Close();
        }

        private void SetBusy(bool busy)
        {
            _busy = busy;
            _install.Enabled = _cancel.Enabled = _browse.Enabled = _path.Enabled = _check.Enabled = !busy;
            _browser.Enabled = _startup.Enabled = _desktop.Enabled = _colour.Enabled = !busy;
            _bar.Visible = busy;
        }
    }
}
