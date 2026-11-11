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
; una instalacion nueva (o una reinstalacion) nunca deja el sistema visible en la red sin avisar: la tablet se vuelve a activar a proposito
Filename: "{app}\PuntoDeVenta.exe"; Parameters: "--apagar-tablet"; Flags: runhidden
Filename: "{app}\PuntoDeVenta.exe"; Description: "Abrir Punto de Venta"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; el desinstalador debe cerrar el programa antes de borrar archivos (si no, quedan archivos y el puerto 5000 ocupados)
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM PuntoDeVenta.exe"; Flags: runhidden; RunOnceId: "CerrarPuntoDeVenta"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Punto de Venta (acceso desde tablet)"""; Flags: runhidden; RunOnceId: "QuitarReglaFirewall"

; Los datos de la tienda viven en %APPDATA%\PuntoVentaAbarrotes y NO se borran al desinstalar ni al actualizar.
