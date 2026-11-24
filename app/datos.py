"""Lectura de la base de datos y cálculo de los siete indicadores (RF-09, RF-10, RF-11, sección 7).

El tablero lee solo de PostgreSQL, nunca de los archivos (RN-06).
"""
import threading
import time

import pandas as pd

from app import db
from app.config import MINUTOS_CACHE

# ---------- Indicadores: fórmula, meta y límites del semáforo (sección 7) ----------
# sentido "mayor": más alto es mejor. sentido "menor": más bajo es mejor.
INDICADORES = [
    {"clave": "activos", "nombre": "Usuarios activos del mes", "unidad": "%", "decimales": 1,
     "sentido": "mayor", "verde": 40, "amarillo": 30, "meta": "Meta ≥ 40 %", "origen": "Cliente"},
    {"clave": "rechazo", "nombre": "Tasa de rechazo", "unidad": "%", "decimales": 2,
     "sentido": "menor", "verde": 2, "amarillo": 3, "meta": "Meta ≤ 2 %", "origen": "Cliente"},
    {"clave": "dias", "nombre": "Días promedio para resolver reclamos", "unidad": " días", "decimales": 1,
     "sentido": "menor", "verde": 3, "amarillo": 5, "meta": "Meta ≤ 3 días", "origen": "Cliente"},
    {"clave": "resueltos3", "nombre": "Reclamos resueltos en 3 días o menos", "unidad": "%", "decimales": 1,
     "sentido": "mayor", "verde": 80, "amarillo": 70, "meta": "Meta ≥ 80 %", "origen": "Propuesta del grupo"},
    {"clave": "reversion", "nombre": "Tasa de reversión", "unidad": "%", "decimales": 2,
     "sentido": "menor", "verde": 0.5, "amarillo": 1, "meta": "Meta ≤ 0,5 %", "origen": "Propuesta del grupo"},
    {"clave": "tx_activo", "nombre": "Transacciones aprobadas por usuario activo", "unidad": "", "decimales": 2,
     "sentido": "mayor", "verde": 3.5, "amarillo": 3, "meta": "Meta ≥ 3,5", "origen": "Propuesta del grupo"},
    {"clave": "rec_mil", "nombre": "Reclamos por cada 1.000 transacciones", "unidad": "", "decimales": 1,
     "sentido": "menor", "verde": 10, "amarillo": 15, "meta": "Meta ≤ 10", "origen": "Propuesta del grupo"},
]
INDICADOR = {i["clave"]: i for i in INDICADORES}


def semaforo(clave, valor):
    """Devuelve 'verde', 'amarillo', 'rojo' o 'sin_datos' según los límites de la sección 7."""
    if valor is None or pd.isna(valor):
        return "sin_datos"
    ind = INDICADOR[clave]
    valor = round(float(valor), ind["decimales"])
    if ind["sentido"] == "mayor":
        if valor >= ind["verde"]:
            return "verde"
        return "amarillo" if valor >= ind["amarillo"] else "rojo"
    if valor <= ind["verde"]:
        return "verde"
    return "amarillo" if valor <= ind["amarillo"] else "rojo"


# ---------- Formato de números en español ----------

def numero(valor, decimales=0):
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def nombre_mes(periodo):
    periodo = pd.Period(periodo, "M")
    return f"{MESES[periodo.month - 1]} {periodo.year}"


# ---------- Lectura con caché ----------
_cache = {"momento": 0.0, "datos": None}
_candado = threading.Lock()


def invalidar_cache():
    with _candado:
        _cache["momento"] = 0.0


def _leer_todo():
    usuarios = db.consultar(
        "SELECT id_usuario, fecha_registro, ciudad, rango_edad, canal_registro FROM usuario")
    comercios = db.consultar("SELECT id_comercio, categoria, ciudad AS ciudad_comercio FROM comercio")
    transacciones = db.consultar(
        "SELECT id_transaccion, fecha_hora, id_usuario, tipo, id_comercio, valor, estado, canal FROM transaccion")
    reclamos = db.consultar(
        "SELECT id_reclamo, id_transaccion, fecha_reclamo, motivo, dias_para_resolver FROM reclamo")
    return preparar(usuarios, comercios, transacciones, reclamos)


