; Inno Setup Script for AccessiWeather
; Creates a Windows installer with Start Menu and Desktop shortcuts
;
; Requirements:
;   - Inno Setup 6.0 or later (https://jrsoftware.org/isinfo.php)
;   - PyInstaller build output in dist/AccessiWeather_dir/
;
; Build:
;   iscc installer/accessiweather.iss

#define MyAppName "AccessiWeather"
; Version is read from dist/version.txt (written by CI from pyproject.toml)
; Falls back to hardcoded default for local builds
#define MyAppVersion "0.4.3"
#ifexist "..\dist\version.txt"
  #define MyAppVersion ReadIni("..\dist\version.txt", "version", "value", "0.4.3")
#endif
#define MyAppPublisher "Orinks"
#define MyAppURL "https://github.com/Orinks/AccessiWeather"
#define MyAppExeName "AccessiWeather.exe"
#define MyAppDescription "An accessible weather application with NOAA and Open-Meteo support"

[Setup]
; Application identity
AppId={{B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppComments={#MyAppDescription}

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes

; Output settings
OutputDir=..\dist
OutputBaseFilename=AccessiWeather_Setup_v{#MyAppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4

; Privileges (no admin required for per-user install)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Modern installer appearance
WizardStyle=modern
WizardSizePercent=100

; Windows version requirements
MinVersion=10.0

; Uninstaller settings
UninstallDisplayName={#MyAppName}
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main application files from PyInstaller directory output
Source: "..\dist\AccessiWeather_dir\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Fallback: if single-file exe exists, use that
; Source: "..\dist\AccessiWeather.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

; Quick Launch shortcut (optional, legacy)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to launch after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Add to "Open with" context menu for common weather file types (optional)
; Register application path
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey

[Code]
// Custom code for accessibility announcements and checks

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add accessibility checks here
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks
    // Could add first-run setup here
  end;
end;

[UninstallDelete]
; Clean up user data on uninstall (optional - commented out to preserve settings)
; Type: filesandordirs; Name: "{userappdata}\AccessiWeather"
; Type: filesandordirs; Name: "{localappdata}\AccessiWeather"

; Clean up any cached files
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.pyc"
Type: dirifempty; Name: "{app}\__pycache__"
