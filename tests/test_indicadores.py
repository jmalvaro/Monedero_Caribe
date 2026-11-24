"""Pruebas de cálculo (PR-05, PR-06, PR-07). No necesitan base de datos."""
import pandas as pd
import pytest

from app import datos as d


def _datos():
    usuarios = pd.DataFrame({
        "id_usuario": ["U1", "U2", "U3", "U4"],
        "fecha_registro": ["2026-01-05", "2026-01-10", "2026-01-20", "2026-02-01"],
        "ciudad": ["Barranquilla", "Cartagena", "Barranquilla", "Soledad"],
        "rango_edad": ["18-24"] * 4, "canal_registro": ["Referido"] * 4})
    comercios = pd.DataFrame({"id_comercio": ["C1"], "categoria": ["Ropa"], "ciudad": ["Barranquilla"]})
    tx = pd.DataFrame({
        "id_transaccion": [f"T{i}" for i in range(1, 6)],
        "fecha_hora": ["2026-01-06 10:00", "2026-01-07 11:00", "2026-01-15 12:00", "2026-01-25 09:00",
                       "2026-01-26 09:00"],
        "id_usuario": ["U1", "U1", "U2", "U3", "U3"],
        "tipo": ["Recarga", "Pago en comercio", "Retiro", "Recarga", "Recarga"],
        "id_comercio": [None, "C1", None, None, None], "valor": [1000, 2000, 3000, 4000, 5000],
        "estado": ["Aprobada", "Aprobada", "Rechazada", "Aprobada", "Revertida"], "canal": ["Web"] * 5})
    reclamos = pd.DataFrame({"id_reclamo": ["R1", "R2"], "id_transaccion": ["T3", "T5"],
                             "fecha_reclamo": ["2026-01-16", "2026-01-27"], "motivo": ["Cobro doble"] * 2,
                             "dias_para_resolver": [2, 5]})
    return d.preparar(usuarios, comercios, tx, reclamos)


def _indicadores(filtros=None):
    f = d.filtrar(_datos(), filtros or {})
    return {i["clave"]: i["valor"] for i in d.calcular_indicadores(f)}


def test_tasa_de_rechazo():  # PR-05
    assert _indicadores()["rechazo"] == pytest.approx(20.0)


def test_usuarios_activos():  # PR-06: U1 y U3 activos de 3 registrados a fin de enero
    assert _indicadores()["activos"] == pytest.approx(200 / 3)


def test_filtro_ciudad():
    valores = _indicadores({"ciudad": ["Barranquilla"]})
    assert valores["activos"] == pytest.approx(100.0)
    assert valores["rechazo"] == 0


def test_reclamos():
    valores = _indicadores()
    assert valores["dias"] == pytest.approx(3.5)
    assert valores["resueltos3"] == pytest.approx(50.0)
    assert valores["rec_mil"] == pytest.approx(400.0)


@pytest.mark.parametrize("clave,valor,color", [  # PR-07: límites de la sección 7
    ("activos", 40, "verde"), ("activos", 39.9, "amarillo"), ("activos", 30, "amarillo"), ("activos", 29.9, "rojo"),
    ("rechazo", 2, "verde"), ("rechazo", 2.01, "amarillo"), ("rechazo", 3, "amarillo"), ("rechazo", 3.01, "rojo"),
    ("dias", 3, "verde"), ("dias", 5, "amarillo"), ("dias", 5.1, "rojo"),
    ("resueltos3", 80, "verde"), ("resueltos3", 70, "amarillo"), ("resueltos3", 69.9, "rojo"),
    ("reversion", 0.5, "verde"), ("reversion", 1, "amarillo"), ("reversion", 1.01, "rojo"),
    ("tx_activo", 3.5, "verde"), ("tx_activo", 3, "amarillo"), ("tx_activo", 2.99, "rojo"),
    ("rec_mil", 10, "verde"), ("rec_mil", 15, "amarillo"), ("rec_mil", 15.1, "rojo"),
    ("activos", None, "sin_datos"),
])
def test_semaforo(clave, valor, color):
    assert d.semaforo(clave, valor) == color
