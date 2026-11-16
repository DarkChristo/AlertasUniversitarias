import argparse
import csv
import pathlib
from collections import defaultdict


def leer(carpeta):
    datos = defaultdict(list)
    for archivo in sorted(pathlib.Path(carpeta).glob("*.csv")):
        if archivo.name == "resumen.csv":
            continue
        with open(archivo, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                datos[fila["node"]].append(fila)
    for filas in datos.values():
        filas.sort(key=lambda r: float(r["recv_ts"]))   # orden real de llegada
    return datos


def analizar_nodo(filas, total):
    vistos = set()
    duplicados = 0
    fuera_de_orden = 0
    max_seq = -1
    latencias = []
    for r in filas:
        if r["type"] != "ALERT":
            continue
        seq = int(r["seq"])
        if seq in vistos:
            duplicados += 1
            continue
        if seq < max_seq:
            fuera_de_orden += 1
        max_seq = max(max_seq, seq)
        vistos.add(seq)
        latencias.append((float(r["recv_ts"]) - float(r["sender_ts"])) * 1000)
    perdidos = [s for s in range(total) if s not in vistos]
    return {
        "recibidos": len(vistos),
        "entrega_pct": 100.0 * len(vistos) / total if total else 0.0,
        "perdidos": perdidos,
        "duplicados": duplicados,
        "fuera_de_orden": fuera_de_orden,
        "lat_prom": sum(latencias) / len(latencias) if latencias else 0.0,
        "lat_min": min(latencias) if latencias else 0.0,
        "lat_max": max(latencias) if latencias else 0.0,
    }


def main():
    p = argparse.ArgumentParser(description="Analiza los CSV de los receptores")
    p.add_argument("carpeta", help="carpeta con los CSV de la prueba, ej. ../logs/prueba1")
    p.add_argument("--total", type=int, default=None,
                   help="total de alertas enviadas (si no se da, se deduce del mayor seq visto)")
    a = p.parse_args()

    datos = leer(a.carpeta)
    if not datos:
        print("No se encontraron CSV en esa carpeta.")
        return

    if a.total is not None:
        total = a.total
    else:
        ultimo = -1
        for filas in datos.values():
            for r in filas:
                ultimo = max(ultimo, int(r["seq"]))
        total = ultimo + 1

    print(f"\nAlertas enviadas (total): {total}\n")
    print(f"{'nodo':<12}{'recib.':>7}{'entrega%':>10}{'perd.':>7}{'dup.':>6}{'desord.':>9}"
          f"{'lat prom':>10}{'lat min':>9}{'lat max':>9}")
    resumen = []
    for nodo in sorted(datos):
        r = analizar_nodo(datos[nodo], total)
        print(f"{nodo:<12}{r['recibidos']:>7}{r['entrega_pct']:>10.1f}{len(r['perdidos']):>7}"
              f"{r['duplicados']:>6}{r['fuera_de_orden']:>9}"
              f"{r['lat_prom']:>10.1f}{r['lat_min']:>9.1f}{r['lat_max']:>9.1f}")
        resumen.append((nodo, r))

    print("\n(latencias en ms; solo son confiables si los relojes de los equipos estan sincronizados)")
    for nodo, r in resumen:
        if r["perdidos"]:
            lista = r["perdidos"]
            texto = ", ".join(str(s) for s in lista[:15]) + (" ..." if len(lista) > 15 else "")
            print(f"Perdidos en {nodo}: {texto}")

    salida = pathlib.Path(a.carpeta) / "resumen.csv"
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nodo", "total", "recibidos", "entrega_pct", "perdidos", "duplicados",
                    "fuera_de_orden", "lat_prom_ms", "lat_min_ms", "lat_max_ms"])
        for nodo, r in resumen:
            w.writerow([nodo, total, r["recibidos"], f"{r['entrega_pct']:.1f}", len(r["perdidos"]),
                        r["duplicados"], r["fuera_de_orden"], f"{r['lat_prom']:.1f}",
                        f"{r['lat_min']:.1f}", f"{r['lat_max']:.1f}"])
    print(f"\nResumen guardado en {salida}")


if __name__ == "__main__":
    main()
