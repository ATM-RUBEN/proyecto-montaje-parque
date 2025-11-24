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

# ---------------- CONFIGURACIÓN PRINCIPAL ----------------

EXCEL_REGISTRO = "registro_montaje_v2.xlsx"   # Fichero principal de estructuras
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"
EXCEL_FICHAJES = "registro_fichajes.xlsx"
EXCEL_VACACIONES = "solicitudes_vacaciones.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"


# ---------------- UTILIDADES TRABAJADORES ----------------


def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve un diccionario:
    pin -> {"id": int, "nombre": str, "rol": str}

    Se asume formato:
    Columna B = nombre
    Columna C = id
    Columna D = pin
    Columna E = rol (admin / jefe_obra / trabajador)
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


def mapa_trabajadores_por_id():
    """
    Devuelve {id_trabajador: nombre} a partir de TRABAJADORES_PIN
    """
    res = {}
    for pin, info in TRABAJADORES_PIN.items():
        res[info["id"]] = info["nombre"]
    return res


# ---------------- UTILIDADES EXCEL REGISTROS ----------------


def cargar_registros():
    path = Path(EXCEL_REGISTRO)
    if path.exists():
        return pd.read_excel(path)
    columnas = [
        "Trabajador",
        "Nombre",
        "Fecha",
        "Hora inicio",
        "Hora fin",
        "CT",
        "Campo/Área",
        "Nº Mesa",
        "Par de apriete",
        "CHECK LIST",
        "Observaciones",
    ]
    return pd.DataFrame(columns=columnas)


def guardar_registros(df):
    df.to_excel(EXCEL_REGISTRO, index=False)


# ---------------- UTILIDADES FICHAJES ----------------


def cargar_fichajes():
    path = Path(EXCEL_FICHAJES)
    if path.exists():
        return pd.read_excel(path)
    cols = [
        "Trabajador",
        "Nombre",
        "Fecha",
        "Hora entrada",
        "Lat entrada",
        "Lon entrada",
        "Hora salida",
        "Lat salida",
        "Lon salida",
        "Horas trabajadas",
        "Horas extra",
    ]
    return pd.DataFrame(columns=cols)


def guardar_fichajes(df: pd.DataFrame):
    df.to_excel(EXCEL_FICHAJES, index=False)


# ---------------- UTILIDADES VACACIONES ----------------


def cargar_vacaciones():
    path = Path(EXCEL_VACACIONES)
    if path.exists():
        return pd.read_excel(path)
    cols = [
        "ID",
        "Trabajador",
        "Nombre",
        "Fecha solicitud",
        "Desde",
        "Hasta",
        "Estado",
        "Comentario admin",
    ]
    return pd.DataFrame(columns=cols)


def guardar_vacaciones(df: pd.DataFrame):
    df.to_excel(EXCEL_VACACIONES, index=False)


# ---------------- CSS COMÚN ENCABEZADO TIPO APP ----------------

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
  font-size: 19px;
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
.msg {
  margin-top: 8px;
  color: green;
}
.error {
  margin-top: 8px;
  color: #e30613;
}
"""


# ---------------- PLANTILLAS HTML ----------------

LOGIN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ATM España · Acceso</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f4f4f4;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      margin: 0;
    }
    .card {
      background: #fff;
      padding: 30px 40px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
      text-align: center;
      width: 360px;
    }
    .logo {
      width: 140px;
      margin-bottom: 10px;
    }
    h2 { margin: 10px 0 20px; color: #c00000; }
    input[type=password] {
      width: 100%;
      padding: 12px;
      font-size: 20px;
      text-align: center;
      border-radius: 8px;
      border: 1px solid #ccc;
      background: #eef4ff;
      letter-spacing: 0.4em;
    }
    button {
      margin-top: 20px;
      width: 100%;
      padding: 12px;
      border: none;
      border-radius: 8px;
      background: #e30613;
      color: white;
      font-size: 18px;
      cursor: pointer;
    }
    .msg { margin-top: 15px; color: green; }
    .error { margin-top: 15px; color: #e30613; }
  </style>
</head>
<body>
  <div class="card">
    <img src="{{ url_for('static', filename='atm_logo.png') }}" class="logo" alt="ATM España">
    <h2>Introduce tu PIN</h2>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <input type="password" name="pin" maxlength="4" autofocus required>
      <button type="submit">Entrar</button>
    </form>
  </div>
</body>
</html>
"""

