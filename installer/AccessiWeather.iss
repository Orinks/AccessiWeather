; AccessiWeather Inno Setup Script
; Created dynamically for AccessiWeather

#define MyAppName "AccessiWeather"
#define MyAppVersion GetEnv("ACCESSIWEATHER_VERSION")
#define MyAppPublisher "Orinks"
#define MyAppURL "https://github.com/Orinks/AccessiWeather"
#define MyAppExeName "AccessiWeather.exe"
#define MyAppId "{{F8A91E4D-7549-4D61-B8C3-95AF20885A98}}"

; Get absolute paths from environment variables
#define RootDir GetEnv("ACCESSIWEATHER_ROOT_DIR")
#define DistDir GetEnv("ACCESSIWEATHER_DIST_DIR")

[Setup]
; Basic Setup Information
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Compression settings
Compression=lzma
SolidCompression=yes
; Output settings
OutputDir={#DistDir}
OutputBaseFilename={#MyAppName}_Setup_v{#MyAppVersion}
; Installer appearance
; No icon file found in the project
WizardStyle=modern
; Installer privileges
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest

; Installer UI settings
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Include all files from the dist directory (created by PyInstaller)
Source: "{#DistDir}\AccessiWeather\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Include additional files
Source: "{#RootDir}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RootDir}\RELEASE_README.md"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion

[Icons]
; Create program shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Create desktop shortcut if selected
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Create quick launch shortcut if selected
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Install Python dependencies if needed
Filename: "{sys}\cmd.exe"; Parameters: "/c pip install -q wxPython requests plyer geopy python-dateutil"; Description: "Install required Python packages"; Flags: postinstall; Check: CheckPythonInstalled

; Option to run the application after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Create configuration directory during installation
procedure CreateConfigDir;
var
  ConfigDir: String;
begin
  ConfigDir := ExpandConstant('{userappdata}\.accessiweather');
  if not DirExists(ConfigDir) then
    ForceDirectories(ConfigDir);
end;

// Create a sample config file if it doesn't exist
procedure CreateSampleConfig;
var
  ConfigFile: String;
  SampleConfigContent: String;
begin
  ConfigFile := ExpandConstant('{userappdata}\.accessiweather\config.json');

  // Only create if the file doesn't exist
  if not FileExists(ConfigFile) then
  begin
    SampleConfigContent := '{ ' + #13#10 +
                          '  "api_settings": {' + #13#10 +
                          '    "contact_info": ""' + #13#10 +
                          '  },' + #13#10 +
                          '  "settings": {' + #13#10 +
                          '    "update_interval_minutes": 10,' + #13#10 +
                          '    "alert_radius_miles": 25,' + #13#10 +
                          '    "precise_location_alerts": true,' + #13#10 +
                          '    "show_nationwide_location": true,' + #13#10 +
                          '    "minimize_to_tray": true,' + #13#10 +
                          '    "cache_enabled": true,' + #13#10 +
                          '    "cache_ttl": 300,' + #13#10 +
                          '    "auto_refresh_national": true,' + #13#10 +
                          '    "data_source": "nws"' + #13#10 +
                          '  },' + #13#10 +
                          '  "api_keys": {' + #13#10 +
                          '    "weatherapi": ""' + #13#10 +
                          '  }' + #13#10 +
                          '}';

    SaveStringToFile(ConfigFile, SampleConfigContent, False);
  end;
end;

// Check if Python is installed and version is compatible
function CheckPythonInstalled(): Boolean;
var
  ResultCode: Integer;
  TempFile: String;
  Output: String;
  VersionCheckScript: String;
begin
  Result := False;

  // Try to run python --version to check if Python is installed
  if not Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    MsgBox('Python is not installed or not in PATH. The application may not work correctly.', mbInformation, MB_OK);
    Exit;
  end;

  // Create a temporary file for the version check script
  TempFile := ExpandConstant('{tmp}\check_python_version.py');

  // Python script to check version
  VersionCheckScript :=
    'import sys' + #13#10 +
    'min_version = (3, 7)' + #13#10 +
    'current = sys.version_info[:2]' + #13#10 +
    'if current >= min_version:' + #13#10 +
    '    print("Compatible")' + #13#10 +
    'else:' + #13#10 +
    '    print("Incompatible")' + #13#10;

  // Save the script to the temporary file
  SaveStringToFile(TempFile, VersionCheckScript, False);

  // Run the script and check the output
  if Exec('python', TempFile, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    // Python is installed, now check if version is compatible
    if ResultCode = 0 then
      Result := True
    else
      MsgBox('Python version is not compatible. Python 3.7 or higher is required.', mbInformation, MB_OK);
  end;

  // Clean up the temporary file
  DeleteFile(TempFile);
end;

// Run these procedures during installation
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    CreateConfigDir;
    CreateSampleConfig;
  end;
end;
