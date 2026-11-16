import argparse
import csv
import datetime
import random
import socket
import struct
import time
from common import load_config, decode, BASE


def main():
    cfg = load_config()
    p = argparse.ArgumentParser(description="Receptor de alertas por multicast")
    p.add_argument("--node", required=True, help="nombre del nodo, ej. pc2")
    p.add_argument("--iface", default="0.0.0.0", help="IP local de la interfaz de red a usar")
    p.add_argument("--drop-rate", type=float, default=0.0,
                   help="probabilidad (0 a 1) de descartar un paquete para simular perdida")
    a = p.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", cfg["port"]))

    # Unirse al grupo multicast (dispara el IGMP Join en la red)
    mreq = struct.pack("4s4s", socket.inet_aton(cfg["group"]), socket.inet_aton(a.iface))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    (BASE / "logs").mkdir(exist_ok=True)
    nombre = f"{a.node}_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"
    archivo = open(BASE / "logs" / nombre, "w", newline="", encoding="utf-8")
    log = csv.writer(archivo)
    # En los latidos, la columna seq guarda el last_seq que informa el emisor
    log.writerow(["node", "type", "seq", "sender_ts", "recv_ts", "level", "zone"])

    print(f"[{a.node}] escuchando en {cfg['group']}:{cfg['port']}  (Ctrl+C para salir)")
    if a.drop_rate > 0:
        print(f"[{a.node}] SIMULANDO perdida: se descarta el {a.drop_rate * 100:.0f}% de los paquetes")

    vistos = set()
    esperado = 0
    duplicados = 0
    descartados = 0
    try:
        while True:
            data, origen = sock.recvfrom(4096)
            recv_ts = time.time()

            if a.drop_rate > 0 and random.random() < a.drop_rate:
                descartados += 1
                print("[DESCARTADO] paquete descartado a proposito (perdida simulada)")
                continue

            msg = decode(data)

            if msg.get("type") == "HEARTBEAT":
                ultimo = msg["last_seq"]
                log.writerow([a.node, "HEARTBEAT", ultimo, msg["sender_ts"], recv_ts, "", ""])
                archivo.flush()
                if ultimo >= esperado:
                    print(f"[LATIDO] el emisor ya envio hasta seq={ultimo}; aqui falta desde seq={esperado}")
                continue

            seq = msg["seq"]
            log.writerow([a.node, "ALERT", seq, msg["sender_ts"], recv_ts, msg["level"], msg["zone"]])
            archivo.flush()

            if seq in vistos:
                duplicados += 1
                print(f"[DUPLICADO] seq={seq}")
                continue
            if seq > esperado:
                print(f"[HUECO] faltan seq {esperado} a {seq - 1}")
            elif seq < esperado:
                print(f"[TARDE] seq={seq} llego fuera de orden")
            vistos.add(seq)
            esperado = max(esperado, seq + 1)

            lat = (recv_ts - msg["sender_ts"]) * 1000
            print(f"[RECIBIDO] seq={seq} nivel={msg['level']} zona={msg['zone']} "
                  f"desde={origen[0]} lat={lat:.1f} ms | {msg['text']}")
    except KeyboardInterrupt:
        print("\nCerrando receptor.")
        print(f"Resumen {a.node}: unicos={len(vistos)}, huecos hasta el ultimo visto={esperado - len(vistos)}, "
              f"duplicados={duplicados}, descartados a proposito={descartados}")
    finally:
        archivo.close()


if __name__ == "__main__":
    main()
