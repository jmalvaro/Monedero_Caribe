"""Gestión de usuarios del sistema (RF-03, CU-06). Solo perfil administrador."""
from dash import Input, Output, State, ctx, dash_table, dcc, html, no_update

from app import auth


def _datos_usuarios():
    tabla = auth.listar_usuarios()
    tabla["estado"] = tabla["activo"].map(lambda a: "Activo" if a is None or bool(a) else "Inactivo")
    return tabla[["id_usuario_sistema", "nombre_usuario", "perfil", "estado"]].to_dict("records")


def _opciones(filas):
    return [{"label": f"{f['nombre_usuario']} ({f['perfil']}, {f['estado'].lower()})",
             "value": f["id_usuario_sistema"]} for f in filas]


def layout():
    try:
        filas = _datos_usuarios()
        aviso = None
    except Exception as error:  # noqa: BLE001
        filas, aviso = [], html.Div(f"No se pudo leer usuario_sistema: {str(error)[:200]}",
                                    className="aviso aviso-error")
    sin_columna = None if auth.hay_columna_activo() else html.Div(
        "Para desactivar usuarios, la tabla usuario_sistema necesita la columna 'activo'. "
        "Ejecute sql/usuario_sistema_activo.sql en Supabase.", className="aviso")
    return html.Div([
        html.Div(className="titulo-pagina", children=[
            html.H1("Gestión de usuarios"),
            html.P("Cree usuarios del tablero, asígneles perfil y desactívelos. Las contraseñas se guardan cifradas.",
                   className="subtitulo")]),
        aviso, sin_columna,
        html.Div(className="rejilla-dos", children=[
            html.Section(className="tarjeta formulario", children=[
                html.H2("Crear usuario"),
                html.Label("Nombre de usuario", htmlFor="nu-nombre"),
                dcc.Input(id="nu-nombre", type="text", autoComplete="off"),
                html.Label("Contraseña (mínimo 8 caracteres)", htmlFor="nu-clave"),
                dcc.Input(id="nu-clave", type="password", autoComplete="new-password"),
                html.Label("Perfil", htmlFor="nu-perfil"),
                dcc.Dropdown(id="nu-perfil", clearable=False, searchable=False, value=auth.PERFIL_CONSULTA,
                             options=[{"label": "Consulta (solo ve el tablero)", "value": auth.PERFIL_CONSULTA},
                                      {"label": "Administrador (carga archivos y gestiona usuarios)",
                                       "value": auth.PERFIL_ADMIN}]),
                html.Button("Crear usuario", id="nu-crear", className="boton boton-primario", n_clicks=0),
            ]),
            html.Section(className="tarjeta formulario", children=[
                html.H2("Activar o desactivar"),
                html.Label("Usuario", htmlFor="us-elegido"),
                dcc.Dropdown(id="us-elegido", options=_opciones(filas), placeholder="Elija un usuario"),
                html.Div(className="botones", children=[
                    html.Button("Desactivar", id="us-desactivar", className="boton boton-peligro", n_clicks=0),
                    html.Button("Activar", id="us-activar", className="boton boton-secundario", n_clicks=0),
                ]),
            ]),
        ]),
        html.Div(id="us-mensaje"),
        html.Section(className="tarjeta", children=[
            html.H2("Usuarios del sistema"),
            html.Div(className="tabla-desplazable", children=dash_table.DataTable(
                id="us-tabla", data=filas, page_size=10, style_as_list_view=True,
                columns=[{"name": "ID", "id": "id_usuario_sistema"}, {"name": "Usuario", "id": "nombre_usuario"},
                         {"name": "Perfil", "id": "perfil"}, {"name": "Estado", "id": "estado"}],
                style_header={"backgroundColor": "#F8FAFC", "color": "#475569", "fontWeight": "600",
                              "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #E2E8F0"},
                style_cell={"fontFamily": "Inter, system-ui, sans-serif", "fontSize": "13px", "padding": "8px 10px",
                            "textAlign": "left", "borderBottom": "1px solid #F1F5F9"},
                style_data_conditional=[{"if": {"filter_query": '{estado} = "Inactivo"'}, "color": "#94A3B8"}],
            )),
        ]),
    ])


def registrar(app):
    @app.callback(
        Output("us-mensaje", "children"), Output("us-tabla", "data"), Output("us-elegido", "options"),
        Output("nu-nombre", "value"), Output("nu-clave", "value"),
        Input("nu-crear", "n_clicks"), Input("us-desactivar", "n_clicks"), Input("us-activar", "n_clicks"),
        State("nu-nombre", "value"), State("nu-clave", "value"), State("nu-perfil", "value"),
        State("us-elegido", "value"), prevent_initial_call=True,
    )
    def gestionar(_crear, _desactivar, _activar, nombre, clave, perfil, elegido):
        limpiar = (no_update, no_update)
        try:
            if ctx.triggered_id == "nu-crear":
                auth.crear_usuario(nombre, clave, perfil)
                mensaje, limpiar = f"Usuario «{nombre.strip()}» creado con perfil {perfil}.", ("", "")
            else:
                if elegido is None:
                    raise ValueError("Elija un usuario.")
                activar = ctx.triggered_id == "us-activar"
                auth.cambiar_estado_usuario(elegido, activar)
                mensaje = "Usuario activado." if activar else "Usuario desactivado: ya no podrá entrar al tablero."
            filas = _datos_usuarios()
            return html.Div(mensaje, className="aviso aviso-ok"), filas, _opciones(filas), *limpiar
        except (ValueError, PermissionError, RuntimeError) as error:
            return html.Div(str(error), className="aviso aviso-error"), no_update, no_update, no_update, no_update
