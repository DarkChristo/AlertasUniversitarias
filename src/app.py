"""Aplicacion de alertas universitarias (interfaz Tkinter) sobre multicast UDP.

Roles:
  emisor   -> crea y envia alertas al grupo multicast.
  receptor -> se une al grupo y muestra las alertas que llegan (mas contadores de huecos, etc.).

Ejecutar:  python app.py      (desde la carpeta src)
"""
import json
import queue
import socket
import time
import tkinter as tk
from tkinter import ttk, messagebox

from common import BASE, load_config
from auth import autenticar
from net import AlertSender, AlertReceiver

NIVELES = ["info", "aviso", "critica"]
# nivel -> (color de fondo, color de texto)
COLORES = {
    "info": ("#d6eaf8", "#1b4f72"),
    "aviso": ("#fdebd0", "#9c640c"),
    "critica": ("#f5b7b1", "#922b21"),
}
RUTA_LOCAL = BASE / "config_local.json"


# ---------------------------------------------------------------------- utilidades
def cargar_local():
    try:
        with open(RUTA_LOCAL, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar_local(datos):
    try:
        with open(RUTA_LOCAL, "w", encoding="utf-8") as f:
            json.dump(datos, f)
    except OSError:
        pass


def detectar_ip(cfg):
    """IP que el sistema usaria para salir hacia el grupo. Es solo una sugerencia editable."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((cfg["group"], cfg["port"]))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "0.0.0.0"


def cargar_plantillas():
    try:
        with open(BASE / "data" / "alertas_prueba.json", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return [{"level": "info", "zone": "Campus", "text": "Alerta de prueba"}]


def barra_superior(padre, app, usuario, iface):
    barra = ttk.Frame(padre)
    barra.pack(fill="x")
    cfg = app.cfg
    texto = (f"{usuario['nombre']}   |   rol: {usuario['rol']}   |   "
             f"interfaz {iface}   |   grupo {cfg['group']}:{cfg['port']}")
    ttk.Label(barra, text=texto, font=("Segoe UI", 10, "bold")).pack(side="left")
    ttk.Button(barra, text="Cerrar sesión", command=app.mostrar_login).pack(side="right")
    return barra


# ---------------------------------------------------------------------- aplicacion
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Alertas universitarias - Multicast")
        self.geometry("980x640")
        self.minsize(820, 520)
        self.cfg = load_config()
        self.frame = None
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar)
        self.mostrar_login()

    def _cambiar(self, nuevo):
        if self.frame is not None:
            if hasattr(self.frame, "cerrar"):
                self.frame.cerrar()
            self.frame.destroy()
        self.frame = nuevo
        self.frame.pack(fill="both", expand=True)

    def mostrar_login(self):
        self._cambiar(LoginFrame(self))

    def entrar(self, usuario, iface):
        try:
            if usuario["rol"] == "emisor":
                nuevo = EmisorFrame(self, usuario, iface)
            else:
                nuevo = ReceptorFrame(self, usuario, iface)
        except OSError as e:
            messagebox.showerror(
                "Error de red",
                f"No se pudo abrir el socket multicast con la interfaz {iface}.\n\n{e}\n\n"
                "Revisa que la IP sea la de tu adaptador Wi-Fi (ipconfig).")
            return
        self._cambiar(nuevo)

    def al_cerrar(self):
        if self.frame is not None and hasattr(self.frame, "cerrar"):
            self.frame.cerrar()
        self.destroy()


# ---------------------------------------------------------------------- login
class LoginFrame(ttk.Frame):
    def __init__(self, app):
        super().__init__(app, padding=40)
        self.app = app
        centro = ttk.Frame(self)
        centro.place(relx=0.5, rely=0.45, anchor="center")

        ttk.Label(centro, text="Sistema de alertas universitarias",
                  font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        ttk.Label(centro, text="Inicio de sesión").grid(row=1, column=0, columnspan=2, pady=(0, 18))

        ttk.Label(centro, text="Usuario").grid(row=2, column=0, sticky="e", padx=6, pady=4)
        self.usuario = ttk.Entry(centro, width=28)
        self.usuario.grid(row=2, column=1, pady=4)

        ttk.Label(centro, text="Contraseña").grid(row=3, column=0, sticky="e", padx=6, pady=4)
        self.password = ttk.Entry(centro, width=28, show="*")
        self.password.grid(row=3, column=1, pady=4)

        ttk.Label(centro, text="IP de mi interfaz").grid(row=4, column=0, sticky="e", padx=6, pady=4)
        self.ip = ttk.Entry(centro, width=28)
        self.ip.grid(row=4, column=1, pady=4)
        self.ip.insert(0, cargar_local().get("iface") or detectar_ip(app.cfg))

        ttk.Label(centro, text="(la IP de tu Wi-Fi del hotspot, ej. 192.168.137.x)",
                  foreground="#666666").grid(row=5, column=0, columnspan=2)

        self.error = ttk.Label(centro, text="", foreground="#b03a2e")
        self.error.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(centro, text="Ingresar", command=self.intentar).grid(row=7, column=0, columnspan=2, pady=12)

        self.usuario.focus_set()
        self.bind_all("<Return>", lambda e: self.intentar())

    def intentar(self):
        usuario = self.usuario.get().strip()
        password = self.password.get()
        iface = self.ip.get().strip()
        try:
            socket.inet_aton(iface)
        except OSError:
            self.error.config(text="La IP de la interfaz no es válida.")
            return
        datos = autenticar(usuario, password)
        if datos is None:
            self.error.config(text="Usuario o contraseña incorrectos.")
            return
        guardar_local({"iface": iface})
        self.app.entrar(datos, iface)

    def cerrar(self):
        self.unbind_all("<Return>")


# ---------------------------------------------------------------------- pantalla del emisor
class EmisorFrame(ttk.Frame):
    def __init__(self, app, usuario, iface):
        super().__init__(app, padding=12)
        self.app = app
        self.sender = AlertSender(app.cfg, iface, usuario["usuario"])
        self.sender.iniciar_latidos()
        self.plantillas = cargar_plantillas()
        self._enviadas = 0
        self._rafaga_activa = False
        self._cerrado = False

        barra_superior(self, app, usuario, iface)

        caja = ttk.LabelFrame(self, text="Nueva alerta", padding=10)
        caja.pack(fill="x", pady=10)

        ttk.Label(caja, text="Plantilla").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.plantilla = ttk.Combobox(
            caja, state="readonly", width=70,
            values=[f"[{p['level']}] {p['zone']}: {p['text']}" for p in self.plantillas])
        self.plantilla.grid(row=0, column=1, columnspan=3, sticky="w", pady=3)
        self.plantilla.bind("<<ComboboxSelected>>", self._cargar_plantilla)

        ttk.Label(caja, text="Nivel").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.nivel = ttk.Combobox(caja, state="readonly", width=12, values=NIVELES)
        self.nivel.set("aviso")
        self.nivel.grid(row=1, column=1, sticky="w", pady=3)

        ttk.Label(caja, text="Zona").grid(row=1, column=2, sticky="e", padx=4, pady=3)
        self.zona = ttk.Entry(caja, width=34)
        self.zona.grid(row=1, column=3, sticky="w", pady=3)

        ttk.Label(caja, text="Mensaje").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        self.texto = ttk.Entry(caja, width=88)
        self.texto.grid(row=2, column=1, columnspan=3, sticky="w", pady=3)

        botones = ttk.Frame(caja)
        botones.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Button(botones, text="Enviar alerta", command=self.enviar_formulario).pack(side="left")

        ttk.Label(botones, text="     Ráfaga de prueba:  cantidad").pack(side="left")
        self.cantidad = ttk.Spinbox(botones, from_=1, to=2000, width=6)
        self.cantidad.set(20)
        self.cantidad.pack(side="left", padx=4)
        ttk.Label(botones, text="intervalo (ms)").pack(side="left")
        self.intervalo = ttk.Spinbox(botones, from_=1, to=5000, width=6)
        self.intervalo.set(200)
        self.intervalo.pack(side="left", padx=4)
        self.btn_rafaga = ttk.Button(botones, text="Enviar ráfaga", command=self.rafaga)
        self.btn_rafaga.pack(side="left", padx=6)

        self.contador = ttk.Label(self, text="Alertas enviadas: 0", font=("Segoe UI", 10, "bold"))
        self.contador.pack(anchor="w")
        ttk.Label(self, text="Cada alerta se envía UNA sola vez al grupo; el emisor no conoce a los receptores.",
                  foreground="#666666").pack(anchor="w")

        cols = ("hora", "seq", "nivel", "zona", "texto")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, ancho in zip(cols, (80, 50, 80, 200, 520)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=ancho, anchor="w")
        for nivel, (fondo, texto) in COLORES.items():
            self.tree.tag_configure(nivel, background=fondo, foreground=texto)
        self.tree.pack(fill="both", expand=True, pady=(6, 0))

    def _cargar_plantilla(self, _evento=None):
        i = self.plantilla.current()
        if i < 0:
            return
        p = self.plantillas[i]
        self.nivel.set(p["level"])
        self.zona.delete(0, "end")
        self.zona.insert(0, p["zone"])
        self.texto.delete(0, "end")
        self.texto.insert(0, p["text"])

    def enviar_formulario(self):
        zona = self.zona.get().strip()
        texto = self.texto.get().strip()
        if not zona or not texto:
            messagebox.showwarning("Faltan datos", "Escribe la zona y el mensaje (o elige una plantilla).")
            return
        self._enviar(self.nivel.get(), zona, texto)

    def _enviar(self, nivel, zona, texto):
        try:
            msg = self.sender.enviar_alerta(nivel, zona, texto)
        except OSError as e:
            messagebox.showerror("Error al enviar", str(e))
            return False
        self._enviadas += 1
        self.contador.config(text=f"Alertas enviadas: {self._enviadas}")
        self.tree.insert("", 0, values=(time.strftime("%H:%M:%S"), msg["seq"], nivel, zona, texto), tags=(nivel,))
        return True

    def rafaga(self):
        if self._rafaga_activa:
            return
        try:
            n = int(self.cantidad.get())
            ms = max(1, int(self.intervalo.get()))
        except ValueError:
            messagebox.showwarning("Datos inválidos", "Cantidad e intervalo deben ser números enteros.")
            return
        self._rafaga_activa = True
        self.btn_rafaga.state(["disabled"])

        def paso(i):
            if self._cerrado:
                return
            if i >= n:
                self._rafaga_activa = False
                self.btn_rafaga.state(["!disabled"])
                return
            p = self.plantillas[i % len(self.plantillas)]
            if not self._enviar(p["level"], p["zone"], p["text"]):
                self._rafaga_activa = False
                self.btn_rafaga.state(["!disabled"])
                return
            self.after(ms, paso, i + 1)

        paso(0)

    def cerrar(self):
        self._cerrado = True
        self.sender.cerrar()


# ---------------------------------------------------------------------- pantalla del receptor
class ReceptorFrame(ttk.Frame):
    def __init__(self, app, usuario, iface):
        super().__init__(app, padding=12)
        self.app = app
        self.eventos = queue.Queue()
        self.rx = AlertReceiver(app.cfg, iface, usuario["usuario"], self.eventos)
        self.rx.start()
        self._after_id = None

        barra_superior(self, app, usuario, iface)

        self.banner = tk.Label(self, text="Esperando alertas del emisor...", font=("Segoe UI", 14, "bold"),
                               bg="#eaecee", fg="#555555", pady=14, wraplength=900)
        self.banner.pack(fill="x", pady=10)

        # contadores
        fila = ttk.Frame(self)
        fila.pack(fill="x")
        self.vars = {}
        for clave, titulo in (("recibidas", "Recibidas"), ("huecos", "Huecos (perdidas)"),
                              ("duplicados", "Duplicados"), ("tardios", "Fuera de orden"),
                              ("descartados", "Descartadas (simuladas)"), ("rechazados", "Rechazadas (firma)")):
            v = tk.StringVar(value="0")
            self.vars[clave] = v
            col = ttk.Frame(fila, padding=(0, 0, 18, 0))
            col.pack(side="left")
            ttk.Label(col, text=titulo, foreground="#666666").pack(anchor="w")
            ttk.Label(col, textvariable=v, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.estado_emisor = tk.StringVar(value="Emisor: sin señal todavía")
        ttk.Label(fila, textvariable=self.estado_emisor, font=("Segoe UI", 10, "bold")).pack(side="right")

        cols = ("hora", "seq", "nivel", "zona", "texto", "emisor", "lat")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        titulos = ("Hora", "Seq", "Nivel", "Zona", "Mensaje", "Emisor", "Lat. (ms)")
        for c, t, ancho in zip(cols, titulos, (80, 50, 80, 170, 400, 90, 70)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=ancho, anchor="w")
        for nivel, (fondo, texto) in COLORES.items():
            self.tree.tag_configure(nivel, background=fondo, foreground=texto)
        self.tree.pack(fill="both", expand=True, pady=(10, 6))

        inferior = ttk.Frame(self)
        inferior.pack(fill="x")
        self.registro = tk.Text(inferior, height=5, state="disabled", font=("Consolas", 9))
        self.registro.pack(side="left", fill="x", expand=True)

        opciones = ttk.LabelFrame(inferior, text="Prueba de falla", padding=8)
        opciones.pack(side="right", padx=(10, 0))
        ttk.Label(opciones, text="Pérdida simulada (%)").grid(row=0, column=0, sticky="w")
        self.perdida = ttk.Spinbox(opciones, from_=0, to=100, width=5)
        self.perdida.set(0)
        self.perdida.grid(row=0, column=1, padx=6)
        ttk.Button(opciones, text="Aplicar", command=self.aplicar_perdida).grid(row=0, column=2)
        ttk.Label(opciones, text="Descarta paquetes en la aplicación\n(no en la red).",
                  foreground="#666666").grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self._poll()

    def aplicar_perdida(self):
        try:
            p = float(self.perdida.get())
        except ValueError:
            return
        p = min(100.0, max(0.0, p))
        self.rx.drop_rate = p / 100.0
        self._log(f"Pérdida simulada: {p:.0f} %")

    def _log(self, texto):
        self.registro.config(state="normal")
        self.registro.insert("end", f"{time.strftime('%H:%M:%S')}  {texto}\n")
        self.registro.see("end")
        self.registro.config(state="disabled")

    def _poll(self):
        try:
            for _ in range(300):
                tipo, dato = self.eventos.get_nowait()
                self._manejar(tipo, dato)
        except queue.Empty:
            pass
        for clave, v in self.vars.items():
            v.set(str(self.rx.stats[clave]))
        senal = self.rx.ultima_senal
        if senal is None:
            self.estado_emisor.set("Emisor: sin señal todavía")
        elif time.time() - senal < 3.5:
            self.estado_emisor.set("Emisor: ACTIVO")
        else:
            self.estado_emisor.set(f"Emisor: SIN SEÑAL hace {time.time() - senal:.0f} s")
        self._after_id = self.after(100, self._poll)

    def _manejar(self, tipo, dato):
        if tipo == "alerta":
            nivel = dato["level"] if dato["level"] in COLORES else "info"
            self.tree.insert("", 0, values=(
                time.strftime("%H:%M:%S", time.localtime(dato["recv_ts"])), dato["seq"], nivel,
                dato["zone"], dato["text"], dato["sender"], f"{dato['lat_ms']:.0f}"), tags=(nivel,))
            fondo, texto = COLORES[nivel]
            self.banner.config(text=f"[{nivel.upper()}] {dato['zone']}: {dato['text']}", bg=fondo, fg=texto)
        elif tipo == "hueco":
            self._log(f"HUECO: faltan seq {dato[0]} a {dato[1]}")
        elif tipo == "tarde":
            self._log(f"seq {dato} llegó fuera de orden")
        elif tipo == "duplicado":
            self._log(f"DUPLICADO: seq {dato}")
        elif tipo == "falta_final":
            self._log(f"El emisor ya envió hasta seq={dato[1]}; aquí falta desde seq={dato[0]}")
        elif tipo == "rechazado":
            self._log(f"RECHAZADO: mensaje sin firma válida de {dato['origen']} (emisor no autorizado)")
        elif tipo == "sesion":
            self._log("Nueva sesión de emisor: contadores reiniciados")
            for item in self.tree.get_children():
                self.tree.delete(item)

    def cerrar(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.rx.cerrar()


if __name__ == "__main__":
    App().mainloop()
