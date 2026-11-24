import os
import sys

import pandas as pd
import psycopg
from app.config import url_base_datos



COLUMNAS = {
    "usuario": ["id_usuario", "fecha_registro", "ciudad", "rango_edad", "canal_registro"],
    "comercio": ["id_comercio", "categoria", "ciudad"],
    "transaccion": ["id_transaccion", "fecha_hora", "id_usuario", "tipo",
                    "id_comercio", "valor", "estado", "canal"],
    "reclamo": ["id_reclamo", "id_transaccion", "fecha_reclamo", "motivo", "dias_para_resolver"],
}

PERMITIDOS = {
    "ciudad": ["Barranquilla", "Cartagena", "Riohacha", "Santa Marta", "Soledad", "Valledupar"],
    "rango_edad": ["18-24", "25-34", "35-44", "45-59", "60+"],
    "canal_registro": ["Punto físico", "Redes sociales", "Referido", "Tienda de aplicaciones"],
    "categoria": ["Droguería", "Recargas celular", "Restaurante", "Ropa",
                  "Servicios públicos", "Tienda de barrio", "Transporte"],
    "tipo": ["Pago en comercio", "Recarga", "Transferencia", "Retiro"],
    "estado": ["Aprobada", "Rechazada", "Revertida"],
    "canal": ["App Android", "App iOS", "Web"],
    "motivo": ["Bloqueo de cuenta", "Cobro doble", "Pago no reflejado", "Transferencia no recibida"],
}


def leer(ruta):
    if ruta.lower().endswith(".csv"):
        datos = pd.read_csv(ruta, sep=";", header=None, dtype=object, encoding="utf-8-sig")
    else:
        datos = pd.read_excel(ruta, header=None, dtype=object)
    for tabla, columnas in COLUMNAS.items():
        fila_titulos = datos.index[datos[0] == columnas[0]]
        if len(fila_titulos) > 0:
            datos = datos.iloc[fila_titulos[0] + 1:, :len(columnas)]
            datos.columns = columnas
            datos.index = datos.index + 1
            return tabla, datos
    raise SystemExit(f"{ruta}: no es un archivo de usuarios, comercios, transacciones ni reclamos.")


def sin_adornos(columna):
    return (columna.astype(str).str.normalize("NFD").str.encode("ascii", "ignore")
            .str.decode("ascii").str.strip().str.lower())


def texto_oficial(columna, permitidos):
    oficiales = dict(zip(sin_adornos(pd.Series(permitidos)), permitidos))
    return sin_adornos(columna).map(oficiales)


def a_fecha(columna):
    es_texto = columna.map(lambda x: isinstance(x, str))
    fechas = pd.to_datetime(columna.where(~es_texto), errors="coerce")
    fechas_de_texto = pd.to_datetime(columna.where(es_texto), format="%d/%m/%Y", errors="coerce")
    return fechas.fillna(fechas_de_texto)


def a_numero(columna):
    limpio = columna.map(lambda x: x.replace(".", "").replace(",", ".") if isinstance(x, str) else x)
    return pd.to_numeric(limpio, errors="coerce")


def cargar_archivo(ruta, id_usuario_sistema=None):
    tabla, original = leer(ruta)
    columnas = COLUMNAS[tabla]
    llave = columnas[0]
    datos = original.copy()
    datos["error"] = ""

    def marcar(condicion, mensaje):
        datos.loc[condicion & (datos["error"] == ""), "error"] = mensaje

    with psycopg.connect(url_base_datos()) as conexion:

        def guardados(otra_tabla):
            return {fila[0] for fila in conexion.execute(f"SELECT {COLUMNAS[otra_tabla][0]} FROM {otra_tabla}")}

        marcar(original.duplicated(), "fila repetida")

        for columna in columnas:
            if columna.startswith("id_"):
                datos[columna] = datos[columna].str.strip().str.upper()
            if columna in PERMITIDOS:
                datos[columna] = texto_oficial(datos[columna], PERMITIDOS[columna])
                marcar(datos[columna].isna(), f"{columna} vacío o no permitido")

        marcar(datos[llave].isna(), f"{llave} vacío")
        marcar(datos[llave].isin(guardados(tabla)), f"{llave} ya existe en la base")
        marcar(datos[llave].duplicated(), f"{llave} repetido en el archivo")

        if tabla == "usuario":
            datos["fecha_registro"] = a_fecha(datos["fecha_registro"])

        if tabla == "transaccion":
            datos["fecha_hora"] = a_fecha(datos["fecha_hora"])
            datos["valor"] = a_numero(datos["valor"])
            marcar(datos["fecha_hora"].isna(), "fecha_hora vacía")
            marcar(datos["valor"].isna(), "valor vacío")
            marcar(datos["valor"] <= 0, "valor negativo o cero")
            marcar(~datos["id_usuario"].isin(guardados("usuario")), "el usuario no existe")
            marcar(datos["id_comercio"].notna() & ~datos["id_comercio"].isin(guardados("comercio")),
                   "el comercio no existe")

        if tabla == "reclamo":
            datos["fecha_reclamo"] = a_fecha(datos["fecha_reclamo"])
            datos["dias_para_resolver"] = a_numero(datos["dias_para_resolver"])
            marcar(datos["fecha_reclamo"].isna(), "fecha_reclamo vacía")
            marcar(datos["dias_para_resolver"].isna(), "dias_para_resolver vacío")
            marcar(datos["dias_para_resolver"] < 0, "dias_para_resolver negativo")
            marcar(~datos["id_transaccion"].isin(guardados("transaccion")),
                   "la transacción no existe o fue rechazada")

        buenas = datos[datos["error"] == ""]
        malas = datos[datos["error"] != ""]

        id_carga = conexion.execute(
            """INSERT INTO carga_archivo (nombre_archivo, id_usuario_sistema, filas_leidas,
               filas_cargadas, filas_rechazadas) VALUES (%s, %s, %s, %s, %s) RETURNING id_carga""",
            (os.path.basename(ruta), id_usuario_sistema, len(datos), len(buenas), len(malas))).fetchone()[0]

        filas_buenas = buenas[columnas].astype(object).where(buenas[columnas].notna(), None)
        nombres = ", ".join(columnas)
        marcas = ", ".join(["%s"] * (len(columnas) + 1))
        conexion.cursor().executemany(
            f"INSERT INTO {tabla} ({nombres}, id_carga) VALUES ({marcas})",
            [fila + [id_carga] for fila in filas_buenas.values.tolist()])

        como_venia = original.loc[malas.index].astype(object).fillna("").astype(str).agg("; ".join, axis=1)
        conexion.cursor().executemany(
            "INSERT INTO fila_rechazada (id_carga, numero_fila, motivo, contenido_original) VALUES (%s, %s, %s, %s)",
            list(zip([id_carga] * len(malas), malas.index.tolist(), malas["error"], como_venia)))

    return {"archivo": os.path.basename(ruta), "tabla": tabla, "filas_leidas": len(datos),
            "filas_cargadas": len(buenas), "filas_rechazadas": len(malas)}


if __name__ == "__main__":
    for ruta in sys.argv[1:]:
        print(cargar_archivo(ruta))