FORM_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Registro de montaje</title>
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
      padding:20px 20px 28px;
      border-radius:16px;
      box-shadow:0 4px 15px rgba(0,0,0,0.15);
      max-width:520px;
      margin:0 auto;
    }
    label { display:block; margin-top:10px; font-size:14px; }
    input, select, textarea {
      width:100%;
      padding:10px;
      margin-top:4px;
      border-radius:10px;
      border:1px solid #ccc;
      font-size:15px;
      box-sizing:border-box;
    }
    textarea { resize:vertical; min-height:70px; }
    .fila-tiempo {
      display:flex;
      gap:8px;
      align-items:center;
      margin-top:4px;
    }
    .fila-tiempo input {
      flex:1;
    }
    .btn-tiempo {
      padding:8px 10px;
      border:none;
      border-radius:999px;
      background:#e30613;
      color:white;
      cursor:pointer;
      font-size:12px;
      min-width:90px;
    }
    .btn-guardar {
      margin-top:18px;
      width:100%;
      padding:14px;
      border:none;
      border-radius:999px;
      background:#e30613;
      color:white;
      font-size:18px;
      cursor:pointer;
    }
  </style>
  <script>
    function marcarAhora(idCampo) {
      const ahora = new Date();
      const hh = String(ahora.getHours()).padStart(2, '0');
      const mm = String(ahora.getMinutes()).padStart(2, '0');
      document.getElementById(idCampo).value = hh + ":" + mm;
    }
  </script>
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

      <form method="post">
        <label>Hora inicio:</label>
        <div class="fila-tiempo">
          <input type="time" id="hora_inicio" name="hora_inicio" value="">
          <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_inicio')">Inicio ahora</button>
        </div>

        <label>Hora fin:</label>
        <div class="fila-tiempo">
          <input type="time" id="hora_fin" name="hora_fin" value="">
          <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_fin')">Fin ahora</button>
        </div>

        <label>CT:</label>
        <select name="ct">
          {% for i in cts %}
            <option value="{{ i }}">{{ i }}</option>
          {% endfor %}
        </select>

        <label>Campo / Área:</label>
        <select name="campo">
          {% for i in campos %}
            <option value="{{ i }}">{{ i }}</option>
          {% endfor %}
        </select>

        <label>Nº Mesa:</label>
        <select name="mesa">
          {% for i in mesas %}
            <option value="{{ i }}">{{ i }}</option>
          {% endfor %}
        </select>

        <label>Par de apriete:</label>
        <select name="par_apriete">
          <option value="OK">OK</option>
          <option value="NO OK">NO OK</option>
        </select>

        <label>CHECK LIST:</label>
        <select name="check_list">
          <option value="OK">OK</option>
          <option value="NO OK">NO OK</option>
        </select>

        <label>Observaciones:</label>
        <textarea name="observaciones"></textarea>

        <button type="submit" class="btn-guardar">Guardar registro</button>
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
    body {
      font-family: Arial, sans-serif;
      background:#f4f4f4;
      margin:0;
      padding:16px;
    }
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
    .btn-entrada {
      background:#2e7d32;
      color:#fff;
    }
    .btn-salida {
      background:#c00000;
      color:#fff;
    }
    .small {
      font-size:12px;
      color:#666;
      margin-top:10px;
    }
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

      <p>Jornada estándar: 8 h + 1 h de comida (no computable).</p>

      <form id="formFichaje" method="post">
        <input type="hidden" id="accion" name="accion" value="">
        <input type="hidden" id="lat" name="lat" value="">
        <input type="hidden" id="lon" name="lon" value="">
        <button type="button" class="btn-fichar btn-entrada" onclick="fichar('entrada')">
          Fichar ENTRADA
        </button>
        <button type="button" class="btn-fichar btn-salida" onclick="fichar('salida')">
          Fichar SALIDA
        </button>
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
              <td>{{ s["Estado"] }}</td>
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
                <td>{{ s["Estado"] }}</td>
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
        <div>
          <div class="filtro-label">CT:</div>
          <select name="ct" class="filtro-select">
            <option value="">(Todos)</option>
            {% for ct in list_cts %}
              <option value="{{ ct }}" {% if filtro_ct and filtro_ct == ct|string %}selected{% endif %}>{{ ct }}</option>
            {% endfor %}
          </select>
        </div>
        <div style="margin-top:6px;">
          <div class="filtro-label">Trabajador:</div>
          <select name="trabajador" class="filtro-select">
            <option value="">(Todos)</option>
            {% for t in list_trabajadores %}
              <option value="{{ t }}" {% if filtro_trabajador and filtro_trabajador == t %}selected{% endif %}>{{ t }}</option>
            {% endfor %}
          </select>
        </div>

        <div class="filtro-actions">
          <button type="submit" class="btn-filtrar">Aplicar filtros</button>
          <a href="{{ url_for('resumen') }}" class="btn-limpiar">Limpiar</a>
        </div>
      </form>
    </div>

    <!-- TABLA AVANCE POR CT -->
    <div class="card">
      <h3>% Avance por CT (filtro aplicado)</h3>
      {% if avance_ct %}
        <table>
          <tr>
            <th>CT</th>
            <th>Registros totales</th>
            <th>Terminadas 100%</th>
            <th>% Avance</th>
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
        <p>No hay datos para el filtro seleccionado.</p>
      {% endif %}
    </div>

    <!-- TABLA 1: RESUMEN DIARIO TODOS LOS REGISTROS -->
    <div class="card">
      <div class="toolbar">
        <span><strong>Resumen diario (TODOS los registros)</strong></span>
        <a class="btn-download" href="{{ url_for('descargar_resumen_diario') }}">⬇ Excel</a>
      </div>
      {% if resumen_diario_total %}
        <table>
          <tr>
            <th>Fecha</th>
            <th>Registros totales</th>
          </tr>
          {% for r in resumen_diario_total %}
            <tr>
              <td>{{ r["Fecha"] }}</td>
              <td>{{ r["Registros totales"] }}</td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay registros todavía.</p>
      {% endif %}
    </div>

    <!-- TABLA 2: RESUMEN DIARIO 100x100 TERMINADAS -->
    <div class="card">
      <div class="toolbar">
        <span><strong>Resumen diario (100×100 terminadas)</strong></span>
        <a class="btn-download" href="{{ url_for('descargar_resumen_100') }}">⬇ Excel</a>
      </div>
      {% if resumen_diario_100 %}
        <table>
          <tr>
            <th>Fecha</th>
            <th>Terminadas 100%</th>
          </tr>
          {% for r in resumen_diario_100 %}
            <tr>
              <td>{{ r["Fecha"] }}</td>
              <td>{{ r["Terminadas 100%"] }}</td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay estructuras terminadas al 100% todavía.</p>
      {% endif %}
    </div>

    <!-- TABLA 3: DETALLE COMPLETO -->
    <div class="card">
      <div class="toolbar">
        <span><strong>Detalle de todos los registros</strong></span>
        <a class="btn-download" href="{{ url_for('descargar_resumen_detalle') }}">⬇ Excel</a>
      </div>
      {% if registros %}
        <table>
          <tr>
            <th>#</th>
            <th>Trabajador</th>
            <th>Nombre</th>
            <th>Fecha</th>
            <th>CT</th>
            <th>Campo</th>
            <th>Mesa</th>
            <th>Par</th>
            <th>CHECK</th>
            <th>Obs.</th>
            <th>Editar</th>
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
              <td><a href="{{ url_for('editar_registro', indice=idx) }}" class="btn-edit">Editar</a></td>
              <td>
                {% if usuario_rol == 'admin' %}
                  <form method="post" action="{{ url_for('borrar_registro', indice=idx) }}">
                    <button type="submit" class="btn-delete">X</button>
                  </form>
                {% else %}
                  -
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>No hay registros todavía.</p>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

