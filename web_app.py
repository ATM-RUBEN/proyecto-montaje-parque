from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    render_template_string,
    session,
    send_file,
)
from datetime import date, datetime, timedelta
from pathlib import Path
import pandas as pd
import io
import json
import calendar
import os
from sqlalchemy import create_engine, text


# ---------------- CONFIGURACIÓN PRINCIPAL ----------------

EXCEL_REGISTRO = "registro_montaje_v2.xlsx"   # Fichero principal de estructuras
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"
EXCEL_FICHAJES = "registro_fichajes.xlsx"
EXCEL_VACACIONES = "solicitudes_vacaciones.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.debug = True
@app.route("/debug_trabajadores")
def debug_trabajadores():
    import os

    path = EXCEL_TRABAJADORES
    exists = os.path.exists(path)

    msg = [f"Buscando archivo: {path}", f"¿Existe?: {exists}"]

    if exists:
        try:
            df = pd.read_excel(path)
            msg.append(f"Filas leídas: {len(df)}")
            msg.append(f"Columnas: {list(df.columns)}")
        except Exception as e:
            msg.append(f"ERROR al leer Excel: {e}")

    return "<br>".join(msg)

app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"

# ---------------- CONFIGURACIÓN BASE DE DATOS ----------------

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise RuntimeError("Falta la variable de entorno DATABASE_URL")

# Render da postgres:// y SQLAlchemy prefiere postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, future=True)

# --- RUTA DE PRUEBA BASE DE DATOS -----------------

@app.route("/test_db")
def test_db():
    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT 1")).scalar_one()
        return f"Conexión OK. Resultado SELECT 1 = {resultado}"
    except Exception as e:
        return f"ERROR al conectar con la base de datos: {e}"

def crear_tabla_registros_montaje():
    sql = text("""
        CREATE TABLE IF NOT EXISTS registros_montaje (
            id SERIAL PRIMARY KEY,
            trabajador INTEGER,
            nombre TEXT,
            fecha DATE,
            hora_inicio TIME,
            hora_fin TIME,
            ct INTEGER,
            campo_area TEXT,
            mesa TEXT,
            par_apriete TEXT,
            checklist BOOLEAN,
            observaciones TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        );
    """)
    with engine.begin() as conn:
        conn.execute(sql)

# --- CREAR TABLA REGISTROS -----------------
crear_tabla_registros_montaje()
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()

        if pin in TRABAJADORES_PIN:
            session["usuario_pin"] = pin
            return redirect(url_for("formulario"))

        flash("PIN incorrecto", "error")

    return render_template_string(LOGIN_HTML)
def usuario_actual():
    pin = session.get("usuario_pin")
    if pin and pin in TRABAJADORES_PIN:
        return TRABAJADORES_PIN[pin]
    return None
@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    usuario = usuario_actual()
    if not usuario:
        return redirect(url_for("login"))

    if request.method == "POST":
        df = cargar_registros()
        nuevo = {
            "Trabajador": usuario["id"],
            "Nombre": usuario["nombre"],
            "Fecha": request.form.get("fecha"),
            "Hora inicio": request.form.get("hora_inicio"),
            "Hora fin": request.form.get("hora_fin"),
            "CT": request.form.get("ct"),
            "Campo/Área": request.form.get("campo_area"),
            "Nº Mesa": request.form.get("mesa"),
            "Par de apriete": request.form.get("par"),
            "CHECK LIST": request.form.get("checklist"),
            "Observaciones": request.form.get("observaciones"),
        }
        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_registros(df)

        flash("Registro guardado", "msg")
        return redirect(url_for("formulario"))

    # GET: pintar formulario
    return render_template_string(
        FORMULARIO_HTML,
        common_header_css=COMMON_HEADER_CSS,
        usuario_nombre=usuario["nombre"],
        usuario_rol=usuario["rol"],
        hoy=date.today().isoformat(),
    )



@app.route("/debug_formulario")
def debug_formulario():
    try:
        usuario = usuario_actual()
        return f"""
        <h1>DEBUG FORMULARIO</h1>
        <p><b>Usuario actual:</b> {usuario}</p>
        """
    except Exception:
        import traceback
        return f"<h1>ERROR EN DEBUG</h1><pre>{traceback.format_exc()}</pre>"

