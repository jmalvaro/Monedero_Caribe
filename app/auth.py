"""Inicio de sesión, perfiles y gestión de usuarios del sistema (RF-01, RF-02, RF-03, RF-15).

Tabla usada (diagrama de la base de datos):
    usuario_sistema(id_usuario_sistema, nombre_usuario, contrasena_hash, perfil)
SUPUESTO: la columna 'activo' no está en el diagrama. Si existe se usa para desactivar
usuarios (RF-03); el script sql/usuario_sistema_activo.sql la agrega.
"""
from functools import lru_cache
from html import escape

from flask import redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from app import db

PERFIL_ADMIN = "administrador"
PERFIL_CONSULTA = "consulta"
# SUPUESTO: el perfil se guarda como texto. Se aceptan estas variantes para administrador.
_VALORES_ADMIN = {"administrador", "admin"}

RUTAS_PUBLICAS = ("/login", "/assets/", "/_favicon", "/salud")
RUTAS_SOLO_ADMIN = ("/carga", "/usuarios")


@lru_cache(maxsize=1)
def hay_columna_activo():
    return db.columna_existe("usuario_sistema", "activo")


def es_admin_perfil(perfil):
    return str(perfil or "").strip().lower() in _VALORES_ADMIN


def usuario_actual():
    if "id_usuario_sistema" not in session:
        return None
    return {
        "id": session["id_usuario_sistema"],
        "nombre": session["nombre_usuario"],
        "admin": session.get("admin", False),
    }


def es_admin():
    usuario = usuario_actual()
    return bool(usuario and usuario["admin"])


def _verificar_clave(clave, guardada):
    guardada = guardada or ""
    if guardada.startswith("$2"):  # hash bcrypt, por si la base ya tiene usuarios creados así
        try:
            import bcrypt

            return bcrypt.checkpw(clave.encode(), guardada.encode())
        except Exception:  # noqa: BLE001
            return False
    try:
        return check_password_hash(guardada, clave)
    except Exception:  # noqa: BLE001
        return False


def autenticar(nombre_usuario, clave):
    columnas = "id_usuario_sistema, nombre_usuario, contrasena_hash, perfil"
    if hay_columna_activo():
        columnas += ", activo"
    filas = db.consultar(
        f"SELECT {columnas} FROM usuario_sistema WHERE lower(nombre_usuario) = lower(%s)",
        (nombre_usuario.strip(),),
    )
    if filas.empty:
        return None
    fila = filas.iloc[0]
    if "activo" in filas.columns and fila["activo"] is not None and not bool(fila["activo"]):
        return None
    if not _verificar_clave(clave, fila["contrasena_hash"]):
        return None
    return {
        "id": int(fila["id_usuario_sistema"]),
        "nombre": fila["nombre_usuario"],
        "admin": es_admin_perfil(fila["perfil"]),
    }


# ---------- Gestión de usuarios (solo administrador) ----------

def listar_usuarios():
    extra = ", activo" if hay_columna_activo() else ", TRUE AS activo"
    return db.consultar(
        f"SELECT id_usuario_sistema, nombre_usuario, perfil{extra} FROM usuario_sistema ORDER BY nombre_usuario"
    )


def crear_usuario(nombre_usuario, clave, perfil):
    if not es_admin():
        raise PermissionError("Solo el administrador puede crear usuarios.")
    nombre_usuario = (nombre_usuario or "").strip()
    if len(nombre_usuario) < 3:
        raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
    if len(clave or "") < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    if perfil not in (PERFIL_ADMIN, PERFIL_CONSULTA):
        raise ValueError("Perfil no válido.")
    existe = db.consultar(
        "SELECT 1 FROM usuario_sistema WHERE lower(nombre_usuario) = lower(%s)", (nombre_usuario,)
    )
    if not existe.empty:
        raise ValueError("Ya existe un usuario con ese nombre.")
    db.ejecutar(
        "INSERT INTO usuario_sistema (nombre_usuario, contrasena_hash, perfil) VALUES (%s, %s, %s)",
        (nombre_usuario, generate_password_hash(clave), perfil),
    )


def cambiar_estado_usuario(id_usuario_sistema, activo):
    if not es_admin():
        raise PermissionError("Solo el administrador puede desactivar usuarios.")
    if not hay_columna_activo():
        raise RuntimeError(
            "La tabla usuario_sistema no tiene la columna 'activo'. Ejecute sql/usuario_sistema_activo.sql."
        )
    if int(id_usuario_sistema) == usuario_actual()["id"] and not activo:
        raise ValueError("No puede desactivar su propio usuario.")
    db.ejecutar(
        "UPDATE usuario_sistema SET activo = %s WHERE id_usuario_sistema = %s",
        (activo, int(id_usuario_sistema)),
    )


# ---------- Rutas Flask: login, logout y protección ----------

PAGINA_LOGIN = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monedero Caribe · Iniciar sesión</title>
<link rel="stylesheet" href="/assets/estilos.css">
</head><body class="pagina-login">
<main class="login-caja">
  <div class="login-marca"><span class="logo">MC</span><span>Monedero Caribe</span></div>
  <h1>Tablero de Inteligencia de Negocios</h1>
  <p class="texto-suave">Ingrese con su usuario y contraseña.</p>
  {mensaje}
  <form method="post" action="/login" autocomplete="on">
    <label for="usuario">Usuario</label>
    <input id="usuario" name="usuario" required autofocus value="{usuario}">
    <label for="clave">Contraseña</label>
    <input id="clave" name="clave" type="password" required>
    <button type="submit" class="boton boton-primario">Ingresar</button>
  </form>
</main></body></html>"""


def registrar_rutas(servidor):
    @servidor.before_request
    def proteger():
        ruta = request.path
        if ruta.startswith(RUTAS_PUBLICAS) or ruta == "/logout":
            return None
        if usuario_actual() is None:
            if ruta.startswith("/_dash"):
                return ("Sesión expirada", 401)
            return redirect("/login")
        if ruta.startswith(RUTAS_SOLO_ADMIN) and not es_admin():
            return redirect("/")
        return None

    @servidor.route("/login", methods=["GET", "POST"])
    def login():
        mensaje, usuario = "", ""
        if request.method == "POST":
            usuario = request.form.get("usuario", "")
            try:
                datos = autenticar(usuario, request.form.get("clave", ""))
            except Exception:  # noqa: BLE001
                datos = None
                mensaje = '<p class="aviso aviso-error">No se pudo conectar con la base de datos. Intente de nuevo.</p>'
            if datos:
                session.clear()
                session["id_usuario_sistema"] = datos["id"]
                session["nombre_usuario"] = datos["nombre"]
                session["admin"] = datos["admin"]
                return redirect("/")
            if not mensaje:
                mensaje = '<p class="aviso aviso-error">Usuario o contraseña incorrectos.</p>'
        elif usuario_actual():
            return redirect("/")
        return PAGINA_LOGIN.format(mensaje=mensaje, usuario=escape(usuario))

    @servidor.route("/logout")
    def logout():
        session.clear()
        return redirect("/login")

    @servidor.route("/salud")
    def salud():
        ok, detalle = db.comprobar_conexion()
        return ({"base_de_datos": "ok"} if ok else {"base_de_datos": "error"}), (200 if ok else 503)
