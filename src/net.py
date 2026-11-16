"""Motor de red del sistema de alertas: multicast UDP.

AlertSender   -> envia alertas y latidos AL GRUPO (un solo sendto llega a todos los miembros).
AlertReceiver -> se une al grupo (IP_ADD_MEMBERSHIP) y recibe en un hilo aparte; avisa a la
                 interfaz grafica por medio de una cola (queue) porque Tkinter no es seguro con hilos.
"""
import csv
import datetime
import random
import socket
import struct
import threading
import time

from common import BASE, encode, decode, firmar, verificar


class AlertSender:
    def __init__(self, cfg, iface, usuario):
        self.cfg = cfg
        self.usuario = usuario
        self.clave = cfg.get("hmac_key", "")
        self.destino = (cfg["group"], cfg["port"])
        self.session = int(time.time() * 1000)   # identifica esta sesion de envio
        self.seq = 0
        self.ultimo = -1
        self.heartbeat_s = 1.0
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._hilo = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            # TTL: hasta cuantos saltos de red llega el paquete (1 = red local)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, cfg["ttl"])
            # Permite que receptores de este mismo equipo tambien reciban
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            # Interfaz de salida (clave cuando hay Wi-Fi + Ethernet + adaptadores virtuales)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
        except OSError:
            self.sock.close()
            raise

    def _enviar(self, msg):
        if self.clave:
            firmar(msg, self.clave)
        self.sock.sendto(encode(msg), self.destino)   # UN solo envio llega a todo el grupo

    def iniciar_latidos(self):
        def latido():
            while not self._parar.is_set():
                msg = {"type": "HEARTBEAT", "session": self.session, "last_seq": self.ultimo,
                       "sender_ts": time.time(), "sender": self.usuario}
                try:
                    self._enviar(msg)
                except OSError:
                    pass
                self._parar.wait(self.heartbeat_s)
        self._hilo = threading.Thread(target=latido, daemon=True)
        self._hilo.start()

    def enviar_alerta(self, level, zone, text):
        with self._lock:
            seq = self.seq
            self.seq += 1
            msg = {"type": "ALERT", "session": self.session, "seq": seq, "sender_ts": time.time(),
                   "sender": self.usuario, "level": level, "zone": zone, "text": text}
            self._enviar(msg)
            self.ultimo = seq
        return msg

    def cerrar(self):
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2)
        self.sock.close()


class AlertReceiver(threading.Thread):
    """Eventos que pone en la cola: (tipo, dato)
    alerta, hueco, tarde, duplicado, latido, falta_final, rechazado, descartado, sesion
    """

    def __init__(self, cfg, iface, nodo, eventos, drop_rate=0.0):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.nodo = nodo
        self.eventos = eventos
        self.clave = cfg.get("hmac_key", "")
        self.drop_rate = drop_rate           # perdida SIMULADA a nivel de aplicacion (0 a 1)
        self.ultima_senal = None
        self.stats = self._stats_vacias()
        self._parar = threading.Event()
        self._sesion = None
        self._archivo = None
        self._log = None
        self._vistos = set()
        self._esperado = 0
        self._ultimo_aviso = None

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.sock.bind(("", cfg["port"]))
            # Unirse al grupo multicast (esto dispara el IGMP Join en la red)
            self.mreq = struct.pack("4s4s", socket.inet_aton(cfg["group"]), socket.inet_aton(iface))
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.mreq)
            self.sock.settimeout(0.5)
        except OSError:
            self.sock.close()
            raise

    @staticmethod
    def _stats_vacias():
        return {"recibidas": 0, "huecos": 0, "duplicados": 0, "tardios": 0,
                "descartados": 0, "rechazados": 0}

    # ------------------------------------------------------------------ hilo de recepcion
    def run(self):
        try:
            while not self._parar.is_set():
                try:
                    data, origen = self.sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    continue
                except OSError:
                    break
                recv_ts = time.time()

                if self.drop_rate > 0 and random.random() < self.drop_rate:
                    self.stats["descartados"] += 1
                    self.eventos.put(("descartado", None))
                    continue
                try:
                    msg = decode(data)
                except (ValueError, UnicodeDecodeError):
                    continue
                if self.clave and not verificar(msg, self.clave):
                    self.stats["rechazados"] += 1
                    self.eventos.put(("rechazado", {"origen": origen[0], "sender": msg.get("sender", "?")}))
                    continue
                try:
                    self._procesar(msg, recv_ts)
                except (KeyError, TypeError):
                    continue
        finally:
            self._cerrar_csv()
            try:
                self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, self.mreq)  # IGMP Leave
            except OSError:
                pass
            self.sock.close()

    def _procesar(self, msg, recv_ts):
        if msg.get("session") != self._sesion:
            self._nueva_sesion(msg.get("session"))
        self.ultima_senal = recv_ts

        if msg["type"] == "HEARTBEAT":
            ultimo = msg.get("last_seq", -1)
            self._escribir(["HEARTBEAT", ultimo, msg["sender_ts"], recv_ts, "", ""])
            self.eventos.put(("latido", ultimo))
            if ultimo >= self._esperado and self._ultimo_aviso != (self._esperado, ultimo):
                self._ultimo_aviso = (self._esperado, ultimo)
                self.eventos.put(("falta_final", (self._esperado, ultimo)))
            return

        seq = msg["seq"]
        self._escribir(["ALERT", seq, msg["sender_ts"], recv_ts, msg.get("level", ""), msg.get("zone", "")])
        if seq in self._vistos:
            self.stats["duplicados"] += 1
            self.eventos.put(("duplicado", seq))
            return
        if seq > self._esperado:
            self.eventos.put(("hueco", (self._esperado, seq - 1)))
        elif seq < self._esperado:
            self.stats["tardios"] += 1
            self.eventos.put(("tarde", seq))
        self._vistos.add(seq)
        self._esperado = max(self._esperado, seq + 1)
        self.stats["recibidas"] = len(self._vistos)
        self.stats["huecos"] = self._esperado - len(self._vistos)
        self.eventos.put(("alerta", {
            "seq": seq, "level": msg.get("level", "info"), "zone": msg.get("zone", ""),
            "text": msg.get("text", ""), "sender": msg.get("sender", "?"),
            "lat_ms": (recv_ts - msg["sender_ts"]) * 1000, "recv_ts": recv_ts}))

    # ------------------------------------------------------------------ CSV (formato de analyze.py)
    def _nueva_sesion(self, sesion):
        self._cerrar_csv()
        self._sesion = sesion
        self._vistos = set()
        self._esperado = 0
        self._ultimo_aviso = None
        self.stats = self._stats_vacias()
        (BASE / "logs").mkdir(exist_ok=True)
        nombre = f"{self.nodo}_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"
        self._archivo = open(BASE / "logs" / nombre, "w", newline="", encoding="utf-8")
        self._log = csv.writer(self._archivo)
        self._log.writerow(["node", "type", "seq", "sender_ts", "recv_ts", "level", "zone"])
        self.eventos.put(("sesion", sesion))

    def _escribir(self, fila):
        self._log.writerow([self.nodo] + fila)
        self._archivo.flush()

    def _cerrar_csv(self):
        if self._archivo is not None:
            self._archivo.close()
            self._archivo = None

    def cerrar(self):
        self._parar.set()
        if self.is_alive():
            self.join(timeout=2)