@app.route("/fichaje", methods=["GET", "POST"])
def fichaje():
    usuario = usuario_actual()
    if not usuario:
        return redirect(url_for("login"))

    if request.method == "POST":
        df = cargar_fichajes()
        nuevo = {
            "Trabajador": usuario["id"],
            "Nombre": usuario["nombre"],
            "Fecha": date.today(),
            "Hora entrada": datetime.now().strftime("%H:%M:%S") if request.form["accion"] == "entrada" else None,
            "Hora salida": datetime.now().strftime("%H:%M:%S") if request.form["accion"] == "salida" else None,
            "Lat entrada": request.form.get("lat"),
            "Lon entrada": request.form.get("lon"),
        }
        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_fichajes(df)

        flash("Fichaje registrado", "msg")
        return redirect(url_for("fichaje"))

    return render_template_string(
        FICHAJE_HTML,
        common_header_css=COMMON_HEADER_CSS,
        usuario_nombre=usuario["nombre"],
        usuario_rol=usuario["rol"],
    )
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def guardar_registro_db(
    trabajador,
    nombre,
    fecha,
    hora_inicio,
    hora_fin,
    ct,
    campo_area,
    mesa,
    par_apriete,
    checklist,
    observaciones
):
    sql = text("""
        INSERT INTO registros_montaje
        (trabajador, nombre, fecha, hora_inicio, hora_fin, ct, campo_area, mesa, par_apriete, checklist, observaciones)
        VALUES
        (:trabajador, :nombre, :fecha, :hora_inicio, :hora_fin, :ct, :campo_area, :mesa, :par_apriete, :checklist, :observaciones)
    """)
    
    with engine.begin() as conn:
        conn.execute(sql, {
            "trabajador": trabajador,
            "nombre": nombre,
            "fecha": fecha,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "ct": ct,
            "campo_area": campo_area,
            "mesa": mesa,
            "par_apriete": par_apriete,
            "checklist": checklist,
            "observaciones": observaciones
        })


# ---------------- UTILIDADES TRABAJADORES ----------------

