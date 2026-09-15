param(
  [string]$Version = "0.1.0.0",
  [string]$Publisher = "CN=50CA2AC2-0155-44AC-B2B0-47100A3FB6E2"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "artifacts\msix"
$payload = Join-Path $out "payload"
Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $payload | Out-Null

$exe = Get-ChildItem (Join-Path $root "src-tauri\target\release") -Filter "html-studio.exe" -Recurse | Select-Object -First 1
if (-not $exe) { $exe = Get-ChildItem (Join-Path $root "src-tauri\target\release") -Filter "vel-studio.exe" -Recurse | Select-Object -First 1 }
if (-not $exe) { throw "Tauri executable was not found." }
Copy-Item $exe.FullName (Join-Path $payload "HTMLStudio.exe")

@"
<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedCapabilites">
  <Identity Name="HappyRecorder3D.html-studio" Publisher="$Publisher" Version="$Version" />
  <Properties><DisplayName>HTML Studio</DisplayName><PublisherDisplayName>Happy Recorder 3D</PublisherDisplayName><Description>Friendly native learning IDE for HTML, CSS, JavaScript and Teloce.</Description><Logo>Assets\StoreLogo.png</Logo></Properties>
  <Resources><Resource Language="en-us" /></Resources>
  <Applications><Application Id="HTMLStudio" Executable="HTMLStudio.exe" EntryPoint="Windows.FullTrustApplication"><uap:VisualElements AppListEntry="none" DisplayName="HTML Studio" Description="Friendly HTML, CSS and JavaScript learning IDE" Square150x150Logo="Assets\Square150x150Logo.png" Square44x44Logo="Assets\Square44x44Logo.png" /></Application></Applications>
  <Capabilities><rescap:Capability Name="runFullTrust" /></Capabilities>
</Package>
"@ | Set-Content (Join-Path $payload "AppxManifest.xml") -Encoding UTF8

New-Item -ItemType Directory -Force (Join-Path $payload "Assets") | Out-Null
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap 150, 150
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(23, 27, 45))
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$font = New-Object System.Drawing.Font("Segoe UI", 32, [System.Drawing.FontStyle]::Bold)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(142, 230, 208))
$graphics.DrawString("< />", $font, $brush, 18, 48)
$font.Dispose(); $brush.Dispose()
$bitmap.Save((Join-Path $payload "Assets\StoreLogo.png"), [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Save((Join-Path $payload "Assets\Square150x150Logo.png"), [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose(); $graphics.Dispose()
Copy-Item (Join-Path $payload "Assets\StoreLogo.png") (Join-Path $payload "Assets\Square44x44Logo.png")

$makeAppx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Filter makeappx.exe -Recurse | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeAppx) { throw "Windows SDK makeappx.exe was not found." }
& $makeAppx.FullName pack /d $payload /p (Join-Path $out "VelStudio.msix") /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed with exit code $LASTEXITCODE." }
Write-Host "Created unsigned MSIX staging artifact: $out\VelStudio.msix"
