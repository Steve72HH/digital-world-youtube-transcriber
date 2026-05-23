$ErrorActionPreference = "Stop"

Write-Host "Digital World YouTube Transcriber - Abhaengigkeiten"
Write-Host "Pruefe Python, yt-dlp, Whisper und FFmpeg..."

function Find-Python {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @("python")
    }

    return $null
}

function Invoke-Python {
    param(
        [string[]]$PythonCommand,
        [string[]]$Arguments
    )

    $pythonArgs = @()
    if ($PythonCommand.Length -gt 1) {
        $pythonArgs = $PythonCommand[1..($PythonCommand.Length - 1)]
    }

    & $PythonCommand[0] @pythonArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python-Befehl fehlgeschlagen: $($Arguments -join ' ')"
    }
}

$pythonCommand = Find-Python
if (-not $pythonCommand) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Python wurde nicht gefunden und winget ist nicht verfuegbar. Bitte Python 3.11 oder neuer installieren."
    }

    Write-Host "Python wird ueber winget installiert..."
    winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Python-Installation fehlgeschlagen."
    }
    $pythonCommand = Find-Python
}

Write-Host "Aktualisiere pip..."
Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "pip", "install", "--upgrade", "pip")

Write-Host "Installiere yt-dlp und OpenAI Whisper..."
Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "pip", "install", "--upgrade", "yt-dlp", "openai-whisper", "typing_extensions")

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "FFmpeg wird ueber winget installiert..."
        winget install --id Gyan.FFmpeg -e --source winget --accept-package-agreements --accept-source-agreements
    } else {
        Write-Warning "FFmpeg wurde nicht gefunden. Bitte FFmpeg manuell installieren und in PATH aufnehmen."
    }
}

Write-Host "Fertig. Die App kann jetzt yt-dlp und Whisper verwenden."
