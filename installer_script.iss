; ao3_helper.iss

[Setup]
AppName=AO3 Helper
AppVersion=1.6.0
AppPublisher=Symphony_of_Dreams
DefaultDirName={autopf}\AO3 Helper
DefaultGroupName=AO3 Helper
UninstallDisplayIcon={app}\AO3 Helper.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputBaseFilename=setup_ao3_helper_v1.6.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]

Source: "G:\Ao3 Helper\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]

Name: "{group}\AO3 Helper"; Filename: "{app}\AO3 Helper.exe"

Name: "{autodesktop}\AO3 Helper"; Filename: "{app}\AO3 Helper.exe"; Tasks: desktopicon

[Tasks]

Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]

Filename: "{app}\AO3 Helper.exe"; Description: "{cm:LaunchProgram,AO3 Helper}"; Flags: nowait postinstall skipifsilent