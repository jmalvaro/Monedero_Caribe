"""Pantalla de carga de archivos (RF-04 a RF-08). Solo perfil administrador (RF-02)."""
import base64
import os
import tempfile

from dash import Input, Output, State, dash_table, dcc, html, no_update

from app import auth, db
from app import datos as d

# Orden en que deben aplicarse para que existan los usuarios y comercios antes que las transacciones.
ORDEN = ["usuario", "comercio", "transac", "reclamo"]
ESTILO_TABLA = dict(
    page_size=10, sort_action="native", style_as_list_view=True,
    filter_options={"placeholder_text": "Filtrar…", "case": "insensitive"},
    style_header={"backgroundColor": "#F8FAFC", "color": "#475569", "fontWeight": "600", "fontSize": "12px",
                  "textTransform": "uppercase", "borderBottom": "2px solid #E2E8F0"},
    style_cell={"fontFamily": "Inter, system-ui, sans-serif", "fontSize": "13px", "padding": "8px 10px",
                "textAlign": "left", "borderBottom": "1px solid #F1F5F9", "maxWidth": "420px",
                "overflow": "hidden", "textOverflow": "ellipsis"},
)


def _prioridad(nombre):
    nombre = nombre.lower()
    return next((i for i, clave in enumerate(ORDEN) if clave in nombre), len(ORDEN))


def _historial():
    return db.consultar("""
        SELECT c.id_carga, c.nombre_archivo, to_char(c.fecha_carga, 'DD/MM/YYYY HH24:MI') AS fecha_carga,
               u.nombre_usuario AS cargado_por, c.filas_leidas, c.filas_cargadas, c.filas_rechazadas
        FROM carga_archivo c LEFT JOIN usuario_sistema u ON u.id_usuario_sistema = c.id_usuario_sistema
        ORDER BY c.id_carga DESC""")


def _rechazos(id_carga):
    return db.consultar(
        "SELECT numero_fila, motivo, contenido_original FROM fila_rechazada WHERE id_carga = %s ORDER BY numero_fila",
        (int(id_carga),))


NOMBRES = {"id_carga": "ID carga", "nombre_archivo": "Archivo", "fecha_carga": "Fecha y hora",
           "cargado_por": "Cargado por", "filas_leidas": "Filas leídas", "filas_cargadas": "Filas cargadas",
           "filas_rechazadas": "Filas rechazadas", "numero_fila": "N.º de fila", "motivo": "Motivo",
           "contenido_original": "Contenido original"}


def _columnas(nombres):
    return [{"name": NOMBRES.get(n, n), "id": n} for n in nombres]


def layout():
    try:
        historial = _historial()
        aviso = None
    except Exception as error:  # noqa: BLE001
        historial, aviso = None, html.Div(f"No se pudo leer el historial: {str(error)[:200]}",
                                          className="aviso aviso-error")
    return html.Div([
        html.Div(className="titulo-pagina", children=[
            html.H1("Cargar archivos"),
            html.P("Suba usuarios.xlsx, comercios.csv (separado por punto y coma), transacciones.xlsx y "
                   "reclamos.xlsx. Se revisa cada fila y solo se guardan las correctas.", className="subtitulo"),
        ]),
        aviso,
        html.Section(className="tarjeta", children=[
            dcc.Upload(id="subir", multiple=True, accept=".xlsx,.csv", className="zona-subida", children=html.Div([
                html.Strong("Arrastre los archivos aquí"), html.Span(" o haga clic para elegirlos"),
                html.P("Si sube varios a la vez se aplican en orden: usuarios, comercios, transacciones, reclamos.",
                       className="subtitulo"),
            ])),
            dcc.Loading(html.Div(id="resultado-carga"), type="dot", color="#0EA5E9"),
        ]),
        html.Section(className="tarjeta", children=[
            html.Div(className="tarjeta-encabezado", children=[html.Div([
                html.H2("Historial de cargas"),
                html.P("Haga clic en una carga para ver sus filas rechazadas.", className="subtitulo")])]),
            html.Div(className="tabla-desplazable", children=dash_table.DataTable(
                id="tabla-historial",
                data=historial.to_dict("records") if historial is not None else [],
                columns=_columnas(["id_carga", "nombre_archivo", "fecha_carga", "cargado_por", "filas_leidas",
                                   "filas_cargadas", "filas_rechazadas"]),
                **ESTILO_TABLA)),
        ]),
        html.Section(className="tarjeta", children=[
            html.H2(id="rechazos-titulo", children="Filas rechazadas"),
            html.Div(className="tabla-desplazable", children=dash_table.DataTable(
                id="tabla-rechazos", data=[], columns=_columnas(["numero_fila", "motivo", "contenido_original"]),
                filter_action="native", export_format="csv", **ESTILO_TABLA)),
        ]),
    ])


