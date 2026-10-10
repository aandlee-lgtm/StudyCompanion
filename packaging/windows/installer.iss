; Inno Setup script for HSC Companion 2027 (per-user install, no administrator rights needed).
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "HSC Companion"
#define MyAppExe "HSC Companion.exe"

[Setup]
AppId={{7C1F3E52-5A0B-4D7B-9C2E-2027A11CE5A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=HSC Companion (private study app)
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=HSC-Companion-{#MyAppVersion}-Windows-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\dist\HSC Companion\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Start {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[Messages]
FinishedLabel=HSC Companion is installed. Your study data is kept separately in %APPDATA%\HSC Companion, so uninstalling or updating never deletes it.
