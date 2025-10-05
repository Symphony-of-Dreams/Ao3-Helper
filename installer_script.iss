; ao3_helper.iss (Script per Inno Setup)

[Setup]
AppName=AO3 Helper
AppVersion=1.0.0
AppPublisher=Symphony_of_Dreams
DefaultDirName={autopf}\AO3 Helper
DefaultGroupName=AO3 Helper
UninstallDisplayIcon={app}\AO3 Helper.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputBaseFilename=setup_ao3_helper_v1.0.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Questa è la parte cruciale.
; Prende TUTTI i file dalla nostra directory 'dist' e li copia nella cartella di installazione.
Source: "G:\Ao3 Helper\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Icona nel Menu Avvio
Name: "{group}\AO3 Helper"; Filename: "{app}\AO3 Helper.exe"
; Icona sul Desktop
Name: "{autodesktop}\AO3 Helper"; Filename: "{app}\AO3 Helper.exe"; Tasks: desktopicon

[Tasks]
; Opzione per creare o meno l'icona sul desktop
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
; Esegue l'applicazione alla fine dell'installazione (opzionale)
Filename: "{app}\AO3 Helper.exe"; Description: "{cm:LaunchProgram,AO3 Helper}"; Flags: nowait postinstall skipifsilent