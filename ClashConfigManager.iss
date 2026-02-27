; ============================================================
; ClashConfigManager.iss — Inno Setup
; Директория проекта: D:\Documents2\coding\yaml
; ============================================================

#define MyAppName      "Clash Config Manager"
#define MyAppVersion   "2.0"
#define MyAppPublisher "ClashConfigManager"
#define MyAppExeName   "ClashConfigManager.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist\installer
OutputBaseFilename=ClashConfigManager_v{#MyAppVersion}_Setup
SetupIconFile=D:\Documents2\coding\yaml\icon.png
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#MyAppVersion}.0.0

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon";  Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon";  Description: "Запускать при входе в Windows (свёрнутым в трей)"; GroupDescription: "Дополнительно:"

[Files]
Source: "D:\Documents2\coding\yaml\dist\ClashConfigManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "D:\Documents2\coding\yaml\icon.png";                    DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";          Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.png"
Name: "{group}\Удалить {#MyAppName}";  Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.png"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; \
    ValueData: """{app}\{#MyAppExeName}"" --minimized"; \
    Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden waituntilterminated

[UninstallDelete]
Type: files; Name: "{app}\app_config.json"
Type: files; Name: "{app}\clean.yaml"
Type: files; Name: "{app}\sub_cache.json"

[Code]
function InitializeSetup(): Boolean;
var ResultCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
