# Builds the MDM RT installer: Setup.cs (AnyCPU MSIL, .NET Framework 4.0) with a package folder
# (package\make-package.py) embedded as gzip resources, compiled with Roslyn csc. MSIL, so the one Setup runs on
# Windows RT 8.1 / Windows 10 ARM32 as well as on x64 Windows; the flavour only says which programs it carries.
# Adapted from 7-Zip RT's installer (hamed7ir/7zip-rt 7zip-rt\installer\build-installer.ps1), itself from Venetium's.
#
#   .\installer\build-installer.ps1 -Package F:\mdm-rt\deliver\MDM-RT-0.5.2-arm32 -Version 0.5.2 -Flavor arm32
#
# Writes <Out>\MDM-RT-Setup-<version>-<flavor>.exe (default Out: the package folder's parent). The exe is a release
# asset, not part of the repository.
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$Version,
    [ValidateSet('arm32', 'x64')][string]$Flavor = 'arm32',
    [string]$Out,
    [string]$Work
)
$ErrorActionPreference = 'Stop'
$Package = (Resolve-Path $Package).Path
if (-not $Out)  { $Out  = Split-Path -Parent $Package }
if (-not $Work) { $Work = Join-Path (Split-Path -Parent $Package) ("setup-build-$Flavor") }
$repo    = Split-Path -Parent $PSScriptRoot                    # the mdm-rt project folder
$setupCs = Join-Path $PSScriptRoot 'Setup.cs'
$icon    = Join-Path $repo 'branding\icons\mdm-rt.ico'
foreach ($p in @($Package, $setupCs, $icon, (Join-Path $Package 'misterdownloadmanager.exe'), (Join-Path $Package 'misterdownloadmanager-nmhost.exe'))) { if (-not (Test-Path $p)) { throw "missing: $p" } }
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Sha256([string]$p) { (Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant() }

# -- 1. gzip each package file (sub folders kept); payload.list + csc /resource arguments --------------------------
if (Test-Path $Work) { throw "$Work exists already (a fresh folder is needed; move the old one away)" }
New-Item -ItemType Directory -Force (Join-Path $Work 'payload') | Out-Null
$list = New-Object System.Collections.Generic.List[string]
$res  = New-Object System.Collections.Generic.List[string]
$files = Get-ChildItem -Path $Package -Recurse -File | Sort-Object FullName
foreach ($f in $files) {
    $rel  = $f.FullName.Substring($Package.Length).TrimStart('\')
    $relf = $rel -replace '\\', '/'                            # forward slashes in the list and resource names
    $gz   = Join-Path $Work ('payload\' + $rel + '.gz')
    New-Item -ItemType Directory -Force (Split-Path $gz) | Out-Null
    $in = [System.IO.File]::OpenRead($f.FullName); $outS = [System.IO.File]::Create($gz)
    $z  = New-Object System.IO.Compression.GZipStream($outS, [System.IO.Compression.CompressionLevel]::Optimal)
    $in.CopyTo($z); $z.Dispose(); $outS.Dispose(); $in.Dispose()
    $list.Add((Sha256 $f.FullName) + "`t" + $f.Length + "`t" + $relf)
    $res.Add('/resource:"' + $gz + '",payload/' + $relf + '.gz')
}
[System.IO.File]::WriteAllLines((Join-Path $Work 'payload.list'), $list, (New-Object System.Text.UTF8Encoding($false)))
"payload: $($list.Count) files from $Package"

# -- 2. SetupInfo.cs (the namespace must match Setup.cs) ---------------------------------------------------------
$vp = @(($Version -replace '[^0-9.]', '').Split('.') | Where-Object { $_ -ne '' } | ForEach-Object { [int]$_ }) + @(0, 0, 0, 0)
$asmVersion = ($vp[0..3] -join '.')                          # 0.5.2 -> 0.5.2.0
$info = @"
using System.Reflection;
[assembly: AssemblyTitle("MDM RT Setup")]
[assembly: AssemblyProduct("MDM RT")]
[assembly: AssemblyCompany("MDM RT (unofficial fork of Mister Download Manager by Ahmed Nefzaoui)")]
[assembly: AssemblyCopyright("Mister Download Manager: Copyright (c) 2026 Ahmed Nefzaoui; MDM RT: Hamed Ghorbani. GPL-3.0-or-later")]
[assembly: AssemblyVersion("$asmVersion")]
[assembly: AssemblyInformationalVersion("$Version $Flavor")]
namespace MdmRtSetup
{
    internal static class Info
    {
        internal const string AppVersion = "$Version";
        internal const string Flavor = "$Flavor";
    }
}
"@
[System.IO.File]::WriteAllText((Join-Path $Work 'SetupInfo.cs'), $info, (New-Object System.Text.UTF8Encoding($false)))

# -- 3. compile with Roslyn csc against .NET 4.0 reference assemblies ($csc, $refs: csc-common.ps1) --------------
. (Join-Path $PSScriptRoot 'csc-common.ps1')
New-Item -ItemType Directory -Force $Out | Out-Null
$setupExe = Join-Path $Out ("MDM-RT-Setup-$Version-$Flavor.exe")
$rsp = New-Object System.Collections.Generic.List[string]
$rsp.AddRange([string[]]@(
    '/nostdlib+', '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+', '/langversion:7.3', '/codepage:65001',
    '/deterministic+',
    ('/out:"' + $setupExe + '"'),
    ('/win32icon:"' + $icon + '"'),
    ('/resource:"' + $icon + '",setup.icon.ico'),
    ('/resource:"' + (Join-Path $Work 'payload.list') + '",payload.list'),
    ('/r:"' + (Join-Path $refs 'mscorlib.dll') + '"'),
    ('/r:"' + (Join-Path $refs 'System.dll') + '"'),
    ('/r:"' + (Join-Path $refs 'System.Core.dll') + '"'),
    ('/r:"' + (Join-Path $refs 'System.Drawing.dll') + '"'),
    ('/r:"' + (Join-Path $refs 'System.Windows.Forms.dll') + '"')))
$rsp.AddRange([string[]]$res)
$rsp.Add('"' + $setupCs + '"')
$rsp.Add('"' + (Join-Path $Work 'SetupInfo.cs') + '"')
$rspFile = Join-Path $Work 'csc.rsp'
[System.IO.File]::WriteAllLines($rspFile, $rsp, (New-Object System.Text.UTF8Encoding($false)))
& $csc /noconfig "@$rspFile"
if ($LASTEXITCODE -ne 0) { throw "Setup build failed ($LASTEXITCODE)" }

# -- 4. it must be MSIL and reference only 4.0.0.0 assemblies (read in a child PowerShell, so the exe is not held) -
$helper = Join-Path $Work 'asmfacts.ps1'
@'
param([string]$p)
$a = [System.Reflection.Assembly]::ReflectionOnlyLoadFrom($p)
'A=' + [System.Reflection.AssemblyName]::GetAssemblyName($p).ProcessorArchitecture
'R=' + (($a.GetReferencedAssemblies() | ForEach-Object { $_.Name + ' ' + $_.Version }) -join ', ')
'@ | Set-Content -Path $helper -Encoding UTF8
$ps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$facts = & $ps -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $helper $setupExe
"$facts"
if (-not ($facts -match '^A=MSIL$')) { throw 'Setup is not MSIL' }
if (($facts | Where-Object { $_ -like 'R=*' }) -match '\b[1-9]\.[1-9]\.\d+\.\d+|\b4\.[1-9]\.') { throw 'Setup references assemblies newer than 4.0' }
"OK  $setupExe  $((Get-Item $setupExe).Length) bytes  sha256 $(Sha256 $setupExe)"
