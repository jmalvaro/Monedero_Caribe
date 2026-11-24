"""Crea (o actualiza la contraseña de) un usuario del sistema desde la terminal.

Uso:  python -m scripts.crear_admin <nombre_usuario> [administrador|consulta]
La contraseña se pide sin mostrarla y se guarda cifrada (RF-03, RNF-02).
"""
import getpass
import sys

from werkzeug.security import generate_password_hash

from app import db


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    nombre = sys.argv[1].strip()
    perfil = sys.argv[2] if len(sys.argv) > 2 else "administrador"
    if perfil not in ("administrador", "consulta"):
        raise SystemExit("El perfil debe ser administrador o consulta.")
    clave = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if len(clave) < 8 or clave != getpass.getpass("Repita la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden o son muy cortas.")
    hash_clave = generate_password_hash(clave)
    existe = db.consultar("SELECT id_usuario_sistema FROM usuario_sistema WHERE lower(nombre_usuario) = lower(%s)",
                          (nombre,))
    if existe.empty:
        db.ejecutar("INSERT INTO usuario_sistema (nombre_usuario, contrasena_hash, perfil) VALUES (%s, %s, %s)",
                    (nombre, hash_clave, perfil))
        print(f"Usuario {nombre} creado con perfil {perfil}.")
    else:
        db.ejecutar("UPDATE usuario_sistema SET contrasena_hash = %s, perfil = %s WHERE id_usuario_sistema = %s",
                    (hash_clave, perfil, int(existe.iloc[0, 0])))
        print(f"Usuario {nombre} actualizado con perfil {perfil}.")


if __name__ == "__main__":
    main()
