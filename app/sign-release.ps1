param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $FilePath)) {
    throw "Datei zum Signieren wurde nicht gefunden: $FilePath"
}

$signTool = $env:SIGNTOOL_PATH
if (-not $signTool) {
    $candidates = @(
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe",
        "C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86\signtool.exe"
    )
    $signTool = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $signTool) {
    Write-Host "signtool.exe wurde nicht gefunden. Ueberspringe Code Signing."
    exit 0
}

$timestampUrl = if ($env:CODESIGN_TIMESTAMP_URL) { $env:CODESIGN_TIMESTAMP_URL } else { "http://timestamp.digicert.com" }
$description = "Digital World YouTube Transcriber"
$website = "https://digital-world.dev"

if ($env:CODESIGN_CERT_PATH) {
    if (-not (Test-Path $env:CODESIGN_CERT_PATH)) {
        throw "CODESIGN_CERT_PATH wurde gesetzt, aber die Datei existiert nicht: $env:CODESIGN_CERT_PATH"
    }

    $args = @(
        "sign",
        "/fd", "SHA256",
        "/tr", $timestampUrl,
        "/td", "SHA256",
        "/d", $description,
        "/du", $website,
        "/f", $env:CODESIGN_CERT_PATH
    )
    if ($env:CODESIGN_CERT_PASSWORD) {
        $args += @("/p", $env:CODESIGN_CERT_PASSWORD)
    }
    $args += $FilePath
    & $signTool @args
} elseif ($env:CODESIGN_CERT_SUBJECT) {
    & $signTool sign /fd SHA256 /tr $timestampUrl /td SHA256 /d $description /du $website /n $env:CODESIGN_CERT_SUBJECT $FilePath
} else {
    Write-Host "Kein Code-Signing-Zertifikat konfiguriert. Setze CODESIGN_CERT_PATH oder CODESIGN_CERT_SUBJECT."
    exit 0
}

if ($LASTEXITCODE -ne 0) {
    throw "Code Signing fehlgeschlagen: $FilePath"
}

Write-Host "Signiert: $FilePath"
