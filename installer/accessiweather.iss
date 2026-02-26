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
{
  Post-install: set System.AppUserModel.ID on the Start Menu shortcut.
  Required for WinRT toast notifications to surface in Action Center and
  for screen readers to announce notification text.
  Uses a temporary PowerShell script (Add-Type/C#) to call IPropertyStore
  via SHGetPropertyStoreFromParsingName — simpler than Pascal COM bindings.
}

const
  AppUserModelIDStr = 'Orinks.AccessiWeather';

function WriteSetAppIdScript(const ScriptPath: string): Boolean;
var
  Lines: TArrayOfString;
begin
  SetArrayLength(Lines, 44);
  Lines[0]  := 'param([string]$Path, [string]$AppId)';
  Lines[1]  := 'if (-not (Test-Path $Path)) { Write-Host "Shortcut not found: $Path"; exit 0 }';
  Lines[2]  := 'try {';
  Lines[3]  := 'Add-Type -TypeDefinition @"';
  Lines[4]  := 'using System;';
  Lines[5]  := 'using System.Runtime.InteropServices;';
  Lines[6]  := '[Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]';
  Lines[7]  := '[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]';
  Lines[8]  := 'public interface IPropertyStore {';
  Lines[9]  := '    void GetCount(out uint c);';
  Lines[10] := '    void GetAt(uint i, out PropKey k);';
  Lines[11] := '    void GetValue(ref PropKey k, out object v);';
  Lines[12] := '    void SetValue(ref PropKey k, ref PropVariantW v);';
  Lines[13] := '    void Commit();';
  Lines[14] := '}';
  Lines[15] := '[StructLayout(LayoutKind.Sequential, Pack=4)]';
  Lines[16] := 'public struct PropKey { public Guid fmt; public uint pid; }';
  Lines[17] := '[StructLayout(LayoutKind.Explicit)]';
  Lines[18] := 'public struct PropVariantW {';
  Lines[19] := '    [FieldOffset(0)] public ushort vt;';
  Lines[20] := '    [FieldOffset(8)] public IntPtr pwszVal;';
  Lines[21] := '}';
  Lines[22] := 'public class PropStoreHelper {';
  Lines[23] := '    [DllImport("shell32.dll", CharSet=CharSet.Unicode)]';
  Lines[24] := '    public static extern int SHGetPropertyStoreFromParsingName(';
  Lines[25] := '        string path, IntPtr pbc, int flags,';
  Lines[26] := '        [MarshalAs(UnmanagedType.LPStruct)] Guid riid,';
  Lines[27] := '        [MarshalAs(UnmanagedType.Interface)] out IPropertyStore ppv);';
  Lines[28] := '}';
  Lines[29] := '"@ -Language CSharp';
  Lines[30] := '$iid = [Guid]"886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"';
  Lines[31] := '$store = $null';
  Lines[32] := '$hr = [PropStoreHelper]::SHGetPropertyStoreFromParsingName($Path, [IntPtr]::Zero, 2, $iid, [ref]$store)';
  Lines[33] := 'if ($hr -ne 0) { throw "SHGetPropertyStoreFromParsingName hr=0x$($hr.ToString(''X''))" }';
  Lines[34] := '$key = [PropKey]@{ fmt = [Guid]"9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"; pid = 5 }';
  Lines[35] := '$ptr = [System.Runtime.InteropServices.Marshal]::StringToCoTaskMemUni($AppId)';
  Lines[36] := 'try {';
  Lines[37] := '    $pv = [PropVariantW]@{ vt = 0x1F; pwszVal = $ptr }';
  Lines[38] := '    $store.SetValue([ref]$key, [ref]$pv)';
  Lines[39] := '    $store.Commit()';
  Lines[40] := '    Write-Host "AppUserModel.ID set: $AppId -> $Path"';
  Lines[41] := '} finally { [System.Runtime.InteropServices.Marshal]::FreeCoTaskMem($ptr) }';
  Lines[42] := '} catch { Write-Warning "Failed: $_"; exit 0 }';
  Lines[43] := '';
  Result := SaveStringsToFile(ScriptPath, Lines, False);
end;

procedure SetShortcutAppUserModelID(const ShortcutPath: string);
var
  ScriptPath: string;
  ResultCode: Integer;
begin
  if not FileExists(ShortcutPath) then
  begin
    Log('AppUserModel.ID: shortcut not found, skipping: ' + ShortcutPath);
    Exit;
  end;

  ScriptPath := ExpandConstant('{tmp}\set_appid.ps1');
  if not WriteSetAppIdScript(ScriptPath) then
  begin
    Log('AppUserModel.ID: failed to write temp script');
    Exit;
  end;

  Exec(
    'powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '"'
      + ' -Path "' + ShortcutPath + '"'
      + ' -AppId "' + AppUserModelIDStr + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );

  if ResultCode = 0 then
    Log('AppUserModel.ID: success on ' + ShortcutPath)
  else
    Log('AppUserModel.ID: PowerShell returned ' + IntToStr(ResultCode) + ' for ' + ShortcutPath);

  DeleteFile(ScriptPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  StartMenuLnk: string;
  DesktopLnk: string;
begin
  if CurStep = ssPostInstall then
  begin
    StartMenuLnk := ExpandConstant('{group}\{#MyAppName}.lnk');
    SetShortcutAppUserModelID(StartMenuLnk);

    if IsTaskSelected('desktopicon') then
    begin
      DesktopLnk := ExpandConstant('{autodesktop}\{#MyAppName}.lnk');
      SetShortcutAppUserModelID(DesktopLnk);
    end;
  end;
end;
