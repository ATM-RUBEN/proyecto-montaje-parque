from flask import (
    Flask,
    request,
    redirect,
    url_for,
    flash,
    render_template_string,
    session,
    send_from_directory,
)
from datetime import date
from pathlib import Path
import pandas as pd
import os

# ---------------- CONFIGURACIÓN ----------------

# Nuevo fichero de registros limpio
EXCEL_REGISTRO = "registro_montaje_v2.xlsx"
EXCEL_TRABAJADORES = "TRABAJADORES PIN.xlsx"

MAX_CT = 100
MAX_CAMPO = 10000
MAX_MESA = 10000

app = Flask(__name__)
app.secret_key = "cambia_esto_por_algo_mas_raro_y_largo"

# Carpeta static para logo y excels descargables
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

# ---------------- CARGA DE TRABAJADORES ----------------


def cargar_trabajadores_desde_excel():
    """
    Lee TRABAJADORES PIN.xlsx y devuelve:
      pin -> {"id": int, "nombre": str, "rol": str}
    Estructura esperada:
      Col B: Nombre
      Col C: ID
      Col D: PIN
      Col E: Rol (admin / jefe_obra / trabajador)
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
                "id": int(float(trabajador_id)) if trabajador_id else None,
                "nombre": nombre,
                "rol": rol_raw,
            }
        except Exception:
            continue

    return trabajadores


TRABAJADORES_PIN = cargar_trabajadores_desde_excel()

# ---------------- REGISTROS DE MONTAJE ----------------


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


def guardar_registros(df: pd.DataFrame):
    df.to_excel(EXCEL_REGISTRO, index=False)


# ---------------- ESTILOS COMUNES (ENCABEZADO TIPO APP CENTRADO) ----------------

COMMON_HEADER_CSS = """
    .app-shell {
      max-width: 480px;
      margin: 0 auto;
    }
    .app-header {
      text-align: center;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1px solid #ddd;
    }
    .app-logo {
      margin-bottom: 6px;
    }
    .app-logo img {
      height: 48px;
    }
    .app-user-name {
      font-weight: bold;
      font-size: 20px;
      margin-top: 4px;
    }
    .app-user-role {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 14px;
      color: #666;
      margin-top: 2px;
    }
    .app-user-role-icon {
      font-size: 16px;
    }
    .app-nav {
      margin-top: 10px;
      display: flex;
      justify-content: center;
      flex-wrap: wrap;
      gap: 8px;
    }
    .app-nav a {
      text-decoration: none;
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid #ddd;
      background: #ffffff;
      color: #1976d2;
      font-size: 14px;
    }
    .app-nav a.logout {
      border-color: #f5b5b5;
      background: #ffe5e5;
      color: #c00000;
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
      max-width: 90%;
    }
    .logo {
      width: 150px;
      margin-bottom: 10px;
    }
    h2 { margin: 10px 0 20px; color: #c00000; font-size: 20px; }
    input[type=password] {
      width: 100%;
      padding: 14px;
      font-size: 22px;
      text-align: center;
      border-radius: 10px;
      border: 1px solid #ccc;
      background: #eef4ff;
      letter-spacing: 0.35em;
      box-sizing: border-box;
    }
    button {
      margin-top: 20px;
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 999px;
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
      <input type="password" name="pin" maxlength="6" autofocus required>
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
      background: #f4f4f4;
      margin: 0;
      padding: 16px;
    }
    {{ common_header_css|safe }}
    .card {
      background: #fff;
      padding: 20px 18px 28px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
      max-width: 480px;
      margin: 0 auto;
    }
    label { display: block; margin-top: 10px; font-size: 14px; }
    input, select, textarea {
      width: 100%;
      padding: 12px;
      margin-top: 4px;
      border-radius: 10px;
      border: 1px solid #ccc;
      font-size: 16px;
      box-sizing: border-box;
    }
    textarea { resize: vertical; min-height: 80px; }
    .fila-tiempo {
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 5px;
    }
    .fila-tiempo input {
      flex: 1;
    }
    .btn-tiempo {
      padding: 10px 14px;
      border: none;
      border-radius: 999px;
      background: #e30613;
      color: white;
      cursor: pointer;
      font-size: 13px;
      min-width: 110px;
    }
    .btn-guardar {
      margin-top: 20px;
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 999px;
      background: #e30613;
      color: white;
      font-size: 18px;
      cursor: pointer;
    }
    .msg { margin-top: 10px; color: green; font-size: 14px; }
    .error { margin-top: 10px; color: #e30613; font-size: 14px; }
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
          <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_inicio')">Marcar inicio</button>
        </div>

        <label>Hora fin:</label>
        <div class="fila-tiempo">
          <input type="time" id="hora_fin" name="hora_fin" value="">
          <button type="button" class="btn-tiempo" onclick="marcarAhora('hora_fin')">Marcar fin</button>
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

RESUMEN_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Resumen de registros</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background:#f4f4f4;
      margin:0;
      padding:16px;
    }
    {{ common_header_css|safe }}
    .section {
      background:#fff;
      padding:15px;
      border-radius:14px;
      box-shadow:0 4px 15px rgba(0,0,0,0.15);
      margin-bottom:20px;
    }
    .section-header {
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin-bottom:10px;
      gap: 10px;
      flex-wrap: wrap;
    }
    h2 {
      margin:0;
      font-size:16px;
    }
    table {
      border-collapse:collapse;
      width:100%;
      font-size:12px;
    }
    th, td {
      border:1px solid #ddd;
      padding:6px 8px;
    }
    th { background:#eee; }
    .btn-descargar {
      padding:6px 10px;
      border-radius:999px;
      border:none;
      background:#1976d2;
      color:#fff;
      font-size:12px;
      cursor:pointer;
      white-space: nowrap;
    }
    .btn-borrar {
      padding:4px 6px;
      border-radius:6px;
      border:none;
      background:#e30613;
      color:#fff;
      font-size:11px;
      cursor:pointer;
    }
    .msg, .error {
      margin-bottom:10px;
      font-size:14px;
    }
    .error { color:#e30613; }
    .msg { color:green; }
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
        <a href="{{ url_for('resumen') }}">📋 Resumen</a>
        <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="section">
      <div class="section-header">
        <h2>Resumen diario (nº de registros por día)</h2>
        <form method="get" action="{{ url_for('descargar_resumen_diario') }}">
          <button type="submit" class="btn-descargar">⬇ Descargar Excel</button>
        </form>
      </div>

      {% if resumen_diario %}
        <table>
          <tr>
            <th>Fecha</th>
            <th>Nº registros</th>
          </tr>
          {% for fila in resumen_diario %}
            <tr>
              <td>{{ fila["Fecha"] }}</td>
              <td>{{ fila["Conteo"] }}</td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>Aún no hay registros.</p>
      {% endif %}
    </div>

    <div class="section">
      <div class="section-header">
        <h2>Detalle de todos los registros</h2>
        <form method="get" action="{{ url_for('descargar_detalle') }}">
          <button type="submit" class="btn-descargar">⬇ Descargar Excel</button>
        </form>
      </div>

      {% if registros %}
        <table>
          <tr>
            <th>#</th>
            <th>Trabajador</th>
            <th>Nombre</th>
            <th>Fecha</th>
            <th>Hora inicio</th>
            <th>Hora fin</th>
            <th>CT</th>
            <th>Campo</th>
            <th>Mesa</th>
            <th>Par</th>
            <th>CHECK LIST</th>
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
              <td>{{ row["Hora inicio"] }}</td>
              <td>{{ row["Hora fin"] }}</td>
              <td>{{ row["CT"] }}</td>
              <td>{{ row["Campo/Área"] }}</td>
              <td>{{ row["Nº Mesa"] }}</td>
              <td>{{ row["Par de apriete"] }}</td>
              <td>{{ row["CHECK LIST"] }}</td>
              <td>{{ row["Observaciones"] }}</td>
              <td><a href="{{ url_for('editar_registro', indice=idx) }}">Editar</a></td>
              <td>
                {% if usuario_rol == 'admin' %}
                  <form method="post" action="{{ url_for('borrar_registro', indice=idx) }}" onsubmit="return confirm('¿Seguro que quieres borrar este registro?');">
                    <button type="submit" class="btn-borrar">🗑</button>
                  </form>
                {% else %}
                  -
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </table>
      {% else %}
        <p>Aún no hay registros.</p>
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
    .card {
      background:#fff;
      padding:20px;
      border-radius:12px;
      max-width:480px;
      margin:0 auto;
      box-shadow:0 4px 10px rgba(0,0,0,0.15);
    }
    h2 { margin-top:0; font-size:18px; }
    label { display:block; margin-top:10px; font-size:14px; }
    input, select, textarea {
      width:100%;
      padding:8px;
      margin-top:4px;
      border-radius:8px;
      border:1px solid #ccc;
      box-sizing:border-box;
      font-size:14px;
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
    a { text-decoration:none; color:#1976d2; font-size:14px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Editar registro #{{ indice }}</h2>
    <p><a href="{{ url_for('resumen') }}">← Volver al resumen</a></p>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <form method="post">
      <p><strong>Estructura:</strong> CT {{ row["CT"] }} · Campo {{ row["Campo/Área"] }} · Mesa {{ row["Nº Mesa"] }}</p>

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
</body>
</html>
"""

ESTADISTICAS_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Estadísticas de montaje</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f4f4f4;
      margin: 0;
      padding: 16px;
    }
    {{ common_header_css|safe }}
    .grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
      margin-top: 10px;
    }
    @media (min-width: 700px) {
      .grid {
        grid-template-columns: repeat(2, minmax(260px, 1fr));
      }
    }
    .card {
      background: #fff;
      padding: 15px;
      border-radius: 16px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.15);
    }
    .card h3 {
      margin-top: 0;
      font-size: 16px;
      margin-bottom: 8px;
    }
    canvas {
      width: 100% !important;
      max-height: 260px;
    }
    .msg, .error {
      margin-bottom: 10px;
      font-size: 14px;
    }
    .error { color: #e30613; }
    .msg { color: green; }
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
        <a href="{{ url_for('resumen') }}">📋 Resumen</a>
        <a href="{{ url_for('estadisticas') }}">📊 Estadísticas</a>
        <a href="{{ url_for('logout') }}" class="logout">⏻ Salir</a>
      </nav>
    </header>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="{{ category }}">{{ message }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    {% if sin_datos %}
      <p>No hay datos suficientes todavía para mostrar estadísticas.</p>
    {% else %}
      <div class="grid">
        <div class="card">
          <h3>Avance diario (nº registros)</h3>
          <canvas id="chartDiario"></canvas>
        </div>

        <div class="card">
          <h3>CHECK LIST (OK / NO OK)</h3>
          <canvas id="chartChecklist"></canvas>
        </div>

        <div class="card">
          <h3>Par de apriete (OK / NO OK)</h3>
          <canvas id="chartParApriete"></canvas>
        </div>

        <div class="card">
          <h3>Mesas montadas por trabajador</h3>
          <canvas id="chartTrabajadores"></canvas>
        </div>
      </div>

      <script>
        const dailyLabels = {{ daily_labels|tojson }};
        const dailyValues = {{ daily_values|tojson }};

        const checklistLabels = {{ checklist_labels|tojson }};
        const checklistValues = {{ checklist_values|tojson }};

        const parLabels = {{ par_labels|tojson }};
        const parValues = {{ par_values|tojson }};

        const workerLabels = {{ worker_labels|tojson }};
        const workerValues = {{ worker_values|tojson }};

        const ctxDiario = document.getElementById('chartDiario');
        if (ctxDiario && dailyLabels.length > 0) {
          new Chart(ctxDiario, {
            type: 'bar',
            data: {
              labels: dailyLabels,
              datasets: [{
                label: 'Registros por día',
                data: dailyValues
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false
            }
          });
        }

        const ctxChecklist = document.getElementById('chartChecklist');
        if (ctxChecklist && checklistLabels.length > 0) {
          new Chart(ctxChecklist, {
            type: 'doughnut',
            data: {
              labels: checklistLabels,
              datasets: [{
                data: checklistValues
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false
            }
          });
        }

        const ctxPar = document.getElementById('chartParApriete');
        if (ctxPar && parLabels.length > 0) {
          new Chart(ctxPar, {
            type: 'doughnut',
            data: {
              labels: parLabels,
              datasets: [{
                data: parValues
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false
            }
          });
        }

        const ctxTrab = document.getElementById('chartTrabajadores');
        if (ctxTrab && workerLabels.length > 0) {
          new Chart(ctxTrab, {
            type: 'bar',
            data: {
              labels: workerLabels,
              datasets: [{
                label: 'Mesas registradas',
                data: workerValues
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false
            }
          });
        }
      </script>
    {% endif %}
  </div>
</body>
</html>
"""

# ---------------- CONTROL DE SESIÓN ----------------


def requiere_login():
    return "usuario_id" in session


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


# ---------------- FORMULARIO PRINCIPAL ----------------


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
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        cts=cts,
        campos=campos,
        mesas=mesas,
        common_header_css=COMMON_HEADER_CSS,
    )


# ---------------- RESUMEN ----------------


@app.route("/resumen", methods=["GET", "POST"])
def resumen():
    if not requiere_login():
        return redirect(url_for("login"))

    usuario_nombre = session["usuario_nombre"]
    usuario_rol = session["usuario_rol"]

    if usuario_rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para ver el resumen.", "error")
        return redirect(url_for("formulario"))

    df = cargar_registros()

    # Resumen por días
    if df.empty:
        resumen_diario = []
    else:
        df["Fecha"] = df["Fecha"].astype(str)
        resumen_diario = (
            df.groupby("Fecha")
            .size()
            .reset_index(name="Conteo")
            .to_dict("records")
        )

    registros = list(df.iterrows())

    return render_template_string(
        RESUMEN_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        resumen_diario=resumen_diario,
        registros=registros,
        common_header_css=COMMON_HEADER_CSS,
    )


# ---------------- DESCARGA EXCEL ----------------


@app.route("/descargar_resumen_diario")
def descargar_resumen_diario():
    df = cargar_registros()
    if df.empty:
        df_out = pd.DataFrame({"Fecha": [], "Conteo": []})
    else:
        df["Fecha"] = df["Fecha"].astype(str)
        df_out = df.groupby("Fecha").size().reset_index(name="Conteo")

    STATIC_DIR.mkdir(exist_ok=True)
    ruta = STATIC_DIR / "resumen_diario.xlsx"
    df_out.to_excel(ruta, index=False)

    return send_from_directory(STATIC_DIR, "resumen_diario.xlsx", as_attachment=True)


@app.route("/descargar_detalle")
def descargar_detalle():
    df = cargar_registros()
    STATIC_DIR.mkdir(exist_ok=True)
    ruta = STATIC_DIR / "detalle_registros.xlsx"
    df.to_excel(ruta, index=False)
    return send_from_directory(STATIC_DIR, "detalle_registros.xlsx", as_attachment=True)


# ---------------- EDICIÓN Y BORRADO ----------------


@app.route("/editar/<int:indice>", methods=["GET", "POST"])
def editar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol not in ("admin", "jefe_obra"):
        flash("No tienes permiso para editar registros.", "error")
        return redirect(url_for("resumen"))

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
    return render_template_string(EDIT_HTML, indice=indice, row=row)


@app.route("/borrar/<int:indice>", methods=["POST"])
def borrar_registro(indice):
    if not requiere_login():
        return redirect(url_for("login"))

    rol = session.get("usuario_rol", "trabajador")
    if rol != "admin":
        flash("Solo el administrador puede borrar registros.", "error")
        return redirect(url_for("resumen"))

    df = cargar_registros()

    if indice < 0 or indice >= len(df):
        flash("Registro no encontrado.", "error")
        return redirect(url_for("resumen"))

    df = df.drop(index=indice).reset_index(drop=True)
    guardar_registros(df)

    flash("Registro borrado correctamente.", "msg")
    return redirect(url_for("resumen"))


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
    if df.empty:
        return render_template_string(
            ESTADISTICAS_HTML,
            usuario_nombre=usuario_nombre,
            usuario_rol=usuario_rol,
            sin_datos=True,
            daily_labels=[],
            daily_values=[],
            checklist_labels=[],
            checklist_values=[],
            par_labels=[],
            par_values=[],
            worker_labels=[],
            worker_values=[],
            common_header_css=COMMON_HEADER_CSS,
        )

    df["Fecha"] = df["Fecha"].astype(str)

    # Avance diario
    diario = df.groupby("Fecha").size().reset_index(name="conteo")
    daily_labels = diario["Fecha"].tolist()
    daily_values = diario["conteo"].tolist()

    # Checklist
    checklist_counts = df["CHECK LIST"].value_counts()
    checklist_labels = checklist_counts.index.tolist()
    checklist_values = checklist_counts.values.tolist()

    # Par de apriete
    par_counts = df["Par de apriete"].value_counts()
    par_labels = par_counts.index.tolist()
    par_values = par_counts.values.tolist()

    # Por trabajador
    trab = df.groupby("Nombre").size().reset_index(name="conteo")
    worker_labels = trab["Nombre"].tolist()
    worker_values = trab["conteo"].tolist()

    return render_template_string(
        ESTADISTICAS_HTML,
        usuario_nombre=usuario_nombre,
        usuario_rol=usuario_rol,
        sin_datos=False,
        daily_labels=daily_labels,
        daily_values=daily_values,
        checklist_labels=checklist_labels,
        checklist_values=checklist_values,
        par_labels=par_labels,
        par_values=par_values,
        worker_labels=worker_labels,
        worker_values=worker_values,
        common_header_css=COMMON_HEADER_CSS,
    )


# ---------------- MAIN ----------------

if __name__ == "__main__":
    app.run(debug=True)
