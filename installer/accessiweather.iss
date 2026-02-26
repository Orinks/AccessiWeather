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

const
  AppUserModelIDValue = "Orinks.AccessiWeather";
  CLSID_ShellLink: TGUID = '{00021401-0000-0000-C000-000000000046}';
  IID_IPersistFile: TGUID = '{0000010B-0000-0000-C000-000000000046}';
  IID_IPropertyStore: TGUID = '{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}';
  AppUserModelIDFmtID: TGUID = '{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}';
  AppUserModelIDPID = 5;
  STGM_READWRITE = $00000002;
  VT_LPWSTR = $001F;
  COINIT_APARTMENTTHREADED = $00000002;
  S_OK = 0;
  S_FALSE = 1;

type
  HRESULT = Longint;

  TPropertyKey = record
    fmtid: TGUID;
    pid: Cardinal;
  end;

  PROPVARIANT = record
    vt: Word;
    wReserved1: Word;
    wReserved2: Word;
    wReserved3: Word;
    case Integer of
      0: (pwszVal: PWideChar);
  end;

  IPropertyStore = interface(IUnknown)
    ['{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}']
    function GetCount(out cProps: Cardinal): HRESULT; stdcall;
    function GetAt(iProp: Cardinal; out key: TPropertyKey): HRESULT; stdcall;
    function GetValue(const key: TPropertyKey; out pv: PROPVARIANT): HRESULT; stdcall;
    function SetValue(const key: TPropertyKey; const pv: PROPVARIANT): HRESULT; stdcall;
    function Commit: HRESULT; stdcall;
  end;

  IPersistFile = interface(IUnknown)
    ['{0000010B-0000-0000-C000-000000000046}']
    function GetClassID(out clsid: TGUID): HRESULT; stdcall;
    function IsDirty: HRESULT; stdcall;
    function Load(pszFileName: WideString; dwMode: Cardinal): HRESULT; stdcall;
    function Save(pszFileName: WideString; fRemember: BOOL): HRESULT; stdcall;
    function SaveCompleted(pszFileName: WideString): HRESULT; stdcall;
    function GetCurFile(out ppszFileName: WideString): HRESULT; stdcall;
  end;

function CoInitializeEx(pvReserved: Pointer; dwCoInit: Cardinal): HRESULT;
  external 'CoInitializeEx@ole32.dll stdcall';
procedure CoUninitialize; external 'CoUninitialize@ole32.dll stdcall';
function CoTaskMemAlloc(cb: Cardinal): Pointer; external 'CoTaskMemAlloc@ole32.dll stdcall';
function PropVariantClear(var propvar: PROPVARIANT): HRESULT;
  external 'PropVariantClear@propsys.dll stdcall';

procedure SetLinkAppUserModelID(const ShortcutPath, AppID: string);
var
  ShellLink: IUnknown;
  PersistFile: IPersistFile;
  PropStore: IPropertyStore;
  PropValue: PROPVARIANT;
  Key: TPropertyKey;
  CoInitResult: HRESULT;
  ShouldUninitialize: Boolean;
  HRes: HRESULT;
  BufferSize: Cardinal;
  AppIDPointer: PWideChar;
begin
  ShouldUninitialize := False;
  AppIDPointer := nil;
  FillChar(PropValue, SizeOf(PropValue), 0);

  CoInitResult := CoInitializeEx(nil, COINIT_APARTMENTTHREADED);
  if (CoInitResult <> S_OK) and (CoInitResult <> S_FALSE) then
    raise Exception.CreateFmt('CoInitializeEx failed: 0x%.8x', [CoInitResult]);
  ShouldUninitialize := True;

  try
    ShellLink := CreateComObject(CLSID_ShellLink);
    PersistFile := ShellLink as IPersistFile;
    HRes := PersistFile.Load(ShortcutPath, STGM_READWRITE);
    if HRes <> S_OK then
      raise Exception.CreateFmt('IPersistFile.Load failed: 0x%.8x', [HRes]);

    PropStore := ShellLink as IPropertyStore;

    BufferSize := (Length(AppID) + 1) * SizeOf(WideChar);
    AppIDPointer := CoTaskMemAlloc(BufferSize);
    if AppIDPointer = nil then
      raise Exception.Create('Failed to allocate memory for AppUserModelID');

    StringToWideChar(AppID, AppIDPointer, Length(AppID) + 1);

    PropValue.vt := VT_LPWSTR;
    PropValue.pwszVal := AppIDPointer;
    Key.fmtid := AppUserModelIDFmtID;
    Key.pid := AppUserModelIDPID;

    HRes := PropStore.SetValue(Key, PropValue);
    if HRes <> S_OK then
      raise Exception.CreateFmt('IPropertyStore.SetValue failed: 0x%.8x', [HRes]);

    HRes := PropStore.Commit;
    if HRes <> S_OK then
      raise Exception.CreateFmt('IPropertyStore.Commit failed: 0x%.8x', [HRes]);

    HRes := PersistFile.Save(ShortcutPath, True);
    if HRes <> S_OK then
      raise Exception.CreateFmt('IPersistFile.Save failed: 0x%.8x', [HRes]);
  finally
    PropVariantClear(PropValue);
    if ShouldUninitialize then
      CoUninitialize;
  end;
end;

procedure SetShortcutProp(const ShortcutPath: string);
begin
  if not FileExists(ShortcutPath) then
  begin
    Log(Format('Shortcut not found, skipping AppUserModel.ID registration: %s', [ShortcutPath]));
    Exit;
  end;

  try
    SetLinkAppUserModelID(ShortcutPath, AppUserModelIDValue);
    Log(Format('Set System.AppUserModel.ID "%s" on shortcut %s', [AppUserModelIDValue, ShortcutPath]));
  except
    on E: Exception do
      Log(Format('Failed to set AppUserModel.ID on %s: %s', [ShortcutPath, E.Message]));
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add accessibility checks here
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StartMenuShortcut: string;
  DesktopShortcut: string;
  CommonDesktopShortcut: string;
begin
  if CurStep = ssPostInstall then
  begin
    // Post-installation tasks
    // Could add first-run setup here
    StartMenuShortcut := ExpandConstant('{group}\{#MyAppName}.lnk');
    SetShortcutProp(StartMenuShortcut);

    if IsTaskSelected('desktopicon') then
    begin
      DesktopShortcut := ExpandConstant('{autodesktop}\{#MyAppName}.lnk');
      SetShortcutProp(DesktopShortcut);

      CommonDesktopShortcut := ExpandConstant('{commondesktop}\{#MyAppName}.lnk');
      SetShortcutProp(CommonDesktopShortcut);
    end;
  end;
end;