EDIT_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Editar registro</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; padding:16px; margin:0; }
    {{ common_header_css|safe }}
    .card {
      background:#fff;
      padding:20px;
      border-radius:12px;
      max-width:480px;
      margin:0 auto;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
    }
    label { display:block; margin-top:10px; }
    input, select, textarea {
      width:100%;
      padding:8px;
      margin-top:4px;
      border-radius:8px;
      border:1px solid #ccc;
      box-sizing:border-box;
    }
    textarea { resize:vertical; min-height:70px; }
    button {
      margin-top:20px;
      width:100%;
      padding:12px;
      border:none;
      border-radius:999px;
      background:#e30613;
      color:#fff;
      font-size:16px;
      cursor:pointer;
    }
    a { text-decoration:none; color:#1976d2; font-size:13px; }
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
        <a href="{{ url_for('resumen') }}">📋 Resumen</a>
        <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <div class="card">
      <p><a href="{{ url_for('resumen') }}">← Volver al resumen</a></p>

      {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
          {% for category, message in messages %}
            <div class="{{ category }}">{{ message }}</div>
          {% endfor %}
        {% endif %}
      {% endwith %}

      <h2 style="margin-top:0;">Editar registro #{{ indice }}</h2>
      <p><strong>Estructura:</strong> CT {{ row["CT"] }} · Campo {{ row["Campo/Área"] }} · Mesa {{ row["Nº Mesa"] }}</p>

      <form method="post">
        <label>Par de apriete:</label>
        <select name="par_apriete">
          <option value="OK" {% if row["Par de apriete"] == "OK" %}selected{% endif %}>OK</option>
          <option value="NO OK" {% if row["Par de apriete"] == "NO OK" %}selected{% endif %}>NO OK</option>
        </select>

        <label>CHECK LIST:</label>
        <select name="check_list">
          <option value="OK" {% if row["CHECK LIST"] == "OK" %}selected{% endif %}>OK</option>
          <option value="NO OK" {% if row["CHECK LIST"] == "NO OK" %}selected{% endif %}>NO OK</option>
        </select>

        <label>Observaciones:</label>
        <textarea name="observaciones">{{ row["Observaciones"] }}</textarea>

        <button type="submit">Guardar cambios</button>
      </form>
    </div>
  </div>
</body>
</html>
"""

ESTADISTICAS_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Estadísticas</title>
  <style>
    body { font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:16px; }
    {{ common_header_css|safe }}
    .card {
      background:#fff;
      padding:16px 12px 20px;
      border-radius:16px;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
      max-width:520px;
      margin:0 auto 16px auto;
    }
    h3 { margin-top:0; margin-bottom:8px; }
    canvas { max-width:100%; height:220px; }
    .btn-download {
      text-decoration:none;
      padding:6px 10px;
      border-radius:999px;
      background:#1976d2;
      color:#fff;
      font-size:12px;
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
        <a href="{{ url_for('resumen') }}">📋 Resumen</a>
        <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    <div class="card">
      <h3>Avance diario por CT</h3>
      <canvas id="chartAvanceCT"></canvas>
    </div>

    <div class="card">
      <h3>CHECK LIST OK / NO OK</h3>
      <canvas id="chartChecklist"></canvas>
    </div>

    <div class="card">
      <h3>Par de apriete OK / NO OK</h3>
      <canvas id="chartPar"></canvas>
    </div>

    <div class="card">
      <h3>Mesas montadas por trabajador</h3>
      <canvas id="chartTrabajadores"></canvas>
    </div>

    <div class="card">
      <h3>Informe de fichajes</h3>
      <p>Descargar informe mensual (todas las personas, vacaciones, no fichado, geolocalización):</p>
      <a href="{{ url_for('descargar_fichajes_mes') }}" class="btn-download">⬇ Informe fichajes (mes actual)</a>
    </div>
  </div>

  <script>
    const dataAvanceCT = {{ data_avance_ct|safe }};
    const dataChecklist = {{ data_checklist|safe }};
    const dataPar = {{ data_par|safe }};
    const dataMesasTrab = {{ data_mesas_trabajadores|safe }};

    // Avance diario por CT
    if (dataAvanceCT.labels.length > 0) {
      new Chart(document.getElementById('chartAvanceCT'), {
        type: 'line',
        data: {
          labels: dataAvanceCT.labels,
          datasets: dataAvanceCT.datasets
        },
        options: {
          plugins: {
            legend: { position: 'bottom' }
          },
          scales: {
            x: { ticks: { font: { size: 9 } } },
            y: { beginAtZero: true }
          }
        }
      });
    }

    // CHECK LIST
    new Chart(document.getElementById('chartChecklist'), {
      type: 'doughnut',
      data: {
        labels: ['OK', 'NO OK'],
        datasets: [{
          data: [dataChecklist.ok, dataChecklist.no_ok],
          backgroundColor: ['#2e7d32', '#c00000'],
        }]
      },
      options: {
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });

    // PAR
    new Chart(document.getElementById('chartPar'), {
      type: 'doughnut',
      data: {
        labels: ['OK', 'NO OK'],
        datasets: [{
          data: [dataPar.ok, dataPar.no_ok],
          backgroundColor: ['#2e7d32', '#c00000'],
        }]
      },
      options: {
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });

    // MESAS POR TRABAJADOR
    new Chart(document.getElementById('chartTrabajadores'), {
      type: 'bar',
      data: {
        labels: dataMesasTrab.labels,
        datasets: [{
          label: 'Mesas registradas',
          data: dataMesasTrab.values,
          backgroundColor: '#1976d2'
        }]
      },
      options: {
        plugins: {
          legend: { display:false },
        },
        scales: {
          x: { ticks: { font: { size: 10 } } },
          y: { beginAtZero:true }
        }
      }
    });
  </script>
</body>
</html>
"""


# ---------------- AUTH / SESIÓN ----------------


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        trabajador_info = TRABAJADORES_PIN.get(pin)

        if not trabajador_info:
            flash("PIN incorrecto. Inténtalo de nuevo.", "error")
            return render_template_string(LOGIN_HTML)

        session["usuario_id"] = trabajador_info["id"]
        session["usuario_nombre"] = trabajador_info["nombre"]
        session["usuario_rol"] = trabajador_info["rol"]

        return redirect(url_for("formulario"))

    return render_template_string(LOGIN_HTML)


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "msg")
    return redirect(url_for("login"))


def requiere_login():
    return "usuario_id" in session


# ---------------- FORMULARIO MONTAJE ----------------


@app.route("/formulario", methods=["GET", "POST"])
def formulario():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    if request.method == "POST":
        hora_inicio = request.form.get("hora_inicio", "")
        hora_fin = request.form.get("hora_fin", "")
        ct = request.form.get("ct", "")
        campo = request.form.get("campo", "")
        mesa = request.form.get("mesa", "")
        par_apriete = request.form.get("par_apriete", "")
        check_list = request.form.get("check_list", "")
        observaciones = request.form.get("observaciones", "")

        try:
            ct_int = int(ct)
            campo_int = int(campo)
            mesa_int = int(mesa)
        except ValueError:
            flash("CT, Campo y Mesa deben ser números válidos.", "error")
            return redirect(url_for("formulario"))

        df = cargar_registros()

        # Comprobar duplicado de estructura
        duplicado = df[
            (df["CT"] == ct_int)
            & (df["Campo/Área"] == campo_int)
            & (df["Nº Mesa"] == mesa_int)
        ]

        if not duplicado.empty:
            flash(
                "Esta estructura ya ha sido registrada anteriormente. "
                "Por favor, contacta con tu supervisor para aclarar esta situación.",
                "error",
            )
            return redirect(url_for("formulario"))

        hoy = date.today()

        nuevo = {
            "Trabajador": usuario_id,
            "Nombre": usuario_nombre,
            "Fecha": hoy,
            "Hora inicio": hora_inicio,
            "Hora fin": hora_fin,
            "CT": ct_int,
            "Campo/Área": campo_int,
            "Nº Mesa": mesa_int,
            "Par de apriete": par_apriete,
            "CHECK LIST": check_list,
            "Observaciones": observaciones,
        }

        df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
        guardar_registros(df)

        flash("✅ Registro guardado correctamente.", "msg")
        return redirect(url_for("formulario"))

    cts = list(range(1, MAX_CT + 1))
    campos = list(range(1, MAX_CAMPO + 1))
    mesas = list(range(1, MAX_MESA + 1))

    return render_template_string(
        FORM_HTML,
        cts=cts,
        campos=campos,
        mesas=mesas,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        common_header_css=COMMON_HEADER_CSS,
    )


# ---------------- FICHAR JORNADA ----------------


@app.route("/fichaje", methods=["GET", "POST"])
def fichaje():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    if request.method == "POST":
        accion = request.form.get("accion", "")
        lat = request.form.get("lat", "")
        lon = request.form.get("lon", "")

        ahora = datetime.now()
        hoy = ahora.date()
        hora_str = ahora.strftime("%H:%M:%S")

        df = cargar_fichajes()

        # localizamos si ya hay fichaje para hoy del trabajador
        if not df.empty and "Fecha" in df.columns:
            try:
                fechas = pd.to_datetime(df["Fecha"]).dt.date
                mask = (df["Trabajador"] == usuario_id) & (fechas == hoy)
            except Exception:
                mask = (df["Trabajador"] == usuario_id) & (df["Fecha"] == hoy)
        else:
            mask = (df["Trabajador"] == usuario_id) & (df["Fecha"] == hoy)

        if mask.any():
            idx = df[mask].index[0]
        else:
            nueva_fila = {
                "Trabajador": usuario_id,
                "Nombre": usuario_nombre,
                "Fecha": hoy,
                "Hora entrada": "",
                "Lat entrada": "",
                "Lon entrada": "",
                "Hora salida": "",
                "Lat salida": "",
                "Lon salida": "",
                "Horas trabajadas": 0.0,
                "Horas extra": 0.0,
            }
            df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
            idx = df.index[-1]

        if accion == "entrada":
            df.at[idx, "Hora entrada"] = hora_str
            df.at[idx, "Lat entrada"] = lat
            df.at[idx, "Lon entrada"] = lon
            flash(f"✅ Entrada fichada a las {hora_str}.", "msg")

        elif accion == "salida":
            df.at[idx, "Hora salida"] = hora_str
            df.at[idx, "Lat salida"] = lat
            df.at[idx, "Lon salida"] = lon

            hora_entrada_str = df.at[idx, "Hora entrada"]
            if hora_entrada_str:
                try:
                    h_ent = datetime.strptime(hora_entrada_str, "%H:%M:%S")
                    h_sal = datetime.strptime(hora_str, "%H:%M:%S")
                    if h_sal < h_ent:
                        h_sal += timedelta(days=1)

                    delta = h_sal - h_ent
                    horas_totales = delta.total_seconds() / 3600.0
                    horas_trabajadas = max(0.0, horas_totales - 1.0)  # restar comida

                    horas_extra = 0.0
                    if horas_trabajadas > 8.0:
                        horas_extra = horas_trabajadas - 8.0

                    df.at[idx, "Horas trabajadas"] = round(horas_trabajadas, 2)
                    df.at[idx, "Horas extra"] = round(horas_extra, 2)

                    flash(
                        f"✅ Salida fichada a las {hora_str}. "
                        f"Horas trabajadas: {horas_trabajadas:.2f} (extras: {horas_extra:.2f}).",
                        "msg",
                    )
                except Exception:
                    flash("Salida fichada, pero no se han podido calcular las horas.", "error")
            else:
                flash("⚠ Has fichado salida sin tener registrada una entrada.", "error")
        else:
            flash("Acción de fichaje no reconocida.", "error")

        guardar_fichajes(df)
        return redirect(url_for("fichaje"))

    return render_template_string(
        FICHAJE_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        common_header_css=COMMON_HEADER_CSS,
    )


# ---------------- VACACIONES ----------------


@app.route("/vacaciones", methods=["GET", "POST"])
def vacaciones():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    df = cargar_vacaciones()

    if request.method == "POST":
        desde = request.form.get("desde", "")
        hasta = request.form.get("hasta", "")

        if not desde or not hasta:
            flash("Debes indicar fecha de inicio y fin.", "error")
            return redirect(url_for("vacaciones"))

        try:
            d_desde = datetime.strptime(desde, "%Y-%m-%d").date()
            d_hasta = datetime.strptime(hasta, "%Y-%m-%d").date()
        except ValueError:
            flash("Formato de fecha inválido.", "error")
            return redirect(url_for("vacaciones"))

        if d_hasta < d_desde:
            flash("La fecha final no puede ser anterior a la inicial.", "error")
            return redirect(url_for("vacaciones"))

        if df.empty:
            nuevo_id = 1
        else:
            nuevo_id = int(df["ID"].max()) + 1

        nueva_fila = {
            "ID": nuevo_id,
            "Trabajador": usuario_id,
            "Nombre": usuario_nombre,
            "Fecha solicitud": date.today(),
            "Desde": d_desde,
            "Hasta": d_hasta,
            "Estado": "pendiente",
            "Comentario admin": "",
        }
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)
        guardar_vacaciones(df)

        flash("✅ Solicitud de vacaciones enviada.", "msg")
        return redirect(url_for("vacaciones"))

    if df.empty:
        mis_solicitudes = []
        todas_solicitudes = []
    else:
        mis_solicitudes = df[df["Trabajador"] == usuario_id].sort_values(
            by="Fecha solicitud", ascending=False
        ).to_dict("records")

        if usuario_rol in ("admin", "jefe_obra"):
            todas_solicitudes = df.sort_values(
                by="Fecha solicitud", ascending=False
            ).to_dict("records")
        else:
            todas_solicitudes = []

    return render_template_string(
        VACACIONES_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        mis_solicitudes=mis_solicitudes,
        todas_solicitudes=todas_solicitudes,
        common_header_css=COMMON_HEADER_CSS,
    )


