; TakePath Windows setup package (Inno Setup 6.3+)
; Bundles the full PyInstaller --onedir output; end users need no Python.
; Build from repository root after PyInstaller has created dist\TakePath.
;
; CI passes version parameters with:
;   ISCC.exe /DMyAppVersion=1.2.0-beta.4 /DMyAppNumericVersion=1.2.0.0 installer\takepath.iss

#ifndef MyAppVersion
  #define MyAppVersion "1.2.0-beta.4"
#endif
#ifndef MyAppNumericVersion
  #define MyAppNumericVersion "1.2.0.0"
#endif

#define MyAppName "TakePath"
#define MyAppExeName "TakePath.exe"

[Setup]
AppId={{CE2CE588-1F02-4DDE-9922-9F6A5B4C5A75}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppNumericVersion}
AppPublisher=TakePath contributors
AppPublisherURL=https://github.com/jiniyasshah/TakePath
AppSupportURL=https://github.com/jiniyasshah/TakePath/issues
AppUpdatesURL=https://github.com/jiniyasshah/TakePath/releases
DefaultDirName={localappdata}\Programs\TakePath
DefaultGroupName=TakePath
UninstallDisplayName=TakePath
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\takepath.ico
OutputDir=..\release
OutputBaseFilename=TakePath-windows-x64-setup
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; Include the entire onedir bundle, not just TakePath.exe.
Source: "..\dist\TakePath\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\TakePath"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\TakePath"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch TakePath"; Flags: nowait postinstall skipifsilent
