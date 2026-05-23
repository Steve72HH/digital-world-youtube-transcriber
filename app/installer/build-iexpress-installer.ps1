$ErrorActionPreference = "Stop"

$base = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $base "dist"
$installer = Join-Path $base "installer"
$version = "1.0.0"
$output = Join-Path $dist "Digital-World-YouTube-Transcriber-Installer-$version.exe"
$sed = Join-Path $installer "Digital-World-YouTube-Transcriber.sed"

$appExe = Join-Path $dist "Digital-World-YouTube-Transcriber.exe"
$installCmd = Join-Path $installer "install-local.cmd"
$deps = Join-Path $installer "install-dependencies.ps1"
$requirements = Join-Path $base "requirements-runtime.txt"

if (-not (Test-Path $appExe)) {
    throw "App-EXE wurde nicht gefunden: $appExe"
}

$sedContent = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=Digital World YouTube Transcriber installieren?
DisplayLicense=
FinishMessage=Installation abgeschlossen.
TargetName=$output
FriendlyName=Digital World YouTube Transcriber Installer
AppLaunched=install-local.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[Strings]
FILE0="Digital-World-YouTube-Transcriber.exe"
FILE1="install-local.cmd"
FILE2="install-dependencies.ps1"
FILE3="requirements-runtime.txt"
[SourceFiles]
SourceFiles0=$dist
SourceFiles1=$installer
SourceFiles2=$base
[SourceFiles0]
%FILE0%=
[SourceFiles1]
%FILE1%=
%FILE2%=
[SourceFiles2]
%FILE3%=
"@

Set-Content -Path $sed -Value $sedContent -Encoding ASCII
& iexpress.exe /N /Q $sed
if ($LASTEXITCODE -ne 0) {
    throw "IExpress konnte den Installer nicht erstellen."
}

Write-Host "IExpress-Installer erstellt: $output"
