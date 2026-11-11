"""Ventana de control (tkinter): el usuario no necesita terminal. Se importa solo si hay interfaz grafica."""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox

from pos import paths

ROJO, VERDE = "#d8001d", "#0a7a2f"


def abrir_carpeta(ruta):
    os.makedirs(ruta, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(ruta)  # noqa: S606
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", ruta])


def correr(srv, abrir_navegador, carpeta_respaldos, guardar_lan):
    """Muestra la ventana y bloquea hasta que el usuario cierra el sistema. Lanza tk.TclError si no hay pantalla."""
    root = tk.Tk()
    root.title("Punto de Venta")
    root.resizable(False, False)
    try:
        root.iconbitmap(paths.recurso("instalador", "icono.ico"))
    except tk.TclError:
        pass

    marco = tk.Frame(root, padx=24, pady=18)
    marco.pack()
    tk.Label(marco, text="🛒  Punto de Venta", font=("Segoe UI", 18, "bold"), fg=ROJO).pack()
    tk.Label(marco, text="●  El sistema está funcionando", font=("Segoe UI", 11), fg=VERDE).pack(pady=(4, 12))
    tk.Button(marco, text="Abrir el sistema", font=("Segoe UI", 13, "bold"), bg=ROJO, fg="white",
              activebackground="#a30016", activeforeground="white", relief="flat", padx=24, pady=8,
              command=abrir_navegador).pack(fill="x")

    lan = tk.BooleanVar(value=srv.lan)
    direccion = tk.StringVar()
    ayuda = tk.Label(marco, justify="left", wraplength=360, fg="#555", font=("Segoe UI", 9))
    caja = tk.Entry(marco, textvariable=direccion, state="readonly", justify="center", font=("Segoe UI", 11, "bold"))

    def refrescar_lan():
        if srv.lan and srv.urls_lan():
            direccion.set(srv.urls_lan()[0])
            ayuda.config(text="En la tablet o el celular (conectado al mismo Wi-Fi) abre el navegador y escribe esta dirección:")
            ayuda.pack(pady=(8, 2)); caja.pack(fill="x")
        else:
            ayuda.pack_forget(); caja.pack_forget()

    def cambiar_lan():
        try:
            srv.reiniciar(lan.get())
            guardar_lan(lan.get())
        except OSError as e:
            lan.set(srv.lan)
            messagebox.showerror("Punto de Venta", f"No se pudo cambiar el acceso desde tablet:\n{e}")
        refrescar_lan()

    tk.Checkbutton(marco, text="Permitir usar el sistema desde una tablet o celular", variable=lan,
                   command=cambiar_lan, font=("Segoe UI", 10)).pack(pady=(14, 0), anchor="w")
    refrescar_lan()

    tk.Button(marco, text="Abrir carpeta de respaldos", relief="groove",
              command=lambda: abrir_carpeta(carpeta_respaldos)).pack(fill="x", pady=(14, 4))

    def salir():
        if messagebox.askyesno("Cerrar el Punto de Venta",
                               "Si lo cierras no podrás cobrar (ni desde las tablets) hasta volver a abrirlo.\n\n¿Quieres cerrarlo?"):
            srv.detener()
            root.destroy()

    tk.Button(marco, text="Cerrar el sistema", relief="groove", command=salir).pack(fill="x")
    root.protocol("WM_DELETE_WINDOW", salir)
    root.mainloop()
