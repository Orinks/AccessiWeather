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
#define MyAppVersion "0.9.4"
#ifexist "..\dist\version.txt"
  #define MyAppVersion ReadIni("..\dist\version.txt", "version", "value", "0.9.4")
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

; Privileges and install scope
; - Default to per-user installs (safest for accessibility/non-admin users)
; - Keep using previous privilege mode for upgrades so install scope stays stable
; - Disable interactive override dialog to avoid accidental scope switching and
;   duplicate ARP entries from mixed HKCU/HKLM installs
PrivilegesRequired=lowest
UsePreviousPrivileges=yes
PrivilegesRequiredOverridesAllowed=commandline

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
// Installer scope hardening:
// If setup is running in admin install mode, remove a stale per-user uninstall
// entry for this AppId to avoid duplicate Add/Remove Programs rows.
// (Per-user mode intentionally does not touch HKLM for safety/permissions.)
const
  UninstallKeyWithBraces = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E}_is1';
  UninstallKeyWithoutBraces = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E_is1';

procedure RemoveStalePerUserArpEntriesForAdminInstall();
begin
  if not IsAdminInstallMode then
    exit;

  if RegKeyExists(HKCU, UninstallKeyWithBraces) then
  begin
    if RegDeleteKeyIncludingSubkeys(HKCU, UninstallKeyWithBraces) then
      Log('Removed stale HKCU uninstall key: ' + UninstallKeyWithBraces)
    else
      Log('Failed to remove HKCU uninstall key: ' + UninstallKeyWithBraces);
  end;

  // Older/legacy builds may have emitted a key without braces around the GUID.
  if RegKeyExists(HKCU, UninstallKeyWithoutBraces) then
  begin
    if RegDeleteKeyIncludingSubkeys(HKCU, UninstallKeyWithoutBraces) then
      Log('Removed stale HKCU uninstall key: ' + UninstallKeyWithoutBraces)
    else
      Log('Failed to remove HKCU uninstall key: ' + UninstallKeyWithoutBraces);
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add accessibility checks here
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemoveStalePerUserArpEntriesForAdminInstall();

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
