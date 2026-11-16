"""Crea o actualiza un usuario en data/usuarios.json.

Uso:  python make_user.py <usuario> <emisor|receptor> "<Nombre completo>" <contraseña>
"""
import json
import sys

from auth import hash_password, RUTA_USUARIOS


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        return
    usuario, rol, nombre, password = sys.argv[1:5]
    if rol not in ("emisor", "receptor"):
        print("El rol debe ser 'emisor' o 'receptor'.")
        return
    datos = {"usuarios": []}
    if RUTA_USUARIOS.exists():
        with open(RUTA_USUARIOS, encoding="utf-8") as f:
            datos = json.load(f)
    datos["usuarios"] = [u for u in datos["usuarios"] if u["usuario"].lower() != usuario.lower()]
    salt, h = hash_password(password)
    datos["usuarios"].append({"usuario": usuario, "nombre": nombre, "rol": rol, "salt": salt, "hash": h})
    RUTA_USUARIOS.parent.mkdir(exist_ok=True)
    with open(RUTA_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"Usuario '{usuario}' guardado con rol {rol}.")


if __name__ == "__main__":
    main()
