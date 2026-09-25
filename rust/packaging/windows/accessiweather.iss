; Inno Setup script for AccessiWeather, adapted from the Python edition's
; installer/accessiweather.iss. The AppId, install folder, executable name,
; registry entries and uninstall behaviour are unchanged, so this installer
; upgrades a Python install in place and the Python updater can run it.
;
; Built by `cargo xtask package windows-setup`, which passes:
;   /DMyAppVersion=<version>  /DStageDir=<staged app folder>  /DOutputDir=<dist>

#define MyAppName "AccessiWeather"
#ifndef MyAppVersion
  #error Pass /DMyAppVersion=<version> (cargo xtask package windows-setup does).
#endif
#ifndef StageDir
  #error Pass /DStageDir=<staged app folder> (cargo xtask package windows-setup does).
#endif
#ifndef OutputDir
  #error Pass /DOutputDir=<output folder> (cargo xtask package windows-setup does).
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
; Running copies are closed from PrepareToInstall so setup can continue without
; the default mutex prompt and launch the updated app after install.

; Installation settings
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
DisableProgramGroupPage=yes

; Output settings
OutputDir={#OutputDir}
OutputBaseFilename=AccessiWeather_Setup_v{#MyAppVersion}
SetupIconFile=..\..\crates\aw-app\ui\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Compression
Compression=lzma2/normal
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

[InstallDelete]
; The Python edition's runtime, left behind when this installer upgrades a
; Python install in place. The native app uses none of it. Settings (config),
; portable data (data) and sound packs (soundpacks) stay.
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\*.pyd"
Type: files; Name: "{app}\python*.dll"
Type: files; Name: "{app}\pythoncom*.dll"
Type: files; Name: "{app}\pywintypes*.dll"
Type: files; Name: "{app}\libcrypto-*.dll"
Type: files; Name: "{app}\libssl-*.dll"
Type: files; Name: "{app}\libffi-*.dll"
Type: files; Name: "{app}\mfc140u.dll"
Type: files; Name: "{app}\wxbase*.dll"
Type: files; Name: "{app}\wxmsw*.dll"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\accessiweather"
Type: filesandordirs; Name: "{app}\PIL"
Type: filesandordirs; Name: "{app}\certifi"
Type: filesandordirs; Name: "{app}\charset_normalizer"
Type: filesandordirs; Name: "{app}\cryptography"
Type: filesandordirs; Name: "{app}\desktop_notifier"
Type: filesandordirs; Name: "{app}\jiter"
Type: filesandordirs; Name: "{app}\librt"
Type: filesandordirs; Name: "{app}\lxml"
Type: filesandordirs; Name: "{app}\mypy"
Type: filesandordirs; Name: "{app}\prism"
Type: filesandordirs; Name: "{app}\pydantic_core"
Type: filesandordirs; Name: "{app}\sound_lib"
Type: filesandordirs; Name: "{app}\toasted"
Type: filesandordirs; Name: "{app}\tzdata"
Type: filesandordirs; Name: "{app}\winrt"
Type: filesandordirs; Name: "{app}\winsdk"
Type: filesandordirs; Name: "{app}\wx"

[Files]
; The staged app folder: AccessiWeather.exe, the Visual C++ runtime DLLs and
; the default sound pack.
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

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
; Register application path
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey

[Code]
// Installer scope hardening:
// If setup is running in admin install mode, remove a stale per-user uninstall
// entry for this AppId to avoid duplicate Add/Remove Programs rows.
// (Per-user mode intentionally does not touch HKLM for safety/permissions.)
const
  RunningAppImageName = 'AccessiWeather.exe';
  UninstallKeyWithBraces = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E}_is1';
  UninstallKeyWithoutBraces = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\B8F4D7A2-9E3C-4B5A-8D1F-6C2E7A9B0D3E_is1';

function IsAccessiWeatherRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec(
    ExpandConstant('{cmd}'),
    '/C tasklist /FI "IMAGENAME eq ' + RunningAppImageName + '" /NH | find /I "' + RunningAppImageName + '" >nul',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    Result := ResultCode = 0
  else
    Log('Could not query running AccessiWeather processes.');
end;

procedure KillAccessiWeather(Force: Boolean);
var
  ResultCode: Integer;
  Parameters: String;
begin
  Parameters := '/IM ' + RunningAppImageName + ' /T';
  if Force then
    Parameters := '/F ' + Parameters;

  if Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    Parameters,
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    Log('taskkill.exe ' + Parameters + ' exited with code ' + IntToStr(ResultCode))
  else
    Log('Could not run taskkill.exe ' + Parameters);
end;

procedure WaitForAccessiWeatherToExit(MaxWaitMilliseconds: Integer);
var
  WaitedMilliseconds: Integer;
begin
  WaitedMilliseconds := 0;
  while (WaitedMilliseconds < MaxWaitMilliseconds) and IsAccessiWeatherRunning() do
  begin
    Sleep(500);
    WaitedMilliseconds := WaitedMilliseconds + 500;
  end;
end;

function CloseRunningAccessiWeather(): Boolean;
begin
  Result := True;
  if not IsAccessiWeatherRunning() then
    exit;

  Log('AccessiWeather is running; requesting shutdown before install.');
  KillAccessiWeather(False);
  WaitForAccessiWeatherToExit(5000);

  if IsAccessiWeatherRunning() then
  begin
    Log('AccessiWeather is still running; force-stopping before install.');
    KillAccessiWeather(True);
    WaitForAccessiWeatherToExit(5000);
  end;

  Result := not IsAccessiWeatherRunning();
  if not Result then
    Log('AccessiWeather is still running after automatic close attempts.');
end;

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

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not CloseRunningAccessiWeather() then
    Result := 'Setup could not close AccessiWeather automatically. Please close it and run setup again.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    RemoveStalePerUserArpEntriesForAdminInstall();
end;

[UninstallDelete]
; User data (settings, saved locations) is kept on uninstall.
; Clean up any cached files
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\*.pyc"
Type: dirifempty; Name: "{app}\__pycache__"
