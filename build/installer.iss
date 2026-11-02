; Inno Setup Script for AI DeskMate
; Builds single self-contained Windows Installer: AI-DeskMate-Setup-<version>.exe

#define AppName "AI DeskMate"
#define AppPublisher "AI DeskMate Project"
#define AppURL "https://github.com/example/ai-deskmate"
#define AppExeName "AIDeskMate.exe"

#if FileExists("..\VERSION")
  #define AppVersion Trim(FileRead(FileOpen("..\VERSION")))
#else
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{D37E8F1A-B962-4C10-9E32-5FA21481DC30}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=AI-DeskMate-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start AI DeskMate when I sign in to Windows"; GroupDescription: "Startup options:"; Flags: unchecked

[Files]
Source: "..\dist\AIDeskMate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: User data (%APPDATA%\AI DeskMate) is created at runtime and is never placed in {app}

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "AIDeskMate"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Prompt user whether to retain or delete collected wellness history on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\AI DeskMate');
    if DirExists(DataDir) then
    begin
      if MsgBox('Would you like to keep your collected activity history, energy logs, and settings (%APPDATA%\AI DeskMate) for future reinstalls?' + #13#10#13#10 +
                'Click "Yes" to keep your data, or "No" to completely remove all data.',
                mbConfirmation, MB_YESNO) = IDNO then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
