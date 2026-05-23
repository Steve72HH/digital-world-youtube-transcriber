#define MyAppName "Digital World YouTube Transcriber"
#define MyAppVersion "1.1.2"
#define MyAppPublisher "digital-world.dev"
#define MyAppExeName "Digital-World-YouTube-Transcriber.exe"

[Setup]
AppId={{2D65F067-1F37-4ED6-A9D1-23D1A7C6B49F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://digital-world.dev
AppSupportURL=mailto:kontakt@digital-world.dev
AppUpdatesURL=https://github.com/digital-world-dev/digital-world-youtube-transcriber
DefaultDirName={autopf}\Digital World YouTube Transcriber
DefaultGroupName=Digital World YouTube Transcriber
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Digital-World-YouTube-Transcriber-Setup-{#MyAppVersion}
SetupIconFile=..\assets\logo.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknuepfung erstellen"; GroupDescription: "Zusatzaufgaben:"; Flags: unchecked
Name: "installdeps"; Description: "yt-dlp, OpenAI Whisper und FFmpeg installieren/aktualisieren"; GroupDescription: "Abhaengigkeiten:"; Flags: checkedonce

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\installer\install-dependencies.ps1"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "..\requirements-runtime.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\tools\install-dependencies.ps1"""; Description: "Abhaengigkeiten installieren"; Flags: postinstall waituntilterminated; Tasks: installdeps
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName} starten"; Flags: nowait postinstall skipifsilent
