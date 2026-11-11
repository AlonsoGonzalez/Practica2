; Inno Setup: crea PuntoDeVenta-Setup-<version>.exe a partir de dist\PuntoDeVenta
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
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\PuntoDeVenta.exe
UninstallDisplayName=Punto de Venta Abarrotes
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
; al actualizar, cierra el programa si esta abierto y lo vuelve a abrir al terminar
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "icono"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"
Name: "inicio"; Description: "Abrir el Punto de Venta automáticamente al encender la computadora"; GroupDescription: "Inicio:"; Flags: unchecked

[Files]
Source: "..\dist\PuntoDeVenta\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Punto de Venta"; Filename: "{app}\PuntoDeVenta.exe"
Name: "{autodesktop}\Punto de Venta"; Filename: "{app}\PuntoDeVenta.exe"; Tasks: icono
Name: "{userstartup}\Punto de Venta"; Filename: "{app}\PuntoDeVenta.exe"; Tasks: inicio

[Run]
Filename: "{app}\PuntoDeVenta.exe"; Description: "Abrir Punto de Venta"; Flags: nowait postinstall skipifsilent

; Los datos de la tienda viven en %APPDATA%\PuntoVentaAbarrotes y NO se borran al desinstalar ni al actualizar.
