import hashlib
import hmac
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent


def load_config():
    with open(BASE / "config.json", encoding="utf-8") as f:
        return json.load(f)


def encode(msg: dict) -> bytes:
    return json.dumps(msg, ensure_ascii=False).encode("utf-8")


def decode(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


# ---- Firma HMAC: permite al receptor rechazar mensajes de emisores no autorizados ----
def _contenido(msg: dict) -> bytes:
    base = {k: v for k, v in msg.items() if k != "sig"}
    return json.dumps(base, sort_keys=True, ensure_ascii=False).encode("utf-8")


def firmar(msg: dict, clave: str) -> dict:
    msg["sig"] = hmac.new(clave.encode("utf-8"), _contenido(msg), hashlib.sha256).hexdigest()
    return msg


def verificar(msg: dict, clave: str) -> bool:
    esperado = hmac.new(clave.encode("utf-8"), _contenido(msg), hashlib.sha256).hexdigest()
    return hmac.compare_digest(str(msg.get("sig", "")), esperado)