@app.route("/vacaciones/gestionar/<int:id_solicitud>/<accion>", methods=["POST"])
def gestionar_vacacion(id_solicitud, accion):
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para gestionar vacaciones.", "error")
        return redirect(url_for("vacaciones"))

    df = cargar_vacaciones()
    if df.empty or id_solicitud not in df["ID"].values:
        flash("Solicitud no encontrada.", "error")
        return redirect(url_for("vacaciones"))

    idx = df.index[df["ID"] == id_solicitud][0]
    if accion == "aprobar":
        df.at[idx, "Estado"] = "aprobada"
    elif accion == "denegar":
        df.at[idx, "Estado"] = "denegada"

    guardar_vacaciones(df)
    flash(f"Solicitud {id_solicitud} actualizada a {df.at[idx, 'Estado']}.", "msg")
    return redirect(url_for("vacaciones"))


# ---------------- RESUMEN (DIARIO + DETALLE + AVANCE) ----------------


@app.route("/resumen")
def resumen():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para ver el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    registros = []
    resumen_diario_total = []
    resumen_diario_100 = []
    avance_ct = []
    list_cts = []
    list_trabajadores = []
    filtro_ct = request.args.get("ct", "").strip()
    filtro_trabajador = request.args.get("trabajador", "").strip()

    if not df.empty:
        # Asegurar tipo fecha
        try:
            df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
        except Exception:
            pass

        # Listas para filtros (sin filtrar aún)
        list_cts = sorted(df["CT"].dropna().unique().tolist())
        list_trabajadores = sorted(df["Nombre"].dropna().unique().tolist())

        # Aplicar filtros
        df_filtrado = df.copy()
        if filtro_ct:
            try:
                filtro_ct_int = int(filtro_ct)
                df_filtrado = df_filtrado[df_filtrado["CT"] == filtro_ct_int]
            except ValueError:
                pass
        if filtro_trabajador:
            df_filtrado = df_filtrado[df_filtrado["Nombre"] == filtro_trabajador]

        # Detalle (filtrado)
        df_detalle = df_filtrado.sort_values(by="Fecha", ascending=False)
        registros = list(df_detalle.iterrows())

        # Resumen diario TODOS los registros (filtrado)
        if not df_filtrado.empty:
            grp_all = df_filtrado.groupby("Fecha").size().reset_index(name="Registros totales")
            grp_all = grp_all.sort_values(by="Fecha", ascending=False)
            resumen_diario_total = grp_all.to_dict("records")

            # Resumen diario 100x100 terminadas (filtrado)
            df_ok = df_filtrado[
                (df_filtrado["Par de apriete"] == "OK")
                & (df_filtrado["CHECK LIST"] == "OK")
            ].copy()
            if not df_ok.empty:
                grp_ok = df_ok.groupby("Fecha").size().reset_index(name="Terminadas 100%")
                grp_ok = grp_ok.sort_values(by="Fecha", ascending=False)
                resumen_diario_100 = grp_ok.to_dict("records")

            # Avance por CT (filtrado)
            grp_total = df_filtrado.groupby("CT").size().reset_index(name="Total")
            df_ok_ct = df_filtrado[
                (df_filtrado["Par de apriete"] == "OK")
                & (df_filtrado["CHECK LIST"] == "OK")
            ]
            if not df_ok_ct.empty:
                grp_ok_ct = df_ok_ct.groupby("CT").size().reset_index(name="Terminadas")
            else:
                grp_ok_ct = pd.DataFrame(columns=["CT", "Terminadas"])

            df_avance = pd.merge(grp_total, grp_ok_ct, on="CT", how="left").fillna(0)
            df_avance["Terminadas"] = df_avance["Terminadas"].astype(int)
            df_avance["Porcentaje"] = (
                df_avance["Terminadas"] / df_avance["Total"] * 100
            ).round(1)
            avance_ct = df_avance.to_dict("records")

    return render_template_string(
        RESUMEN_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        registros=registros,
        resumen_diario_total=resumen_diario_total,
        resumen_diario_100=resumen_diario_100,
        avance_ct=avance_ct,
        list_cts=list_cts,
        list_trabajadores=list_trabajadores,
        filtro_ct=filtro_ct,
        filtro_trabajador=filtro_trabajador,
        common_header_css=COMMON_HEADER_CSS,
    )


