"""Pantalla principal: filtros, siete tarjetas con semáforo, cuatro gráficas y detalle con un clic."""
import pandas as pd
from dash import Input, Output, State, ctx, dash_table, dcc, html, no_update
from dash.dash_table.Format import Format, Group

from app import datos as d
from app import graficas as g

ETIQUETA_SEMAFORO = {"verde": "Cumple", "amarillo": "Alerta", "rojo": "Crítico", "sin_datos": "Sin datos"}
ICONO_SEMAFORO = {"verde": "✓", "amarillo": "!", "rojo": "✕", "sin_datos": "–"}
NOMBRES_COLUMNA = {
    "id_transaccion": "ID transacción", "fecha_hora": "Fecha y hora", "id_usuario": "Usuario", "ciudad": "Ciudad",
    "tipo": "Tipo", "canal": "Canal", "id_comercio": "Comercio", "categoria": "Categoría", "valor": "Valor (COP)",
    "estado": "Estado", "id_reclamo": "ID reclamo", "fecha_reclamo": "Fecha reclamo", "motivo": "Motivo",
    "dias_para_resolver": "Días para resolver", "canal_registro": "Canal de registro", "rango_edad": "Rango de edad",
    "transacciones_aprobadas": "Transacciones aprobadas", "valor_total": "Valor total (COP)",
}
FILTROS = ["f-mes-ini", "f-mes-fin", "f-ciudad", "f-canal", "f-canal-registro", "f-rango-edad"]


def _dropdown(id_, etiqueta, opciones, multi=True, valor=None):
    return html.Div(className="filtro", children=[
        html.Label(etiqueta, htmlFor=id_),
        dcc.Dropdown(id=id_, options=opciones, value=valor, multi=multi, clearable=multi,
                     placeholder="Todos", searchable=False),
    ])


def _tarjeta_grafica(titulo, subtitulo_id, grafica_id, extra=None):
    return html.Section(className="tarjeta tarjeta-grafica", children=[
        html.Div(className="tarjeta-encabezado", children=[
            html.Div([html.H2(titulo), html.P(id=subtitulo_id, className="subtitulo")]),
            extra,
        ]),
        dcc.Loading(dcc.Graph(id=grafica_id, config={"displayModeBar": False, "responsive": True},
                              className="grafica"), type="dot", color="#0EA5E9"),
    ])


def layout():
    try:
        datos = d.obtener_datos()
    except Exception as error:  # noqa: BLE001
        return html.Div(className="aviso aviso-error", children=[
            html.Strong("No se pudo leer la base de datos. "),
            "Revise las variables del archivo .env y que las tablas existan. ",
            html.Code(str(error)[:300]),
        ])
    if not datos["meses"]:
        return html.Div("La base de datos no tiene transacciones todavía. Un administrador debe cargar los archivos.",
                        className="aviso")
    meses = [{"label": d.nombre_mes(m), "value": str(m)} for m in datos["meses"]]
    op = datos["opciones"]
    filtros = html.Section(className="tarjeta filtros", children=[
        html.Button(["Filtros", html.Span("▾", className="flecha")], id="filtros-boton",
                    className="filtros-boton", n_clicks=0),
        html.Div(id="filtros-cuerpo", className="filtros-cuerpo", children=[
            _dropdown("f-mes-ini", "Mes inicial", meses, multi=False, valor=meses[0]["value"]),
            _dropdown("f-mes-fin", "Mes final", meses, multi=False, valor=meses[-1]["value"]),
            _dropdown("f-ciudad", "Ciudad", op["ciudad"]),
            _dropdown("f-canal", "Canal de la transacción", op["canal"]),
            _dropdown("f-canal-registro", "Canal de registro", op["canal_registro"]),
            _dropdown("f-rango-edad", "Rango de edad", op["rango_edad"]),
            html.Button("Restablecer", id="f-restablecer", className="boton boton-secundario", n_clicks=0),
        ]),
    ])
    selector_rechazos = dcc.RadioItems(
        id="rechazos-vista", className="selector", inline=True, value="canal",
        options=[{"label": "Por canal y tipo", "value": "canal"}, {"label": "Semanal", "value": "semana"}])
    return html.Div([
        html.Div(className="titulo-pagina", children=[
            html.H1("Tablero de uso y fallas"),
            html.P(id="periodo-texto", className="subtitulo"),
        ]),
        filtros,
        html.Div(id="kpis", className="kpis"),
        html.Div(className="rejilla-graficas", children=[
            _tarjeta_grafica("Usuarios activos por mes", "sub-activos-mes", "g-activos-mes"),
            _tarjeta_grafica("Rechazos", "sub-rechazos", "g-rechazos", selector_rechazos),
            _tarjeta_grafica("Usuarios activos por ciudad y canal de registro", "sub-ciudad", "g-ciudad"),
            _tarjeta_grafica("Reclamos por motivo y días de respuesta", "sub-reclamos", "g-reclamos"),
        ]),
        html.Section(id="detalle-caja", className="tarjeta detalle", children=[
            html.Div(className="tarjeta-encabezado", children=[
                html.Div([html.H2(id="detalle-titulo", children="Detalle"),
                          html.P(id="detalle-subtitulo", className="subtitulo",
                                 children="Haga clic en un punto o barra de cualquier gráfica para ver aquí "
                                          "las filas que forman ese valor.")]),
            ]),
            html.Div(className="tabla-desplazable", children=dash_table.DataTable(
                id="detalle-tabla", data=[], columns=[], page_size=10, sort_action="native",
                filter_action="native", export_format="csv", export_headers="display",
                filter_options={"placeholder_text": "Filtrar…", "case": "insensitive"},
                style_as_list_view=True, style_table={"minWidth": "100%"},
                style_header={"backgroundColor": "#F8FAFC", "color": "#475569", "fontWeight": "600",
                              "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #E2E8F0"},
                style_cell={"fontFamily": "Inter, system-ui, sans-serif", "fontSize": "13px", "padding": "8px 10px",
                            "textAlign": "left", "borderBottom": "1px solid #F1F5F9", "whiteSpace": "nowrap"},
                style_cell_conditional=[{"if": {"column_type": "numeric"}, "textAlign": "right",
                                         "fontVariantNumeric": "tabular-nums"}],
                style_data_conditional=[
                    {"if": {"filter_query": '{estado} = "Rechazada"', "column_id": "estado"},
                     "color": "#B91C1C", "fontWeight": "600"},
                    {"if": {"filter_query": '{estado} = "Revertida"', "column_id": "estado"},
                     "color": "#A16207", "fontWeight": "600"},
                ],
            )),
        ]),
    ])


