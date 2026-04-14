; ============================================================
; guyong-juhuo Inno Setup Script
; 双模式：静默安装 / 向导界面
; 编译：iscc setup.iss
; ============================================================

#define MyAppName "聚活"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "guyong-juhuo"
#define MyAppURL "https://github.com/taxatombt/guyong-juhuo"
#define MyAppExeName "launcher.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=guyong-juhuo-{#MyAppVersion}-setup
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "开机自动启动"; GroupDescription: "其他选项:"

[Files]
; 排除 .git __pycache__ .env 等不需要的文件
Source: "*"; DestDir: "{app}"; Excludes: ".git,__pycache__,*.pyc,.env,node_modules,*.db,*.log,dist,.venv,*.egg-info,.github,installer"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--init"; Description: "初始化聚活环境"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 卸载时清理启动项
Filename: "taskkill"; Parameters: "/F /IM python.exe"; Flags: runhidden; RunOnceId: "KillPython"