def preparar(usuarios, comercios, transacciones, reclamos):
    """Une las tablas y agrega columnas de mes y semana. Separado de la lectura para poder probarlo."""
    usuarios = usuarios.copy()
    usuarios["fecha_registro"] = pd.to_datetime(usuarios["fecha_registro"], errors="coerce")

    tx = transacciones.copy()
    tx["fecha_hora"] = pd.to_datetime(tx["fecha_hora"], errors="coerce")
    tx["valor"] = pd.to_numeric(tx["valor"], errors="coerce")
    tx = tx.merge(usuarios[["id_usuario", "ciudad", "rango_edad", "canal_registro"]], on="id_usuario", how="left")
    tx = tx.merge(comercios[["id_comercio", "categoria"]], on="id_comercio", how="left")
    tx["mes"] = tx["fecha_hora"].dt.to_period("M")
    tx["semana"] = tx["fecha_hora"].dt.to_period("W-SUN").dt.start_time

    rec = reclamos.copy()
    rec["fecha_reclamo"] = pd.to_datetime(rec["fecha_reclamo"], errors="coerce")
    rec["dias_para_resolver"] = pd.to_numeric(rec["dias_para_resolver"], errors="coerce")
    # RN-05: para filtrar reclamos por ciudad o canal se usa la transacción y el usuario relacionados.
    rec = rec.merge(
        tx[["id_transaccion", "id_usuario", "canal", "tipo", "estado", "valor", "ciudad", "rango_edad",
            "canal_registro"]],
        on="id_transaccion", how="left")
    rec["mes"] = rec["fecha_reclamo"].dt.to_period("M")

    meses = sorted(set(tx["mes"].dropna()) | set(rec["mes"].dropna()))
    opciones = {
        "ciudad": sorted(usuarios["ciudad"].dropna().unique()),
        "canal": sorted(tx["canal"].dropna().unique()),
        "canal_registro": sorted(usuarios["canal_registro"].dropna().unique()),
        "rango_edad": sorted(usuarios["rango_edad"].dropna().unique()),
    }
    return {"usuarios": usuarios, "tx": tx, "reclamos": rec, "meses": meses, "opciones": opciones}


def obtener_datos():
    with _candado:
        vencido = time.time() - _cache["momento"] > MINUTOS_CACHE * 60
        if _cache["datos"] is None or vencido:
            _cache["datos"] = _leer_todo()
            _cache["momento"] = time.time()
        return _cache["datos"]


# ---------- Filtros (RF-11) ----------

def _en_lista(serie, valores):
    return serie.isin(valores) if valores else pd.Series(True, index=serie.index)


def filtrar(datos, filtros):
    """Aplica periodo, ciudad, canal, canal de registro y rango de edad.

    Ciudad, canal de registro y rango de edad son del usuario de la billetera.
    Canal es el de la transacción (no aplica a los usuarios registrados).
    SUPUESTO: los reclamos se ubican en el periodo por su fecha_reclamo.
    """
    meses = datos["meses"]
    if not meses:
        return None
    inicio = pd.Period(filtros.get("mes_ini") or meses[0], "M")
    fin = pd.Period(filtros.get("mes_fin") or meses[-1], "M")
    if inicio > fin:
        inicio, fin = fin, inicio

    u = datos["usuarios"]
    u = u[_en_lista(u["ciudad"], filtros.get("ciudad")) & _en_lista(u["rango_edad"], filtros.get("rango_edad"))
          & _en_lista(u["canal_registro"], filtros.get("canal_registro"))]

    def por_usuario(tabla):
        return (_en_lista(tabla["ciudad"], filtros.get("ciudad"))
                & _en_lista(tabla["rango_edad"], filtros.get("rango_edad"))
                & _en_lista(tabla["canal_registro"], filtros.get("canal_registro"))
                & _en_lista(tabla["canal"], filtros.get("canal")))

    tx = datos["tx"]
    tx = tx[por_usuario(tx) & (tx["mes"] >= inicio) & (tx["mes"] <= fin)]
    rec = datos["reclamos"]
    rec = rec[por_usuario(rec) & (rec["mes"] >= inicio) & (rec["mes"] <= fin)]
    return {"usuarios": u, "tx": tx, "reclamos": rec, "inicio": inicio, "fin": fin,
            "meses": list(pd.period_range(inicio, fin, freq="M"))}


