import argparse
import json
import socket
import threading
import time
from common import load_config, encode, firmar, BASE


def cargar_alertas(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def main():
    cfg = load_config()
    p = argparse.ArgumentParser(description="Emisor de alertas por multicast (linea de comandos)")
    p.add_argument("--count", type=int, default=10, help="cantidad de alertas a enviar")
    p.add_argument("--interval", type=float, default=1.0, help="segundos entre alertas")
    p.add_argument("--heartbeat", type=float, default=1.0, help="segundos entre latidos")
    p.add_argument("--data", default=str(BASE / "data" / "alertas_prueba.json"),
                   help="archivo JSON con las alertas de prueba")
    p.add_argument("--iface", default="0.0.0.0", help="IP local de la interfaz de red a usar")
    a = p.parse_args()

    alertas = cargar_alertas(a.data)
    clave = cfg.get("hmac_key", "")
    session = int(time.time() * 1000)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, cfg["ttl"])
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(a.iface))
    destino = (cfg["group"], cfg["port"])

    def enviar(msg):
        if clave:
            firmar(msg, clave)          # firma HMAC: los receptores de la app rechazan lo no firmado
        sock.sendto(encode(msg), destino)

    estado = {"ultimo": -1}
    parar = threading.Event()

    def latido():
        while not parar.is_set():
            enviar({"type": "HEARTBEAT", "session": session, "last_seq": estado["ultimo"],
                    "sender_ts": time.time(), "sender": "cli"})
            print(f"[LATIDO] last_seq={estado['ultimo']}")
            parar.wait(a.heartbeat)

    hilo = threading.Thread(target=latido, daemon=True)
    hilo.start()

    for seq in range(a.count):
        alerta = alertas[seq % len(alertas)]
        enviar({"type": "ALERT", "session": session, "seq": seq, "sender_ts": time.time(), "sender": "cli",
                "level": alerta["level"], "zone": alerta["zone"], "text": alerta["text"]})
        estado["ultimo"] = seq
        print(f"[ENVIADO] seq={seq} nivel={alerta['level']} zona={alerta['zone']}")
        time.sleep(a.interval)

    time.sleep(a.heartbeat * 3)
    parar.set()
    hilo.join()
    print(f"Listo: {a.count} alertas enviadas (seq 0 a {a.count - 1}).")


if __name__ == "__main__":
    main()
