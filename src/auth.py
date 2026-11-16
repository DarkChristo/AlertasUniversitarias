import hashlib
import hmac
import json
import os

from common import BASE

RUTA_USUARIOS = BASE / "data" / "usuarios.json"
ITERACIONES = 100_000


def hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERACIONES)
    return salt.hex(), h.hex()


def cargar_usuarios():
    with open(RUTA_USUARIOS, encoding="utf-8") as f:
        return json.load(f)["usuarios"]


def autenticar(usuario, password):
    """Devuelve el dict del usuario (sin hash) si las credenciales son correctas, o None."""
    usuario = usuario.strip().lower()
    for u in cargar_usuarios():
        if u["usuario"].lower() == usuario:
            _, h = hash_password(password, u["salt"])
            if hmac.compare_digest(h, u["hash"]):
                return {"usuario": u["usuario"], "nombre": u["nombre"], "rol": u["rol"]}
            return None
    return None
