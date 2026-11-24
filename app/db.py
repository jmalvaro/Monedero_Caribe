"""Conexión a PostgreSQL en Supabase (sección 19.4)."""
import pandas as pd
import psycopg

from app.config import url_base_datos


def conectar():
    return psycopg.connect(url_base_datos(), connect_timeout=10)


def comprobar_conexion():
    """Devuelve (True, versión) o (False, mensaje). Se llama al arrancar, antes de consultar."""
    try:
        with conectar() as conexion:
            version = conexion.execute("SELECT version()").fetchone()[0]
        return True, version
    except Exception as error:  # noqa: BLE001 - se informa el error tal cual
        return False, str(error)


def consultar(sql, parametros=None):
    with conectar() as conexion:
        cursor = conexion.execute(sql, parametros)
        columnas = [c.name for c in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=columnas)


def ejecutar(sql, parametros=None):
    with conectar() as conexion:
        conexion.execute(sql, parametros)


def columna_existe(tabla, columna):
    filas = consultar(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (tabla, columna),
    )
    return not filas.empty
