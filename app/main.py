"""Aplicación Dash del tablero Monedero Caribe.

Arranque local:   python -m app.main
Producción:       gunicorn app.main:server
"""
import sys

from dash import Dash, Input, Output, dcc, html

from app import auth, db
from app.config import DEPURACION, PUERTO_APP, clave_secreta
from app.paginas import carga, tablero, usuarios

app = Dash(
    __name__,
    title="Monedero Caribe · Tablero BI",
    suppress_callback_exceptions=True,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server
server.secret_key = clave_secreta()
server.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
auth.registrar_rutas(server)


def barra_superior():
    usuario = auth.usuario_actual() or {"nombre": "", "admin": False}
    enlaces = [dcc.Link("Tablero", href="/", className="nav-enlace")]
    if usuario["admin"]:  # RF-02: las opciones de administrador solo aparecen para ese perfil
        enlaces += [dcc.Link("Cargar archivos", href="/carga", className="nav-enlace"),
                    dcc.Link("Gestión de usuarios", href="/usuarios", className="nav-enlace")]
    perfil = "Administrador" if usuario["admin"] else "Consulta"
    return html.Header(className="barra-superior", children=[
        html.Div(className="marca", children=[html.Span("MC", className="logo"), html.Span("Monedero Caribe")]),
        html.Nav(enlaces, className="nav"),
        html.Div(className="sesion", children=[
            html.Span(usuario["nombre"], className="sesion-nombre"),
            html.Span(perfil, className="chip chip-perfil"),
            # RF-15: salir desde cualquier pantalla (enlace normal para que Flask limpie la sesión)
            html.A("Cerrar sesión", href="/logout", className="nav-enlace salir"),
        ]),
    ])


def estructura():
    """Se construye en cada carga de página para leer la sesión del usuario."""
    return html.Div([
        dcc.Location(id="url"),
        barra_superior(),
        html.Main(id="contenido", className="contenido"),
        html.Footer("Monedero Caribe · Tablero de Inteligencia de Negocios · Proyecto académico",
                    className="pie"),
    ])


app.layout = estructura


@app.callback(Output("contenido", "children"), Input("url", "pathname"))
def mostrar_pagina(ruta):
    if ruta in ("/carga", "/usuarios") and not auth.es_admin():
        return html.Div("Esta opción es solo para el perfil de administrador.", className="aviso aviso-error")
    if ruta == "/carga":
        return carga.layout()
    if ruta == "/usuarios":
        return usuarios.layout()
    return tablero.layout()


tablero.registrar(app)
carga.registrar(app)
usuarios.registrar(app)


def comprobar_al_arrancar():
    ok, detalle = db.comprobar_conexion()
    if ok:
        print(f"Conexión a la base de datos correcta: {detalle.split(',')[0]}")
    else:
        print(f"ERROR: no se pudo conectar a la base de datos. Revise el archivo .env.\n{detalle}", file=sys.stderr)
    return ok


if __name__ == "__main__":
    comprobar_al_arrancar()
    app.run(host="0.0.0.0", port=PUERTO_APP, debug=DEPURACION)
