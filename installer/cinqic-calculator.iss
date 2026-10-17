; Inno Setup script for Cinqic Calculator.
; Builds a per-user (no admin required) installer from the PyInstaller
; onedir output in dist\CinqicCalculator.

#define MyAppName "Cinqic Calculator"
#define MyAppVersion "1.1.1"
#define MyAppPublisher "Cinqic"
#define MyAppURL "https://cinqic.com"
#define MyAppExeName "CinqicCalculator.exe"

[Setup]
AppId={{6B6E6C9E-6B7B-4C7A-9C6B-CINQICCALC01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\Cinqic\Calculator
DefaultGroupName=Cinqic Calculator
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Cinqic-Calculator-Windows-x64-Setup
SetupIconFile=..\assets\icons\cinqic-calculator.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\CinqicCalculator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cinqic Calculator"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Cinqic Calculator"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Cinqic Calculator"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Cinqic Calculator"; Flags: nowait postinstall skipifsilent