# ---------- Cálculos ----------

def registrados_hasta(usuarios, mes):
    """RN-02. SUPUESTO (RC-10 pendiente): usuarios sin fecha_registro no se cuentan como registrados."""
    return int((usuarios["fecha_registro"] <= mes.end_time).sum())


# SUPUESTO (RC-10 pendiente con el docente): solo cuentan como activos los usuarios que ya estaban
# registrados al cierre del mes. Así el porcentaje nunca supera el 100 % aunque existan transacciones con
# fecha anterior al registro. Para usar la fórmula literal (sin esta condición), poner False.
SOLO_ACTIVOS_REGISTRADOS = True


def activos_en(tx, mes, usuarios=None):
    """RN-01: usuarios distintos con al menos una transacción Aprobada en el mes."""
    ids = tx.loc[(tx["mes"] == mes) & (tx["estado"] == "Aprobada"), "id_usuario"]
    if SOLO_ACTIVOS_REGISTRADOS and usuarios is not None:
        registrados = usuarios.loc[usuarios["fecha_registro"] <= mes.end_time, "id_usuario"]
        ids = ids[ids.isin(registrados)]
    return int(ids.nunique())


def activos_por_mes(f):
    filas = []
    for mes in f["meses"]:
        registrados = registrados_hasta(f["usuarios"], mes)
        activos = activos_en(f["tx"], mes, f["usuarios"])
        filas.append({"mes": mes, "etiqueta": nombre_mes(mes), "activos": activos, "registrados": registrados,
                      "porcentaje": activos / registrados * 100 if registrados else None})
    return pd.DataFrame(filas)


def _division(a, b, factor=1.0):
    return a / b * factor if b else None


def calcular_indicadores(f):
    """Los siete indicadores. 1 y 6 son 'del mes': se calculan para el último mes del periodo (SUPUESTO).
    Los demás se calculan sobre todo el periodo elegido."""
    tx, rec, ultimo = f["tx"], f["reclamos"], f["fin"]
    total = len(tx)
    rechazadas = int((tx["estado"] == "Rechazada").sum())
    revertidas = int((tx["estado"] == "Revertida").sum())
    registrados = registrados_hasta(f["usuarios"], ultimo)
    activos = activos_en(tx, ultimo, f["usuarios"])
    aprobadas_mes = int(((tx["mes"] == ultimo) & (tx["estado"] == "Aprobada")).sum())
    dias = rec["dias_para_resolver"].dropna()
    n_rec = len(rec)

    valores = {
        "activos": (_division(activos, registrados, 100),
                    f"{numero(activos)} de {numero(registrados)} registrados · {nombre_mes(ultimo)}"),
        "rechazo": (_division(rechazadas, total, 100), f"{numero(rechazadas)} rechazadas de {numero(total)}"),
        "dias": (dias.mean() if len(dias) else None, f"{numero(n_rec)} reclamos en el periodo"),
        "resueltos3": (_division(int((dias <= 3).sum()), len(dias), 100),
                       f"{numero(int((dias <= 3).sum()))} de {numero(len(dias))} reclamos"),
        "reversion": (_division(revertidas, total, 100), f"{numero(revertidas)} revertidas de {numero(total)}"),
        "tx_activo": (_division(aprobadas_mes, activos),
                      f"{numero(aprobadas_mes)} aprobadas · {nombre_mes(ultimo)}"),
        "rec_mil": (_division(n_rec, total, 1000), f"{numero(n_rec)} reclamos / {numero(total)} transacciones"),
    }
    resultado = []
    for ind in INDICADORES:
        valor, detalle = valores[ind["clave"]]
        resultado.append({**ind, "valor": valor, "detalle": detalle, "color": semaforo(ind["clave"], valor)})
    return resultado


