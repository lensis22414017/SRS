; ==============================================================================
; SRS 污染场地土壤生态-生产功能重构监管系统 — Inno Setup 安装脚本
; ==============================================================================
; 编译要求: 安装 Inno Setup 6 (https://jrsoftware.org/isdl.php)
; 编译方式: 用 Inno Setup Compiler 打开此 .iss 文件 → 点击 Build (Ctrl+B)
; 前置条件: 先用 PyInstaller 生成 dist/SRS/ 目录 (含 SRS.exe + 依赖)
;
; 输出: packaging/Output/SRS-Setup-1.0.2-Windows-x64.exe (约 280-350MB)
; ==============================================================================

#define MyAppName "污染场地土壤生态-生产功能重构监管系统"
#define MyAppNameEn "SRS"
#define MyAppVersion "1.0.2"
#define MyAppPublisher "生态环境部土壤与农业农村生态环境监管技术中心"
#define MyAppURL "https://github.com/lensis22414017/SRS"
#define MyAppExeName "SRS.exe"

[Setup]
; 基本信息与版本
AppId={{B8F3E2A1-2026-0716-SRSO-000000000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
; 不允许用户选非默认位置(避免权限问题), 但保留自定义能力
DisableProgramGroupPage=yes
; 输出目录与文件名
OutputDir=..\packaging\Output
OutputBaseFilename=SRS-Setup-1.0.2-Windows-x64
; 压缩
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
; 权限要求 (安装到 Program Files 需管理员)
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 图标
SetupIconFile=srs_icon_v4.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
; 安装界面语言
ShowLanguageDialog=no
LanguageDetectionMethod=none
; 磁盘空间检查 (PyInstaller onedir 约 350MB + 缓冲)
ExtraDiskSpaceRequired=524288000
; 卸载
UninstallDisplayName={#MyAppName}
; 向导风格
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "在桌面创建快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "在快速启动栏创建快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce; OnlyBelowVersion: 6.01

[Files]
; PyInstaller 生成的整个 dist/SRS/ 目录
Source: "..\dist\SRS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 演示数据 Excel (安装到 应用数据目录\demo_sites\)
Source: "..\data\demo_sites\*.xlsx"; DestDir: "{commonappdata}\SRS\demo_sites"; Flags: ignoreversion recursesubdirs; Check: DirExists(ExpandConstant('{commonappdata}\SRS\demo_sites'))
; 首次使用说明
Source: "..\docs\USER_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Comment: "启动污染场地监管系统"
Name: "{group}\使用说明"; Filename: "{app}\USER_GUIDE.md"; Comment: "首次使用请阅读"
Name: "{group}\卸载 {#MyAppNameEn}"; Filename: "{uninstallexe}"
; 桌面快捷方式
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "启动污染场地监管系统"

[Run]
; 安装完成后启动
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理应用数据 (数据库、缓存、上传文件)
; 注意: 不删用户数据目录(AppData\Roaming\SRS), 因为可能含甲方的场地数据
; 甲方需手动删除该目录才能完全清除

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

function NeedRestart(): Boolean;
begin
  Result := False;
end;