def _tarjeta_kpi(ind):
    color = ind["color"]
    valor = d.numero(ind["valor"], ind["decimales"])
    unidad = ind["unidad"] if ind["valor"] is not None else ""
    return html.Article(className=f"kpi kpi-{color}", children=[
        html.Div(className="kpi-arriba", children=[
            html.H3(ind["nombre"]),
            html.Span([html.Span(ICONO_SEMAFORO[color], className="chip-icono"), ETIQUETA_SEMAFORO[color]],
                      className=f"chip chip-{color}"),
        ]),
        html.Div([html.Span(valor, className="kpi-valor"), html.Span(unidad, className="kpi-unidad")]),
        html.P(ind["detalle"], className="kpi-detalle"),
        html.Div(className="kpi-abajo", children=[
            html.Span(ind["meta"]),
            html.Span(ind["origen"], className="kpi-origen"),
        ]),
    ])


def _filtros(mes_ini, mes_fin, ciudad, canal, canal_registro, rango_edad):
    return {"mes_ini": mes_ini, "mes_fin": mes_fin, "ciudad": ciudad or [], "canal": canal or [],
            "canal_registro": canal_registro or [], "rango_edad": rango_edad or []}


def _tabla(df):
    df = df.copy()
    for columna in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[columna]):
            df[columna] = df[columna].dt.strftime("%d/%m/%Y %H:%M").str.replace(" 00:00", "", regex=False)
    formato = Format(group=Group.yes, group_delimiter=".", decimal_delimiter=",")
    columnas = []
    for c in df.columns:
        columna = {"name": NOMBRES_COLUMNA.get(c, c), "id": c, "type": "text"}
        if pd.api.types.is_numeric_dtype(df[c]):
            columna.update(type="numeric", format=formato)
        columnas.append(columna)
    df = df.astype(object).where(df.notna(), None)
    return df.to_dict("records"), columnas