@app.route("/descargar_resumen_diario")
def descargar_resumen_diario():
    if not requiere_login():
        return redirect(url_for("login"))
    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    if df.empty:
        flash("No hay datos para descargar.", "error")
        return redirect(url_for("resumen"))

    try:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
    except Exception:
        pass

    df_all = df.copy()
    df_ok = df[
        (df["Par de apriete"] == "OK")
        & (df["CHECK LIST"] == "OK")
    ].copy()

    grp_all = df_all.groupby("Fecha").size().reset_index(name="Registros totales")
    grp_ok = df_ok.groupby("Fecha").size().reset_index(name="Terminadas 100%")

    df_resum = pd.merge(grp_all, grp_ok, on="Fecha", how="left").fillna(0)
    df_resum["Terminadas 100%"] = df_resum["Terminadas 100%"].astype(int)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_resum.to_excel(writer, index=False, sheet_name="Resumen diario")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="resumen_diario_montaje.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/descargar_resumen_100")
def descargar_resumen_100():
    if not requiere_login():
        return redirect(url_for("login"))
    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar este resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    if df.empty:
        flash("No hay datos para descargar.", "error")
        return redirect(url_for("resumen"))

    try:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
    except Exception:
        pass

    df_ok = df[
        (df["Par de apriete"] == "OK")
        & (df["CHECK LIST"] == "OK")
    ].copy()
    if df_ok.empty:
        flash("No hay estructuras terminadas al 100%.", "error")
        return redirect(url_for("resumen"))

    grp_ok = df_ok.groupby("Fecha").size().reset_index(name="Terminadas 100%")
    grp_ok = grp_ok.sort_values(by="Fecha", ascending=False)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        grp_ok.to_excel(writer, index=False, sheet_name="Terminadas 100%")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="resumen_100_terminadas.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/descargar_resumen_detalle")