def rechazos_por_canal_tipo(f):
    rech = f["tx"][f["tx"]["estado"] == "Rechazada"]
    return rech.groupby(["canal", "tipo"]).size().reset_index(name="rechazadas")


def rechazo_semanal(f):
    """RF-14: tasa de rechazo por semana (semana de lunes a domingo)."""
    tx = f["tx"]
    if tx.empty:
        return pd.DataFrame(columns=["semana", "total", "rechazadas", "tasa"])
    grupo = tx.groupby("semana").agg(total=("id_transaccion", "size"),
                                     rechazadas=("estado", lambda s: int((s == "Rechazada").sum())))
    grupo["tasa"] = grupo["rechazadas"] / grupo["total"] * 100
    return grupo.reset_index()


def activos_por_ciudad_canal(f):
    """Usuarios activos del último mes del periodo, por ciudad y canal de registro."""
    tx = f["tx"]
    activos = tx[(tx["mes"] == f["fin"]) & (tx["estado"] == "Aprobada")].drop_duplicates("id_usuario")
    if SOLO_ACTIVOS_REGISTRADOS:
        registrados = f["usuarios"].loc[f["usuarios"]["fecha_registro"] <= f["fin"].end_time, "id_usuario"]
        activos = activos[activos["id_usuario"].isin(registrados)]
    return activos.groupby(["ciudad", "canal_registro"]).size().reset_index(name="activos")


def reclamos_por_motivo(f):
    rec = f["reclamos"]
    if rec.empty:
        return pd.DataFrame(columns=["motivo", "reclamos", "dias_promedio"])
    return (rec.groupby("motivo").agg(reclamos=("id_reclamo", "size"), dias_promedio=("dias_para_resolver", "mean"))
            .reset_index().sort_values("reclamos"))


# ---------- Detalle con un clic (RF-13) ----------
COLUMNAS_TX = ["id_transaccion", "fecha_hora", "id_usuario", "ciudad", "tipo", "canal", "id_comercio",
               "categoria", "valor", "estado"]
COLUMNAS_REC = ["id_reclamo", "fecha_reclamo", "id_transaccion", "id_usuario", "ciudad", "canal", "motivo",
                "dias_para_resolver"]


def detalle(f, grafica, clave):
    """Devuelve (título, DataFrame) con las filas que forman el valor clicado."""
    tx, rec = f["tx"], f["reclamos"]
    if grafica == "activos_mes":
        mes = pd.Period(clave[0], "M")
        filas = tx[(tx["mes"] == mes) & (tx["estado"] == "Aprobada")]
        return f"Transacciones aprobadas de {nombre_mes(mes)}", filas[COLUMNAS_TX]
    if grafica == "rechazos_canal":
        canal, tipo = clave[0], clave[1]
        filas = tx[(tx["estado"] == "Rechazada") & (tx["canal"] == canal) & (tx["tipo"] == tipo)]
        return f"Transacciones rechazadas · {canal} · {tipo}", filas[COLUMNAS_TX]
    if grafica == "rechazos_semana":
        semana = pd.Timestamp(clave[0])
        filas = tx[(tx["semana"] == semana) & (tx["estado"] == "Rechazada")]
        return f"Transacciones rechazadas de la semana del {semana:%d/%m/%Y}", filas[COLUMNAS_TX]
    if grafica == "activos_ciudad":
        ciudad, canal_registro = clave[0], clave[1]
        aprobadas = tx[(tx["mes"] == f["fin"]) & (tx["estado"] == "Aprobada") & (tx["ciudad"] == ciudad)
                       & (tx["canal_registro"] == canal_registro)]
        filas = (aprobadas.groupby(["id_usuario", "ciudad", "canal_registro", "rango_edad"])
                 .agg(transacciones_aprobadas=("id_transaccion", "size"), valor_total=("valor", "sum"))
                 .reset_index())
        return f"Usuarios activos de {ciudad} · {canal_registro} · {nombre_mes(f['fin'])}", filas
    if grafica == "reclamos_motivo":
        filas = rec[rec["motivo"] == clave[0]]
        return f"Reclamos por «{clave[0]}»", filas[COLUMNAS_REC]
    return "", pd.DataFrame()
