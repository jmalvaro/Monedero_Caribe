"""Lectura de la configuración desde variables de entorno (.env).

Ningún dato de conexión ni contraseña vive en el código (RNF-02, sección 19.3).
"""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _requerida(nombre):
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise RuntimeError(
            f"Falta la variable de entorno {nombre}. Copie .env.example a .env y complete los valores."
        )
    return valor


def url_base_datos():
    """Cadena de conexión a PostgreSQL (Supabase).

    Si existe DATABASE_URL se usa tal cual (es la que usa cargar.py).
    Si no, se arma con DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD (sección 19.3).
    """
    directa = os.environ.get("DATABASE_URL", "").strip()
    if directa:
        return directa
    usuario = quote_plus(_requerida("DB_USER"))
    clave = quote_plus(_requerida("DB_PASSWORD"))
    host = _requerida("DB_HOST")
    puerto = os.environ.get("DB_PORT", "5432").strip() or "5432"
    base = _requerida("DB_NAME")
    modo_ssl = os.environ.get("DB_SSLMODE", "require").strip() or "require"
    return f"postgresql://{usuario}:{clave}@{host}:{puerto}/{base}?sslmode={modo_ssl}"


def clave_secreta():
    return _requerida("SECRET_KEY")


MINUTOS_CACHE = int(os.environ.get("MINUTOS_CACHE", "5"))
PUERTO_APP = int(os.environ.get("PORT", "8050"))
DEPURACION = os.environ.get("DASH_DEBUG", "false").lower() == "true"