def descargar_resumen_detalle():
    if not requiere_login():
        return redirect(url_for("login"))
    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()
    if df.empty:
        flash("No hay datos para descargar.", "error")
        return redirect(url_for("resumen"))

    try:
        df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
    except Exception:
        pass

    df_detalle = df.sort_values(by="Fecha", ascending=False)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_detalle.to_excel(writer, index=False, sheet_name="Detalle registros")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="detalle_registros_montaje.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/editar/<int:indice>", methods=["GET", "POST"])
def editar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para editar registros.", "error")
        return redirect(url_for("formulario"))

    usuario_nombre = session["usuario_nombre"]

    df = cargar_registros()

    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    if request.method == "POST":
        par_apriete_nuevo = request.form.get("par_apriete", "")
        check_list_nuevo = request.form.get("check_list", "")
        obs_nueva = request.form.get("observaciones", "")

        df.at[indice, "Par de apriete"] = par_apriete_nuevo
        df.at[indice, "CHECK LIST"] = check_list_nuevo
        df.at[indice, "Observaciones"] = obs_nueva

        guardar_registros(df)

        flash("Cambios guardados correctamente.", "msg")
        return redirect(url_for("resumen"))

    row = df.loc[indice]
    return render_template_string(
        EDIT_HTML,
        indice=indice,
        row=row,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        common_header_css=COMMON_HEADER_CSS,
    )


