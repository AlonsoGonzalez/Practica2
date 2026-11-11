; Inno Setup: crea PuntoDeVenta-Setup.exe a partir de dist\PuntoDeVenta
; Compilar:  iscc /DVersion=1.0.0 instalador\pos.iss
#ifndef Version
  #define Version "1.0.0"
#endif

[Setup]
AppName=Punto de Venta Abarrotes
AppVersion={#Version}
AppId={{8E3B4C52-5B7A-4D1B-9C0E-7B1F5D2A9A10}
DefaultDirName={autopf}\PuntoDeVenta
DefaultGroupName=Punto de Venta
OutputDir=..\salida
OutputBaseFilename=PuntoDeVenta-Setup-{#Version}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayName=Punto de Venta Abarrotes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "icono"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\PuntoDeVenta\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Punto de Venta"; Filename: "{app}\PuntoDeVenta.exe"
Name: "{autodesktop}\Punto de Venta"; Filename: "{app}\PuntoDeVenta.exe"; Tasks: icono
Name: "{group}\Punto de Venta (con acceso desde tablet)"; Filename: "{app}\PuntoDeVenta.exe"; Parameters: "--lan"

[Run]
Filename: "{app}\PuntoDeVenta.exe"; Description: "Abrir Punto de Venta"; Flags: nowait postinstall skipifsilent

; Los datos de la tienda viven en %APPDATA%\PuntoVentaAbarrotes y NO se borran al desinstalar ni al actualizar.
