-- Esquema mínimo, según el diagrama de la base de datos, SOLO para probar el tablero en una base local.
-- No es el esquema oficial del Momento 2 (ese ya está creado en Supabase).
CREATE TABLE usuario_sistema (id_usuario_sistema SERIAL PRIMARY KEY, nombre_usuario TEXT UNIQUE NOT NULL,
  contrasena_hash TEXT NOT NULL, perfil TEXT NOT NULL);
CREATE TABLE carga_archivo (id_carga SERIAL PRIMARY KEY, nombre_archivo TEXT, fecha_carga TIMESTAMP DEFAULT now(),
  id_usuario_sistema INT REFERENCES usuario_sistema, filas_leidas INT, filas_cargadas INT, filas_rechazadas INT);
CREATE TABLE fila_rechazada (id_rechazo SERIAL PRIMARY KEY, id_carga INT REFERENCES carga_archivo,
  numero_fila INT, motivo TEXT, contenido_original TEXT);
CREATE TABLE usuario (id_usuario TEXT PRIMARY KEY, fecha_registro DATE, ciudad TEXT, rango_edad TEXT,
  canal_registro TEXT, id_carga INT REFERENCES carga_archivo);
CREATE TABLE comercio (id_comercio TEXT PRIMARY KEY, categoria TEXT, ciudad TEXT, id_carga INT REFERENCES carga_archivo);
CREATE TABLE transaccion (id_transaccion TEXT PRIMARY KEY, fecha_hora TIMESTAMP, id_usuario TEXT REFERENCES usuario,
  tipo TEXT, id_comercio TEXT REFERENCES comercio, valor NUMERIC, estado TEXT, canal TEXT,
  id_carga INT REFERENCES carga_archivo);
CREATE TABLE reclamo (id_reclamo TEXT PRIMARY KEY, id_transaccion TEXT REFERENCES transaccion, fecha_reclamo DATE,
  motivo TEXT, dias_para_resolver NUMERIC, id_carga INT REFERENCES carga_archivo);