@app.route("/borrar/<int:indice>", methods=["POST"])
def borrar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol != "admin":
        flash("Solo un administrador puede borrar registros.", "error")
        return redirect(url_for("resumen"))

    df = cargar_registros()
    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    df = df.drop(index=indice).reset_index(drop=True)
    guardar_registros(df)
    flash(f"Registro #{indice} borrado correctamente.", "msg")
    return redirect(url_for("resumen"))


# ---------------- DESCARGA INFORME FICHAJES (MES) ----------------


@app.route("/descargar_fichajes_mes")
def descargar_fichajes_mes():
    """
    Informe mensual de fichajes:
    - Una fila por trabajador y día del mes
    - Indica si está de VACACIONES, NO FICHADO o TRABAJADO
    - Incluye horas, extras y geolocalización (lat/lon + links a Google Maps)
    """
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_rol = session.get("usuario_rol", "trabajador")
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para descargar fichajes.", "error")
        return redirect(url_for("formulario"))

    hoy = date.today()
    anio = request.args.get("anio", type=int) or hoy.year
    mes = request.args.get("mes", type=int) or hoy.month

    df_f = cargar_fichajes()
    df_v = cargar_vacaciones()

    # Asegurar tipos de fecha
    if not df_f.empty:
        try:
            df_f["Fecha"] = pd.to_datetime(df_f["Fecha"]).dt.date
        except Exception:
            pass

    if not df_v.empty:
        try:
            df_v["Desde"] = pd.to_datetime(df_v["Desde"]).dt.date
            df_v["Hasta"] = pd.to_datetime(df_v["Hasta"]).dt.date
        except Exception:
            pass

    # Mapa de trabajadores por ID
    trabajadores_id = mapa_trabajadores_por_id()
    if not trabajadores_id:
        flash("No hay datos de trabajadores cargados.", "error")
        return redirect(url_for("estadisticas"))

    _, last_day = calendar.monthrange(anio, mes)

    filas = []

    for id_trab, nombre in trabajadores_id.items():
        for dia in range(1, last_day + 1):
            fecha = date(anio, mes, dia)
            estado_jornada = ""
            hora_entrada = ""
            hora_salida = ""
            horas_trab = ""
            horas_extra = ""
            lat_ent = ""
            lon_ent = ""
            lat_sal = ""
            lon_sal = ""
            link_ent = ""
            link_sal = ""

            # ¿Vacaciones aprobadas?
            en_vacaciones = False
            if not df_v.empty:
                mask_v = (
                    (df_v["Trabajador"] == id_trab)
                    & (df_v["Estado"] == "aprobada")
                    & (df_v["Desde"] <= fecha)
                    & (df_v["Hasta"] >= fecha)
                )
                en_vacaciones = mask_v.any()

            if en_vacaciones:
                estado_jornada = "Vacaciones"
            else:
                # ¿Hay fichajes para ese día?
                if not df_f.empty:
                    try:
                        fechas_f = pd.to_datetime(df_f["Fecha"]).dt.date
                    except Exception:
                        fechas_f = df_f["Fecha"]

                    mask_f = (df_f["Trabajador"] == id_trab) & (fechas_f == fecha)
                    if mask_f.any():
                        idx = df_f[mask_f].index[0]
                        hora_entrada = df_f.at[idx, "Hora entrada"]
                        hora_salida = df_f.at[idx, "Hora salida"]
                        horas_trab = df_f.at[idx, "Horas trabajadas"]
                        horas_extra = df_f.at[idx, "Horas extra"]
                        lat_ent = df_f.at[idx, "Lat entrada"]
                        lon_ent = df_f.at[idx, "Lon entrada"]
                        lat_sal = df_f.at[idx, "Lat salida"]
                        lon_sal = df_f.at[idx, "Lon salida"]

                        if lat_ent and lon_ent:
                            link_ent = f"https://www.google.com/maps?q={lat_ent},{lon_ent}"
                        if lat_sal and lon_sal:
                            link_sal = f"https://www.google.com/maps?q={lat_sal},{lon_sal}"

                        if hora_entrada and hora_salida:
                            estado_jornada = "Trabajado"
                        else:
                            estado_jornada = "Incompleto"
                    else:
                        estado_jornada = "No fichado"
                else:
                    estado_jornada = "No fichado"

            filas.append(
                {
                    "Año": anio,
                    "Mes": mes,
                    "Fecha": fecha,
                    "Trabajador ID": id_trab,
                    "Nombre": nombre,
                    "Estado jornada": estado_jornada,
                    "Hora entrada": hora_entrada,
                    "Hora salida": hora_salida,
                    "Horas trabajadas": horas_trab,
                    "Horas extra": horas_extra,
                    "Lat entrada": lat_ent,
                    "Lon entrada": lon_ent,
                    "Link entrada": link_ent,
                    "Lat salida": lat_sal,
                    "Lon salida": lon_sal,
                    "Link salida": link_sal,
                }
            )

    df_out = pd.DataFrame(filas)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_out.to_excel(
            writer,
            index=False,
            sheet_name=f"Fichajes_{anio}_{mes:02d}",
        )
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f"fichajes_{anio}_{mes:02d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------- ESTADÍSTICAS ----------------