def registrar(app):
    @app.callback(
        Output("resultado-carga", "children"), Output("tabla-historial", "data"),
        Output("tabla-rechazos", "data", allow_duplicate=True),
        Output("rechazos-titulo", "children", allow_duplicate=True),
        Input("subir", "contents"), State("subir", "filename"), prevent_initial_call=True,
    )
    def subir(contenidos, nombres):
        # RF-02: además de ocultarse, la carga se bloquea en el servidor para el perfil de consulta.
        if not auth.es_admin():
            return html.Div("Solo el administrador puede cargar archivos.", className="aviso aviso-error"), \
                no_update, no_update, no_update
        if not contenidos:
            return no_update, no_update, no_update, no_update
        from carga.cargar import cargar_archivo  # importación tardía: solo se necesita al cargar

        usuario = auth.usuario_actual()
        resultados, ultimo = [], None
        for contenido, nombre in sorted(zip(contenidos, nombres), key=lambda par: _prioridad(par[1])):
            nombre = os.path.basename(nombre)
            if not nombre.lower().endswith((".xlsx", ".csv")):
                resultados.append(html.Li([html.Strong(nombre), ": solo se aceptan archivos .xlsx o .csv"],
                                          className="error"))
                continue
            with tempfile.TemporaryDirectory() as carpeta:
                ruta = os.path.join(carpeta, nombre)
                with open(ruta, "wb") as archivo:
                    archivo.write(base64.b64decode(contenido.split(",", 1)[1]))
                try:
                    r = cargar_archivo(ruta, usuario["id"])
                except SystemExit as error:  # CU-02 excepción: archivo no reconocido
                    resultados.append(html.Li([html.Strong(nombre), f": rechazado completo. {error}"],
                                              className="error"))
                    continue
                except Exception as error:  # noqa: BLE001
                    resultados.append(html.Li([html.Strong(nombre), f": error al cargar. {str(error)[:300]}"],
                                              className="error"))
                    continue
            resultados.append(html.Li([
                html.Strong(nombre), f" → tabla {r['tabla']}: ",
                f"{d.numero(r['filas_leidas'])} leídas, {d.numero(r['filas_cargadas'])} cargadas, ",
                html.Span(f"{d.numero(r['filas_rechazadas'])} rechazadas",
                          className="error" if r["filas_rechazadas"] else ""),
            ]))
            ultimo = nombre
        d.invalidar_cache()
        historial = _historial()
        rechazos, titulo = no_update, no_update
        if ultimo is not None:
            id_carga = int(historial.loc[historial["nombre_archivo"] == ultimo, "id_carga"].max())
            rechazos = _rechazos(id_carga).to_dict("records")
            titulo = f"Filas rechazadas de la carga {id_carga} ({ultimo})"
        reporte = html.Div(className="reporte", children=[html.H3("Reporte de carga"), html.Ul(resultados)])
        return reporte, historial.to_dict("records"), rechazos, titulo

    @app.callback(
        Output("tabla-rechazos", "data"), Output("rechazos-titulo", "children"),
        Input("tabla-historial", "active_cell"), State("tabla-historial", "derived_viewport_data"),
        prevent_initial_call=True,
    )
    def ver_rechazos(celda, filas):
        if not celda or not filas or not auth.es_admin():
            return no_update, no_update
        fila = filas[celda["row"]]
        return _rechazos(fila["id_carga"]).to_dict("records"), \
            f"Filas rechazadas de la carga {fila['id_carga']} ({fila['nombre_archivo']})"