def registrar(app):
    @app.callback(Output("filtros-cuerpo", "className"), Input("filtros-boton", "n_clicks"))
    def desplegar_filtros(clics):
        return "filtros-cuerpo abierto" if clics and clics % 2 else "filtros-cuerpo"

    @app.callback([Output(f, "value") for f in FILTROS], Input("f-restablecer", "n_clicks"),
                  State("f-mes-ini", "options"), prevent_initial_call=True)
    def restablecer(_, meses):
        return meses[0]["value"], meses[-1]["value"], [], [], [], []

    @app.callback(
        Output("kpis", "children"), Output("periodo-texto", "children"),
        Output("g-activos-mes", "figure"), Output("sub-activos-mes", "children"),
        Output("g-rechazos", "figure"), Output("sub-rechazos", "children"),
        Output("g-ciudad", "figure"), Output("sub-ciudad", "children"),
        Output("g-reclamos", "figure"), Output("sub-reclamos", "children"),
        [Input(f, "value") for f in FILTROS], Input("rechazos-vista", "value"),
    )
    def actualizar(mes_ini, mes_fin, ciudad, canal, canal_registro, rango_edad, vista):
        datos = d.obtener_datos()
        f = d.filtrar(datos, _filtros(mes_ini, mes_fin, ciudad, canal, canal_registro, rango_edad))
        indicadores = d.calcular_indicadores(f)
        periodo = f"Periodo {d.nombre_mes(f['inicio'])} a {d.nombre_mes(f['fin'])}"

        por_mes = d.activos_por_mes(f)
        fig_mes = g.activos_por_mes(por_mes)
        sub_mes = "Porcentaje de registrados con al menos una transacción aprobada · clic en un punto para el detalle"

        if vista == "semana":
            semanal = d.rechazo_semanal(f)
            fig_rech = g.rechazo_semanal(semanal)
            sub_rech = "Tasa de rechazo por semana (lunes a domingo) · clic en un punto para el detalle"
        else:
            tabla = d.rechazos_por_canal_tipo(f)
            fig_rech = g.rechazos_por_canal_tipo(tabla, sorted(datos["tx"]["tipo"].dropna().unique()))
            sub_rech = (f"{d.numero(int(tabla['rechazadas'].sum()))} transacciones rechazadas en el periodo "
                        "· clic en una barra para el detalle")

        ciudad_tabla = d.activos_por_ciudad_canal(f)
        fig_ciudad = g.activos_por_ciudad_canal(ciudad_tabla, datos["opciones"]["canal_registro"])
        sub_ciudad = (f"{d.numero(int(ciudad_tabla['activos'].sum()))} usuarios activos en "
                      f"{d.nombre_mes(f['fin'])} · clic en una barra para el detalle")

        motivos = d.reclamos_por_motivo(f)
        fig_rec = g.reclamos_por_motivo(motivos)
        excede = int((motivos["dias_promedio"] > 3).sum()) if not motivos.empty else 0
        sub_rec = (f"{d.numero(int(motivos['reclamos'].sum()) if not motivos.empty else 0)} reclamos · "
                   f"⚠ {excede} motivo(s) superan la meta de 3 días" if excede else
                   f"{d.numero(int(motivos['reclamos'].sum()) if not motivos.empty else 0)} reclamos · "
                   "todos los motivos dentro de la meta de 3 días")

        return ([_tarjeta_kpi(i) for i in indicadores], periodo, fig_mes, sub_mes, fig_rech, sub_rech,
                fig_ciudad, sub_ciudad, fig_rec, sub_rec)

    @app.callback(
        Output("detalle-titulo", "children"), Output("detalle-subtitulo", "children"),
        Output("detalle-tabla", "data"), Output("detalle-tabla", "columns"),
        Input("g-activos-mes", "clickData"), Input("g-rechazos", "clickData"),
        Input("g-ciudad", "clickData"), Input("g-reclamos", "clickData"),
        [Input(f, "value") for f in FILTROS], Input("rechazos-vista", "value"),
        prevent_initial_call=True,
    )
    def mostrar_detalle(c_mes, c_rech, c_ciudad, c_rec, mes_ini, mes_fin, ciudad, canal, canal_registro,
                        rango_edad, vista):
        if ctx.triggered_id in FILTROS or ctx.triggered_id == "rechazos-vista":
            # Al cambiar un filtro el detalle anterior ya no corresponde: se limpia.
            return "Detalle", "Haga clic en un punto o barra de cualquier gráfica para ver aquí las filas.", [], []
        origen = {"g-activos-mes": ("activos_mes", c_mes),
                  "g-rechazos": ("rechazos_semana" if vista == "semana" else "rechazos_canal", c_rech),
                  "g-ciudad": ("activos_ciudad", c_ciudad), "g-reclamos": ("reclamos_motivo", c_rec)}
        grafica, clic = origen.get(ctx.triggered_id, (None, None))
        if not clic or not clic.get("points") or "customdata" not in clic["points"][0]:
            return no_update, no_update, no_update, no_update
        clave = clic["points"][0]["customdata"]
        f = d.filtrar(d.obtener_datos(), _filtros(mes_ini, mes_fin, ciudad, canal, canal_registro, rango_edad))
        titulo, filas = d.detalle(f, grafica, clave)
        datos_tabla, columnas = _tabla(filas)
        return titulo, f"{d.numero(len(filas))} filas · puede ordenar, filtrar y exportar a CSV", datos_tabla, columnas