@app.route("/estadisticas")
def estadisticas():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]
    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para ver estadísticas.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    cl_ok = cl_no = par_ok = par_no = 0
    mesas_trab = {"labels": [], "values": []}
    data_avance_ct = {"labels": [], "datasets": []}

    if not df.empty:
        try:
            df["Fecha"] = pd.to_datetime(df["Fecha"]).dt.date
        except Exception:
            pass

        # CHECK LIST
        cl_ok = int((df["CHECK LIST"] == "OK").sum())
        cl_no = int((df["CHECK LIST"] == "NO OK").sum())

        # PAR
        par_ok = int((df["Par de apriete"] == "OK").sum())
        par_no = int((df["Par de apriete"] == "NO OK").sum())

        # Mesas por trabajador
        por_trabajador = df.groupby("Nombre").size().reset_index(name="Mesas")
        mesas_trab["labels"] = por_trabajador["Nombre"].tolist()
        mesas_trab["values"] = por_trabajador["Mesas"].tolist()

        # Avance diario por CT (nº registros por día y CT)
        grp = df.groupby(["Fecha", "CT"]).size().reset_index(name="Total")
        if not grp.empty:
            pivot = grp.pivot(index="Fecha", columns="CT", values="Total").fillna(0)
            labels = [d.strftime("%Y-%m-%d") for d in pivot.index]
            datasets = []
            colores = [
                "#1976d2",
                "#c00000",
                "#2e7d32",
                "#ff9800",
                "#7b1fa2",
                "#0097a7",
                "#5d4037",
            ]
            for i, ct in enumerate(pivot.columns):
                datasets.append(
                    {
                        "label": f"CT {ct}",
                        "data": pivot[ct].tolist(),
                        "borderColor": colores[i % len(colores)],
                        "backgroundColor": colores[i % len(colores)],
                        "tension": 0.2,
                    }
                )
            data_avance_ct = {"labels": labels, "datasets": datasets}

    data_checklist = json.dumps({"ok": cl_ok, "no_ok": cl_no})
    data_par = json.dumps({"ok": par_ok, "no_ok": par_no})
    data_mesas_trabajadores = json.dumps(mesas_trab)
    data_avance_ct_json = json.dumps(data_avance_ct)

    return render_template_string(
        ESTADISTICAS_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        common_header_css=COMMON_HEADER_CSS,
        data_checklist=data_checklist,
        data_par=data_par,
        data_mesas_trabajadores=data_mesas_trabajadores,
        data_avance_ct=data_avance_ct_json,
    )


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app.run(debug=True)
