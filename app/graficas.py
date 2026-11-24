"""Gráficas del tablero (RF-12, RF-14). Cada punto o barra lleva en customdata la llave del detalle (RF-13)."""
import plotly.graph_objects as go

from app.datos import numero

# Colores categóricos en orden fijo (paleta validada para daltonismo). El color sigue a la categoría.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]
PRINCIPAL = SERIES[0]
TEXTO = "#475569"
REJILLA = "#F1F5F9"
META = "#0F172A"


def _base(fig, alto=320):
    fig.update_layout(
        height=alto, margin={"l": 8, "r": 8, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "size": 12, "color": TEXTO},
        separators=",.", hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": "#E2E8F0", "font": {"color": "#0F172A"}},
        legend={"orientation": "h", "y": 1.02, "yanchor": "bottom", "x": 0, "title": None},
        barcornerradius=4, clickmode="event",
    )
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0", automargin=True)
    fig.update_yaxes(gridcolor=REJILLA, zeroline=False, automargin=True)
    return fig


def vacia(mensaje="Sin datos para los filtros elegidos"):
    fig = go.Figure()
    fig.add_annotation(text=mensaje, showarrow=False, font={"size": 13, "color": "#94A3B8"},
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base(fig)


def _linea_meta(fig, valor, texto):
    fig.add_hline(y=valor, line={"color": META, "width": 1, "dash": "dash"},
                  annotation_text=texto, annotation_position="top left",
                  annotation_font={"size": 11, "color": META})


def activos_por_mes(tabla):
    tabla = tabla.dropna(subset=["porcentaje"])
    if tabla.empty:
        return vacia()
    fig = go.Figure(go.Scatter(
        x=tabla["etiqueta"].str.replace(" ", "<br>"), y=tabla["porcentaje"], mode="lines+markers", name="Usuarios activos",
        line={"color": PRINCIPAL, "width": 2}, marker={"size": 9, "color": PRINCIPAL,
                                                         "line": {"color": "#FFFFFF", "width": 2}},
        customdata=list(zip(tabla["mes"].astype(str), tabla["activos"].map(numero), tabla["registrados"].map(numero), tabla["etiqueta"])),
        hovertemplate="<b>%{customdata[3]}</b><br>%{y:.1f} % activos<br>%{customdata[1]} de %{customdata[2]} registrados"
                      "<extra></extra>",
    ))
    _linea_meta(fig, 40, "Meta 40 %")
    tope = max(50, float(tabla["porcentaje"].max()) + 5)
    fig.update_yaxes(range=[0, tope], ticksuffix=" %")
    fig.update_layout(showlegend=False)
    return _base(fig)


def rechazos_por_canal_tipo(tabla, tipos):
    if tabla.empty:
        return vacia()
    fig = go.Figure()
    for i, tipo in enumerate(tipos):
        parte = tabla[tabla["tipo"] == tipo]
        if parte.empty:
            continue
        fig.add_bar(
            x=parte["canal"], y=parte["rechazadas"], name=tipo, marker={"color": SERIES[i % len(SERIES)],
                                                                        "line": {"color": "#FFFFFF", "width": 2}},
            customdata=list(zip(parte["canal"], parte["tipo"])),
            hovertemplate="<b>%{customdata[0]} · %{customdata[1]}</b><br>%{y:,} rechazadas<extra></extra>",
        )
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(title=None)
    return _base(fig)


def rechazo_semanal(tabla):
    if tabla.empty:
        return vacia()
    fig = go.Figure(go.Scatter(
        x=tabla["semana"], y=tabla["tasa"], mode="lines+markers", name="Tasa de rechazo",
        line={"color": SERIES[1], "width": 2}, marker={"size": 8, "color": SERIES[1],
                                                       "line": {"color": "#FFFFFF", "width": 2}},
        customdata=list(zip(tabla["semana"].dt.strftime("%Y-%m-%d"), tabla["rechazadas"].map(numero),
                            tabla["total"].map(numero))),
        hovertemplate="<b>Semana del %{x|%d/%m/%Y}</b><br>%{y:.2f} % rechazo<br>"
                      "%{customdata[1]} de %{customdata[2]} transacciones<extra></extra>",
    ))
    _linea_meta(fig, 2, "Meta 2 %")
    fig.update_yaxes(rangemode="tozero", ticksuffix=" %")
    fig.update_xaxes(tickformat="%d/%m/%y")
    fig.update_layout(showlegend=False)
    return _base(fig)


def activos_por_ciudad_canal(tabla, canales):
    if tabla.empty:
        return vacia()
    orden = tabla.groupby("ciudad")["activos"].sum().sort_values().index.tolist()
    fig = go.Figure()
    for i, canal in enumerate(canales):
        parte = tabla[tabla["canal_registro"] == canal]
        if parte.empty:
            continue
        fig.add_bar(
            y=parte["ciudad"], x=parte["activos"], name=canal, orientation="h",
            marker={"color": SERIES[i % len(SERIES)], "line": {"color": "#FFFFFF", "width": 2}},
            customdata=list(zip(parte["ciudad"], parte["canal_registro"])),
            hovertemplate="<b>%{customdata[0]} · %{customdata[1]}</b><br>%{x:,} usuarios activos<extra></extra>",
        )
    fig.update_layout(barmode="stack", bargap=0.35, legend={"traceorder": "normal"})
    fig.update_yaxes(categoryorder="array", categoryarray=orden, showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=REJILLA)
    return _base(fig)


def reclamos_por_motivo(tabla):
    if tabla.empty:
        return vacia()
    textos = [f"{numero(r)} · {numero(d, 1)} días" + (" ⚠" if d > 3 else "")
              for r, d in zip(tabla["reclamos"], tabla["dias_promedio"])]
    fig = go.Figure(go.Bar(
        y=tabla["motivo"], x=tabla["reclamos"], orientation="h", name="Reclamos",
        marker={"color": PRINCIPAL}, text=textos, textposition="outside", cliponaxis=False,
        textfont={"color": "#0F172A", "size": 12},
        customdata=list(zip(tabla["motivo"], tabla["dias_promedio"].round(1))),
        hovertemplate="<b>%{customdata[0]}</b><br>%{x:,} reclamos<br>%{customdata[1]} días promedio"
                      "<extra></extra>",
    ))
    fig.update_xaxes(range=[0, float(tabla["reclamos"].max()) * 1.7], showgrid=True, gridcolor=REJILLA)
    fig.update_yaxes(showgrid=False)
    fig.update_layout(showlegend=False, bargap=0.4)
    return _base(fig)
