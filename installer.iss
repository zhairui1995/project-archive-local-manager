#define MyAppName "项目档案本地管理系统"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "Local"
#define MyAppExeName "ProjectArchiveManager.exe"

[Setup]
AppId={{A5784E2A-3C64-42E0-B81F-D520E0470A64}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ProjectArchiveManager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=项目档案本地管理系统-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Files]
Source: "deployment\ProjectArchiveManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "MIGRATION_AND_USER_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "deliverables\档案迁移导入模板.xlsx"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{autoprograms}\迁移与使用指南"; Filename: "{app}\MIGRATION_AND_USER_GUIDE.md"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动{#MyAppName}"; Flags: nowait postinstall skipifsilent