def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    pin -> {"id": int, "nombre": str, "rol": str}
    """
    path = Path(EXCEL_TRABAJADORES)
    if not path.exists():
        print("⚠ No se encuentra el archivo de trabajadores:", EXCEL_TRABAJADORES)
        return {}

    df = pd.read_excel(path)

    trabajadores = {}
    for _, row in df.iterrows():
        try:
            nombre = str(row.iloc[1]).strip()
            trabajador_id = str(row.iloc[2]).strip()
            pin = str(row.iloc[3]).strip()
            rol_raw = str(row.iloc[4]).strip().lower()

            if not pin or pin.lower() == "nan":
                continue

            if rol_raw not in {"admin", "jefe_obra", "trabajador"}:
                rol_raw = "trabajador"

            trabajadores[pin] = {
                "id": int(trabajador_id),
                "nombre": nombre,
                "rol": rol_raw,
            }
        except Exception:
            continue

    print("TRABAJADORES_PIN cargado:", trabajadores)
    return trabajadores


TRABAJADORES_PIN = cargar_trabajadores_desde_excel()
@app.route("/debug_login_pin")
def debug_login_pin():
    pin = request.args.get("pin", "").strip()
    from pprint import pformat

    info = TRABAJADORES_PIN.get(pin)
    return (
        f"<h1>Debug login PIN</h1>"
        f"<p>PIN recibido: <b>{pin}</b></p>"
        f"<p>Info en TRABAJADORES_PIN:</p>"
        f"<pre>{pformat(info)}</pre>"
    )


def mapa_trabajadores_por_id():
    res = {}
    for pin, info in TRABAJADORES_PIN.items():
        res[info["id"]] = info["nombre"]
    return res


# ---------------- UTILIDADES EXCEL ----------------

def cargar_registros():
    path = Path(EXCEL_REGISTRO)
    if path.exists():
        return pd.read_excel(path)
    columnas = [
        "Trabajador", "Nombre", "Fecha",
        "Hora inicio", "Hora fin",
        "CT", "Campo/Área", "Nº Mesa",
        "Par de apriete", "CHECK LIST", "Observaciones",
    ]
    return pd.DataFrame(columns=columnas)


def guardar_registros(df):
    """
    Sigue guardando en Excel como hasta ahora
    y además inserta el ÚLTIMO registro en la tabla registros_montaje.
    """
    # 1) Guardar en Excel (como siempre)
    df.to_excel(EXCEL_REGISTRO, index=False)

    # 2) Guardar el último registro en PostgreSQL
    if df.empty:
        return

    # Nos quedamos con la última fila añadida
    ultima = df.iloc[-1]

    # Transformaciones suaves de tipos
    fecha = ultima.get("Fecha")
    if pd.isna(fecha):
        fecha = None
    elif isinstance(fecha, datetime):
        fecha = fecha.date()

    hora_inicio = ultima.get("Hora inicio")
    if pd.isna(hora_inicio):
        hora_inicio = None
    elif isinstance(hora_inicio, datetime):
        hora_inicio = hora_inicio.time()

    hora_fin = ultima.get("Hora fin")
    if pd.isna(hora_fin):
        hora_fin = None
    elif isinstance(hora_fin, datetime):
        hora_fin = hora_fin.time()

    ct = ultima.get("CT")
    if pd.isna(ct):
        ct = None
    else:
        try:
            ct = int(ct)
        except Exception:
            ct = None

    checklist_raw = ultima.get("CHECK LIST")
    if pd.isna(checklist_raw):
        checklist = False
    elif isinstance(checklist_raw, str):
        checklist = checklist_raw.strip().lower() in ("1", "x", "sí", "si", "true", "ok")
    else:
        checklist = bool(checklist_raw)

    trabajador = ultima.get("Trabajador")
    nombre = ultima.get("Nombre")
    campo_area = ultima.get("Campo/Área")
    mesa = ultima.get("Nº Mesa")
    par_apriete = ultima.get("Par de apriete")
    observaciones = ultima.get("Observaciones")

    sql = text("""
        INSERT INTO registros_montaje
        (trabajador, nombre, fecha, hora_inicio, hora_fin, ct, campo_area, mesa,
         par_apriete, checklist, observaciones)
        VALUES
        (:trabajador, :nombre, :fecha, :hora_inicio, :hora_fin, :ct, :campo_area,
         :mesa, :par_apriete, :checklist, :observaciones)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(sql, {
                "trabajador": trabajador,
                "nombre": nombre,
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "ct": ct,
                "campo_area": campo_area,
                "mesa": mesa,
                "par_apriete": par_apriete,
                "checklist": checklist,
                "observaciones": observaciones,
            })
    except Exception as e:
        print("⚠ Error insertando en registros_montaje:", e)


# ---------------- UTILIDADES FICHAJES ----------------

def cargar_fichajes():
    path = Path(EXCEL_FICHAJES)
    if path.exists():
        return pd.read_excel(path)
    cols = [
        "Trabajador", "Nombre", "Fecha",
        "Hora entrada", "Lat entrada", "Lon entrada",
        "Hora salida", "Lat salida", "Lon salida",
        "Horas trabajadas", "Horas extra",
    ]
    return pd.DataFrame(columns=cols)


def guardar_fichajes(df):
    df.to_excel(EXCEL_FICHAJES, index=False)


# ---------------- UTILIDADES VACACIONES ----------------

def cargar_vacaciones():
    path = Path(EXCEL_VACACIONES)
    if path.exists():
        return pd.read_excel(path)
    cols = [
        "ID", "Trabajador", "Nombre",
        "Fecha solicitud", "Desde", "Hasta",
        "Estado", "Comentario admin",
    ]
    return pd.DataFrame(columns=cols)


def guardar_vacaciones(df):
    df.to_excel(EXCEL_VACACIONES, index=False)


# ---------------- CSS ENCABEZADO TIPO APP ----------------

COMMON_HEADER_CSS = """
.app-shell {
  max-width: 520px;
  margin: 0 auto;
}
.app-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 16px;
}
.app-logo img {
  height: 48px;
}
.app-user-name {
  font-weight: bold;
  margin-top: 6px;
  font-size: 20px;
  text-align: center;
}
.app-user-role {
  font-size: 13px;
  color: #666;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
}
.app-user-role-icon {
  font-size: 16px;
}
.app-nav {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 6px;
  margin-top: 10px;
}
.app-nav a {
  padding: 6px 10px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid #ddd;
  font-size: 12px;
  text-decoration: none;
  color: #333;
}
.app-nav a.logout {
  background: #ffe5e5;
  border-color: #ffb3b3;
  color: #c00000;
}
.msg { margin-top: 8px; color: green; }
.error { margin-top: 8px; color: #e30613; }
"""


# ---------------- LOGIN HTML ----------------

LOGIN_HTML = """
<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>ATM España · Acceso</title>
<style>
body {
  font-family: Arial, sans-serif;
  background:#f4f4f4;
  display:flex;
  justify-content:center;
  align-items:center;
  height:100vh;
  margin:0;
}
.card {
  background:#fff;
  padding:30px 40px;
  border-radius:16px;
  box-shadow:0 4px 15px rgba(0,0,0,0.15);
  text-align:center;
  width:360px;
}
.logo {
  width:140px;
  margin-bottom:10px;
}
h2 { margin:10px 0 20px; color:#c00000; }
input[type=password] {
  width:100%;
  padding:12px;
  font-size:20px;
  text-align:center;
  border-radius:8px;
  border:1px solid #ccc;
  background:#eef4ff;
  letter-spacing:0.4em;
}
button {
  margin-top:20px;
  width:100%;
  padding:12px;
  border:none;
  border-radius:8px;
  background:#e30613;
  color:white;
  font-size:18px;
  cursor:pointer;
}
.error { margin-top:15px; color:#e30613; }
.msg { margin-top:15px; color:green; }
</style>
</head>
<body>
<div class='card'>
  <img src='{{ url_for("static", filename="atm_logo.png") }}' class='logo'>
  <h2>Introduce tu PIN</h2>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, message in messages %}
        <div class='{{ category }}'>{{ message }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  <form method='post'>
    <input type='password' name='pin' maxlength='4' required autofocus>
    <button type='submit'>Entrar</button>
  </form>
</div>
</body>
</html>
"""
FORMULARIO_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Registro de montaje</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:16px; }
    {{ common_header_css|safe }}

    .card {
      background:#fff;
      padding:20px 18px 24px;
      border-radius:16px;
      box-shadow:0 4px 15px rgba(0,0,0,0.15);
      max-width:480px;
      margin:0 auto 16px auto;
    }
    label { display:block; margin-top:10px; font-size:14px; }
    input, textarea, select {
      width:100%;
      padding:8px;
      margin-top:4px;
      border-radius:8px;
      border:1px solid #ccc;
      font-size:14px;
      box-sizing:border-box;
    }
    textarea { min-height:70px; }
    button {
      margin-top:16px;
      width:100%;
      padding:12px;
      border:none;
      border-radius:999px;
      background:#e30613;
      color:#fff;
      font-size:16px;
      cursor:pointer;
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-logo">
        <img src="{{ url_for('static', filename='atm_logo.png') }}" alt="ATM España">
      </div>
      <div class="app-user-name">{{ usuario_nombre }}</div>
      <div class="app-user-role">
        <span class="app-user-role-icon">
          {% if usuario_rol == 'admin' %}👑{% elif usuario_rol == 'jefe_obra' %}🦺{% else %}👷{% endif %}
        </span>
        <span>{{ usuario_rol|capitalize }}</span>
      </div>
      <nav class="app-nav">
        <a href="{{ url_for('formulario') }}">📝 Formulario</a>
        <a href="{{ url_for('fichaje') }}">⏱ Fichar</a>
        <a href="{{ url_for('vacaciones') }}">🏖 Vacaciones</a>
        {% if usuario_rol in ['admin', 'jefe_obra'] %}
          <a href="{{ url_for('resumen') }}">📋 Resumen</a>
          <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        {% endif %}
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <div class="card">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <h3>Nuevo registro de montaje</h3>

      <form method="post">
        <label>Fecha:</label>
        <input type="date" name="fecha" value="{{ hoy }}" required>

        <label>Hora inicio:</label>
        <input type="time" name="hora_inicio" required>

        <label>Hora fin:</label>
        <input type="time" name="hora_fin">

        <label>CT:</label>
        <input type="number" name="ct" min="1" max="100">

        <label>Campo / Área:</label>
        <input type="text" name="campo_area">

        <label>Nº Mesa:</label>
        <input type="text" name="mesa">

        <label>Par de apriete:</label>
        <input type="text" name="par">

        <label>Checklist completado:</label>
        <select name="checklist">
          <option value="">(Sin marcar)</option>
          <option value="1">Sí</option>
          <option value="0">No</option>
        </select>

        <label>Observaciones:</label>
        <textarea name="observaciones"></textarea>

        <button type="submit">Guardar registro</button>
      </form>
    </div>
  </div>
</body>
</html>
"""

FICHAJE_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fichar jornada</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:16px; }
    {{ common_header_css|safe }}
    .card {
      background:#fff;
      padding:20px 18px 28px;
      border-radius:16px;
      box-shadow:0 4px 15px rgba(0,0,0,0.15);
      max-width:480px;
      margin:0 auto;
      text-align:center;
    }
    .btn-fichar {
      width:100%;
      padding:16px;
      margin-top:14px;
      border:none;
      border-radius:999px;
      font-size:18px;
      cursor:pointer;
    }
    .btn-entrada { background:#2e7d32; color:#fff; }
    .btn-salida { background:#c00000; color:#fff; }
    .small { font-size:12px; color:#666; margin-top:10px; }
  </style>
  <script>
    function fichar(tipo) {
      if (!navigator.geolocation) {
        alert("Tu dispositivo no permite geolocalización.");
        document.getElementById("accion").value = tipo;
        document.getElementById("formFichaje").submit();
        return;
      }

      navigator.geolocation.getCurrentPosition(
        function(pos) {
          document.getElementById("lat").value = pos.coords.latitude;
          document.getElementById("lon").value = pos.coords.longitude;
          document.getElementById("accion").value = tipo;
          document.getElementById("formFichaje").submit();
        },
        function(err) {
          alert("No se ha podido obtener la ubicación (" + err.message + "). Se fichará sin coordenadas.");
          document.getElementById("accion").value = tipo;
          document.getElementById("formFichaje").submit();
        }
      );
    }
  </script>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-logo">
        <img src="{{ url_for('static', filename='atm_logo.png') }}">
      </div>
      <div class="app-user-name">{{ usuario_nombre }}</div>
      <div class="app-user-role">
        <span class="app-user-role-icon">
          {% if usuario_rol == 'admin' %}👑{% elif usuario_rol == 'jefe_obra' %}🦺{% else %}👷{% endif %}
        </span>
        <span>{{ usuario_rol|capitalize }}</span>
      </div>
      <nav class="app-nav">
        <a href="{{ url_for('formulario') }}">📝 Formulario</a>
        <a href="{{ url_for('fichaje') }}">⏱ Fichar</a>
        <a href="{{ url_for('vacaciones') }}">🏖 Vacaciones</a>
        {% if usuario_rol in ['admin', 'jefe_obra'] %}
          <a href="{{ url_for('resumen') }}">📋 Resumen</a>
          <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        {% endif %}
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <div class="card">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <p>Jornada estándar: 8 h + 1 h de comida (no computable).</p>

      <form id="formFichaje" method="post">
        <input type="hidden" id="accion" name="accion">
        <input type="hidden" id="lat" name="lat">
        <input type="hidden" id="lon" name="lon">

        <button type="button" class="btn-fichar btn-entrada" onclick="fichar('entrada')">Fichar ENTRADA</button>
        <button type="button" class="btn-fichar btn-salida" onclick="fichar('salida')">Fichar SALIDA</button>
      </form>

      <p class="small">
        Se registrará la hora del servidor y, si está disponible, la posición GPS del dispositivo.
      </p>
    </div>
  </div>
</body>
</html>
"""
VACACIONES_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vacaciones</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background:#f4f4f4;
      margin:0;
      padding:16px;
    }
    {{ common_header_css|safe }}
    .card {
      background:#fff;
      padding:20px 18px 24px;
      border-radius:16px;
      box-shadow:0 4px 15px rgba(0,0,0,0.15);
      max-width:480px;
      margin:0 auto 16px auto;
    }
    label { display:block; margin-top:10px; font-size:14px; }
    input, textarea, select {
      width:100%;
      padding:10px;
      margin-top:4px;
      border-radius:10px;
      border:1px solid #ccc;
      font-size:14px;
      box-sizing:border-box;
    }
    button {
      margin-top:16px;
      width:100%;
      padding:12px;
      border:none;
      border-radius:999px;
      background:#1976d2;
      color:#fff;
      font-size:16px;
      cursor:pointer;
    }
    table {
      border-collapse:collapse;
      width:100%;
      font-size:12px;
    }
    th, td {
      border:1px solid #ddd;
      padding:6px 4px;
    }
    th { background:#eee; }
    .admin-section {
      background:#fff;
      padding:12px 10px 16px;
      border-radius:14px;
      box-shadow:0 4px 12px rgba(0,0,0,0.12);
      max-width:480px;
      margin:0 auto;
    }
    .inline-form {
      display:inline-block;
      margin:0 2px;
    }
    .inline-form button {
      width:auto;
      padding:4px 8px;
      font-size:11px;
      border-radius:8px;
    }
    .btn-approve { background:#2e7d32; color:#fff; }
    .btn-deny { background:#c00000; color:#fff; }
    .estado-aprobada { color:#2e7d32; font-weight:bold; }
    .estado-denegada { color:#c00000; font-weight:bold; }
    .estado-pendiente { color:#ff8c00; font-weight:bold; }
  </style>
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="app-logo">
        <img src="{{ url_for('static', filename='atm_logo.png') }}" alt="ATM España">
      </div>
      <div class="app-user-name">{{ usuario_nombre }}</div>
      <div class="app-user-role">
        <span class="app-user-role-icon">
          {% if usuario_rol == 'admin' %}👑{% elif usuario_rol == 'jefe_obra' %}🦺{% else %}👷{% endif %}
        </span>
        <span>{{ usuario_rol|capitalize }}</span>
      </div>
      <nav class="app-nav">
        <a href="{{ url_for('formulario') }}">📝 Formulario</a>
        <a href="{{ url_for('fichaje') }}">⏱ Fichar</a>
        <a href="{{ url_for('vacaciones') }}">🏖 Vacaciones</a>
        {% if usuario_rol in ['admin', 'jefe_obra'] %}
          <a href="{{ url_for('resumen') }}">📋 Resumen</a>
          <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        {% endif %}
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <div class="card">
      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <h3>Solicitar vacaciones</h3>
      <form method="post">
        <label>Desde:</label>
        <input type="date" name="desde" required>

        <label>Hasta:</label>
        <input type="date" name="hasta" required>

        <button type="submit">Enviar solicitud</button>
      </form>
    </div>

    <div class="card">
      <h3>Mis solicitudes</h3>
      {% if mis_solicitudes %}
        <table>
          <tr>
            <th>ID</th>
            <th>Desde</th>
            <th>Hasta</th>
            <th>Estado</th>
            <th>Comentario</th>
          </tr>
          {% for s in mis_solicitudes %}
            <tr>
              <td>{{ s["ID"] }}</td>
              <td>{{ s["Desde"] }}</td>
              <td>{{ s["Hasta"] }}</td>
              <td>
                <span class="
                  {% if s['Estado'] == 'aprobada' %}estado-aprobada
                  {% elif s['Estado'] == 'denegada' %}estado-denegada
                  {% else %}estado-pendiente{% endif %}
                ">
                  {{ s["Estado"] }}
                </span>
              </td>
              <td>{{ s["Comentario admin"] }}</td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>Aún no has solicitado vacaciones.</p>
      {% endif %}
    </div>

    {% if usuario_rol in ['admin', 'jefe_obra'] %}
      <div class="admin-section">
        <h3>Solicitudes de vacaciones (todas)</h3>
        {% if todas_solicitudes %}
          <table>
            <tr>
              <th>ID</th>
              <th>Trabajador</th>
              <th>Desde</th>
              <th>Hasta</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
            {% for s in todas_solicitudes %}
              <tr>
                <td>{{ s["ID"] }}</td>
                <td>{{ s["Nombre"] }}</td>
                <td>{{ s["Desde"] }}</td>
                <td>{{ s["Hasta"] }}</td>
                <td>
                  <span class="
                    {% if s['Estado'] == 'aprobada' %}estado-aprobada
                    {% elif s['Estado'] == 'denegada' %}estado-denegada
                    {% else %}estado-pendiente{% endif %}
                  ">
                    {{ s["Estado"] }}
                  </span>
                </td>
                <td>
                  {% if s["Estado"] == "pendiente" %}
                    <form method="post" class="inline-form" action="{{ url_for('gestionar_vacacion', id_solicitud=s['ID'], accion='aprobar') }}">
                      <button type="submit" class="btn-approve">✔ Aprobar</button>
                    </form>
                    <form method="post" class="inline-form" action="{{ url_for('gestionar_vacacion', id_solicitud=s['ID'], accion='denegar') }}">
                      <button type="submit" class="btn-deny">✖ Denegar</button>
                    </form>
                  {% else %}
                    -
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          </table>
        {% else %}
          <p>No hay solicitudes registradas.</p>
        {% endif %}
      </div>
    {% endif %}
  </div>
</body>
</html>
"""

RESUMEN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Resumen de registros</title>
  <style>
    body { font-family: Arial, sans-serif; padding:16px; background:#f4f4f4; margin:0; }
    {{ common_header_css|safe }}

    .card {
      background:#fff;
      padding:14px 12px 16px;
      border-radius:16px;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
      max-width:520px;
      margin:0 auto 16px auto;
    }

    h3 { margin-top:0; margin-bottom:8px; }

    table {
      border-collapse: collapse;
      width: 100%;
      background:#fff;
      font-size:11px;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 4px 5px;
    }
    th { background:#eee; }

    .toolbar {
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:6px;
      font-size:12px;
    }

    .btn-download {
      text-decoration:none;
      padding:4px 8px;
      border-radius:999px;
      background:#1976d2;
      color:#fff;
      font-size:11px;
    }

    .btn-delete {
      border:none;
      background:#c00000;
      color:#fff;
      padding:3px 6px;
      font-size:10px;
      border-radius:6px;
      cursor:pointer;
    }

    .btn-edit {
      font-size:11px;
      text-decoration:none;
      color:#1976d2;
    }

    /* Filtros */
    .filtro-label {
      font-size:13px;
      margin-top:4px;
    }
    .filtro-select {
      width:100%;
      padding:6px;
      border-radius:8px;
      border:1px solid #ccc;
      font-size:13px;
      margin-top:2px;
      box-sizing:border-box;
    }
    .filtro-actions {
      margin-top:8px;
      display:flex;
      justify-content:space-between;
      gap:6px;
    }
    .btn-filtrar, .btn-limpiar {
      flex:1;
      padding:6px 8px;
      border-radius:999px;
      border:none;
      font-size:13px;
      cursor:pointer;
    }
    .btn-filtrar {
      background:#1976d2;
      color:#fff;
    }
    .btn-limpiar {
      background:#eee;
      color:#333;
      text-align:center;
      text-decoration:none;
      display:inline-block;
      line-height:1.8;
    }
  </style>
</head>

<body>
  <div class="app-shell">

    <!-- APP HEADER -->
    <header class="app-header">
      <div class="app-logo">
        <img src="{{ url_for('static', filename='atm_logo.png') }}" alt="ATM España">
      </div>
      <div class="app-user-name">{{ usuario_nombre }}</div>
      <div class="app-user-role">
        <span class="app-user-role-icon">
          {% if usuario_rol == 'admin' %}👑{% elif usuario_rol == 'jefe_obra' %}🦺{% else %}👷{% endif %}
        </span>
        <span>{{ usuario_rol|capitalize }}</span>
      </div>

      <nav class="app-nav">
        <a href="{{ url_for('formulario') }}">📝 Formulario</a>
        <a href="{{ url_for('fichaje') }}">⏱ Fichar</a>
        <a href="{{ url_for('vacaciones') }}">🏖 Vacaciones</a>
        <a href="{{ url_for('resumen') }}">📋 Resumen</a>
        <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <!-- Mensajes -->
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="card">
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    <!-- FILTROS -->
    <div class="card">
      <h3>Filtros</h3>
      <form method="get">

        <div class="filtro-label">CT:</div>
        <select name="ct" class="filtro-select">
          <option value="">(Todos)</option>
          {% for ct in list_cts %}
            <option value="{{ ct }}" {% if filtro_ct and filtro_ct == ct|string %}selected{% endif %}>CT {{ ct }}</option>
          {% endfor %}
        </select>

        <div class="filtro-label">Trabajador:</div>
        <select name="trabajador" class="filtro-select">
          <option value="">(Todos)</option>
          {% for t in list_trabajadores %}
            <option value="{{ t }}" {% if filtro_trabajador and filtro_trabajador == t %}selected{% endif %}>{{ t }}</option>
          {% endfor %}
        </select>

        <div class="filtro-actions">
          <button type="submit" class="btn-filtrar">Aplicar filtros</button>
          <a href="{{ url_for('resumen') }}" class="btn-limpiar">Limpiar</a>
        </div>
      </form>
    </div>

    <!-- AVANCE POR CT -->
    <div class="card">
      <h3>% Avance por CT</h3>

      {% if avance_ct %}
        <table>
          <tr>
            <th>CT</th>
            <th>Total</th>
            <th>100% OK</th>
            <th>%</th>
          </tr>
          {% for r in avance_ct %}
            <tr>
              <td>{{ r["CT"] }}</td>
              <td>{{ r["Total"] }}</td>
              <td>{{ r["Terminadas"] }}</td>
              <td>{{ r["Porcentaje"] }}%</td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay datos con este filtro.</p>
      {% endif %}
    </div>

    <!-- RESUMEN DIARIO (TODOS) -->
    <div class="card">
      <div class="toolbar">
        <strong>Resumen diario (todos)</strong>
        <a class="btn-download" href="{{ url_for('descargar_resumen_diario') }}">⬇ Excel</a>
      </div>

      {% if resumen_diario_total %}
        <table>
          <tr><th>Fecha</th><th>Registros</th></tr>
          {% for r in resumen_diario_total %}
          <tr>
            <td>{{ r["Fecha"] }}</td>
            <td>{{ r["Registros totales"] }}</td>
          </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay registros.</p>
      {% endif %}
    </div>

    <!-- RESUMEN DIARIO (100%) -->
    <div class="card">
      <div class="toolbar">
        <strong>Resumen diario 100×100</strong>
        <a class="btn-download" href="{{ url_for('descargar_resumen_100') }}">⬇ Excel</a>
      </div>

      {% if resumen_diario_100 %}
        <table>
          <tr><th>Fecha</th><th>100% OK</th></tr>
          {% for r in resumen_diario_100 %}
          <tr>
            <td>{{ r["Fecha"] }}</td>
            <td>{{ r["Terminadas 100%"] }}</td>
          </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay estructuras al 100%.</p>
      {% endif %}
    </div>

    <!-- DETALLE COMPLETO -->
    <div class="card">
      <div class="toolbar">
        <strong>Detalle completo</strong>
        <a class="btn-download" href="{{ url_for('descargar_resumen_detalle') }}">⬇ Excel</a>
      </div>

      {% if registros %}
        <table>
          <tr>
            <th>#</th>
            <th>Trab.</th>
            <th>Nombre</th>
            <th>F.</th>
            <th>CT</th>
            <th>C</th>
            <th>M</th>
            <th>Par</th>
            <th>Check</th>
            <th>Obs</th>
            <th>Edit</th>
            <th>Borrar</th>
          </tr>

          {% for idx, row in registros %}
          <tr>
            <td>{{ idx }}</td>
            <td>{{ row["Trabajador"] }}</td>
            <td>{{ row["Nombre"] }}</td>
            <td>{{ row["Fecha"] }}</td>
            <td>{{ row["CT"] }}</td>
            <td>{{ row["Campo/Área"] }}</td>
            <td>{{ row["Nº Mesa"] }}</td>
            <td>{{ row["Par de apriete"] }}</td>
            <td>{{ row["CHECK LIST"] }}</td>
            <td>{{ row["Observaciones"] }}</td>

            <td><a class="btn-edit" href="{{ url_for('editar_registro', indice=idx) }}"✏️</a></td>

            <td>
              {% if usuario_rol == 'admin' %}
              <form method="post" action="{{ url_for('borrar_registro', indice=idx) }}">
                <button class="btn-delete">X</button>
              </form>
              {% else %}
                -
              {% endif %}
            </td>
          </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay registros.</p>
      {% endif %}
    </div>

  </div>
</body>
</html>
"""
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
